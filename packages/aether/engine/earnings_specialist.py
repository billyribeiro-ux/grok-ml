"""
Earnings / pre-earnings specialist model.

Local-only. Uses event tables on LaCie (no network, no invented rows).

Predicts P(post_ret_1d > 0) from **pre-event only** features so the model
is usable for pre-earnings / event-day positioning without label leakage
from actual EPS (unknown until release).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aether.engine.scorer import LogisticScorer
from aether.paths import PROCESSED, require_lacie

EVENTS_DIR = PROCESSED / "research" / "earnings_events"

# Features known (or proxyable) before / at open of earnings reaction window
PRE_EVENT_FEATURES = (
    "pre_ret_1d",
    "pre_ret_3d",
    "pre_ret_5d",
    "is_bmo",
    "is_amc",
    "has_eps_estimate",
    "eps_estimated_z",  # cross-section z within train fold only — filled at fit time
)

LABEL_COL = "y_up_post_1d"


@dataclass
class EarningsSpecialistResult:
    universe: str
    window: str
    n_events: int
    n_train: int
    n_test: int
    train_frac: float
    accuracy: float
    brier: float
    base_rate: float
    lift: float
    long_only_mean_post_1d: float | None
    short_only_mean_post_1d: float | None
    feature_weights: dict[str, float]
    cut_date: str
    written_at: str
    path: str | None = None


def load_event_table(universe: str = "sp500") -> pd.DataFrame:
    """Load parquet event table; raise if missing (honest)."""
    require_lacie()
    path = EVENTS_DIR / f"{universe}_2018_20260710.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"earnings event table missing: {path} — run scripts/build_earnings_event_tables.py"
        )
    df = pd.read_parquet(path)
    df["earnings_date"] = pd.to_datetime(df["earnings_date"]).dt.normalize()
    return df.sort_values(["earnings_date", "symbol"]).reset_index(drop=True)


def prepare_specialist_frame(events: pd.DataFrame) -> pd.DataFrame:
    """Add pre-event features + label; drop rows without post_ret_1d."""
    df = events.copy()
    if "post_ret_1d" not in df.columns:
        raise ValueError("event table missing post_ret_1d")
    df = df.dropna(subset=["post_ret_1d"]).copy()
    df[LABEL_COL] = (df["post_ret_1d"].astype(float) > 0).astype(float)
    if "time" in df.columns:
        t = df["time"].astype(str).str.lower().fillna("")
        df["is_bmo"] = (t == "bmo").astype(float)
        df["is_amc"] = (t == "amc").astype(float)
    else:
        df["is_bmo"] = 0.0
        df["is_amc"] = 0.0
    if "epsEstimated" in df.columns:
        est = pd.to_numeric(df["epsEstimated"], errors="coerce")
        df["has_eps_estimate"] = est.notna().astype(float)
        # raw estimate kept; z-scored within train at fit time into eps_estimated_z
        df["eps_estimated_raw"] = est
    else:
        df["has_eps_estimate"] = 0.0
        df["eps_estimated_raw"] = np.nan
    for c in ("pre_ret_1d", "pre_ret_3d", "pre_ret_5d"):
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _attach_train_z(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cross-section z of eps estimate using train stats only (no leak)."""
    tr = train.copy()
    te = test.copy()
    raw = tr["eps_estimated_raw"]
    mu = float(raw.mean()) if raw.notna().any() else 0.0
    sig = float(raw.std()) if raw.notna().any() else 1.0
    if sig < 1e-8:
        sig = 1.0
    tr["eps_estimated_z"] = ((raw - mu) / sig).fillna(0.0)
    te["eps_estimated_z"] = ((te["eps_estimated_raw"] - mu) / sig).fillna(0.0)
    return tr, te


def run_earnings_specialist(
    universe: str = "sp500",
    *,
    train_frac: float = 0.7,
    min_confidence: float = 0.55,
    write: bool = True,
) -> EarningsSpecialistResult:
    """
    Time-ordered single cut: train on earlier earnings events, test on later.
    """
    events = load_event_table(universe)
    df = prepare_specialist_frame(events)
    if len(df) < 100:
        raise RuntimeError(f"not enough labeled earnings events: {len(df)}")

    dates = sorted(df["earnings_date"].unique())
    cut_idx = int(len(dates) * train_frac)
    cut_idx = min(max(cut_idx, 5), len(dates) - 5)
    cut = dates[cut_idx]

    train = df[df["earnings_date"] < cut].copy()
    test = df[df["earnings_date"] >= cut].copy()
    train, test = _attach_train_z(train, test)

    # fill pre-ret NaNs neutrally for model rows
    for c in PRE_EVENT_FEATURES:
        if c not in train.columns:
            train[c] = 0.0
            test[c] = 0.0
        train[c] = train[c].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        test[c] = test[c].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    scorer = LogisticScorer(
        feature_cols=PRE_EVENT_FEATURES,
        label_col=LABEL_COL,
        epochs=120,
        lr=0.08,
        l2=1e-3,
    )
    scorer.fit(train)
    proba = scorer.predict_proba(test)
    y = test[LABEL_COL].to_numpy(dtype=float)
    pred = (proba >= 0.5).astype(float)
    acc = float((pred == y).mean()) if len(y) else 0.0
    brier = float(np.mean((proba - y) ** 2)) if len(y) else 1.0
    base = float(y.mean()) if len(y) else 0.5
    lift = acc - max(base, 1.0 - base)

    post = test["post_ret_1d"].to_numpy(dtype=float)
    long_m = float(post[proba >= min_confidence].mean()) if (proba >= min_confidence).any() else None
    short_m = float(post[proba <= (1.0 - min_confidence)].mean()) if (proba <= 1.0 - min_confidence).any() else None

    weights = {}
    if scorer.w is not None:
        for c, w in zip(scorer.feature_cols, scorer.w):
            weights[c] = float(w)

    result = EarningsSpecialistResult(
        universe=universe,
        window="2018-01-01→2026-07-10",
        n_events=int(len(df)),
        n_train=int(len(train)),
        n_test=int(len(test)),
        train_frac=train_frac,
        accuracy=acc,
        brier=brier,
        base_rate=base,
        lift=lift,
        long_only_mean_post_1d=long_m,
        short_only_mean_post_1d=short_m,
        feature_weights=weights,
        cut_date=str(pd.Timestamp(cut).date()),
        written_at=datetime.now(timezone.utc).isoformat(),
    )

    if write:
        require_lacie()
        out_dir = PROCESSED / "research"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"earnings_specialist_{universe}.json"
        payload: dict[str, Any] = asdict(result)
        payload["label"] = LABEL_COL
        payload["features"] = list(PRE_EVENT_FEATURES)
        payload["note"] = (
            "Pre-event features only; does not use epsActual/surprise (unknown pre-release). "
            "long/short means are mean post_ret_1d on high/low confidence OOS predictions."
        )
        path.write_text(json.dumps(payload, indent=2, default=str))
        result.path = str(path)

        # OOS scored events for cockpit / later research
        scored = test[
            ["symbol", "earnings_date", "time", "post_ret_1d", LABEL_COL]
            + [c for c in PRE_EVENT_FEATURES if c in test.columns]
        ].copy()
        scored["p_up_post_1d"] = proba
        scored_path = out_dir / f"earnings_specialist_{universe}_oos.parquet"
        scored.to_parquet(scored_path, index=False)
        payload["oos_path"] = str(scored_path)
        path.write_text(json.dumps(payload, indent=2, default=str))

    return result
