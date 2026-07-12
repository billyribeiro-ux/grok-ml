"""
Earnings specialists for **index constituents** (SP500 / IWM / NASDAQ).

Modes:
  post1d — reaction after the print (features known pre-release, no epsActual)
  pre8   — buy-the-rumor / sell-the-news:
           enter ~8 sessions before earnings, exit T-1 (before the news).
           Features known at T-8 entry only (no leak of the 8d run-up itself).

Local-only. LaCie event tables. No invented rows.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import numpy as np
import pandas as pd

from aether.engine.scorer import LogisticScorer
from aether.paths import PROCESSED, require_lacie

EVENTS_DIR = PROCESSED / "research" / "earnings_events"

Mode = Literal["post1d", "pre8"]

# post-print: features known before / without actuals
POST_FEATURES = (
    "pre_ret_1d",
    "pre_ret_3d",
    "pre_ret_5d",
    "pre_ret_8d",
    "vol_spike_8",
    "is_bmo",
    "is_amc",
    "has_eps_estimate",
    "eps_estimated_z",
    "last_eps_surprise_pct",
)

# buy-rumor at T-8: only history through entry
PRE8_FEATURES = (
    "mom_20_at_t8",
    "mom_5_at_t8",
    "ret_1_at_t8",
    "trail_vol_20",
    "is_bmo",
    "is_amc",
    "has_eps_estimate",
    "eps_estimated_z",
    "last_eps_surprise_pct",
)


@dataclass
class EarningsSpecialistResult:
    universe: str
    mode: str
    strategy: str
    window: str
    n_events: int
    n_train: int
    n_test: int
    train_frac: float
    accuracy: float
    brier: float
    base_rate: float
    lift: float
    long_mean_pnl: float | None
    short_mean_pnl: float | None
    mean_vol_spike_8_oos: float | None
    feature_weights: dict[str, float]
    cut_date: str
    written_at: str
    path: str | None = None


def load_event_table(universe: str = "sp500") -> pd.DataFrame:
    require_lacie()
    path = EVENTS_DIR / f"{universe}_2018_20260710.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"earnings event table missing: {path} — run scripts/build_earnings_event_tables.py"
        )
    df = pd.read_parquet(path)
    df["earnings_date"] = pd.to_datetime(df["earnings_date"]).dt.normalize()
    return df.sort_values(["earnings_date", "symbol"]).reset_index(drop=True)


def prepare_frame(events: pd.DataFrame, mode: Mode) -> tuple[pd.DataFrame, str, tuple[str, ...]]:
    """
    Returns (frame, label_col, feature_cols).
    Drops rows missing the mode's PnL label.
    """
    df = events.copy()
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
        df["eps_estimated_raw"] = est
    else:
        df["has_eps_estimate"] = 0.0
        df["eps_estimated_raw"] = np.nan

    if "last_eps_surprise_pct" not in df.columns:
        df["last_eps_surprise_pct"] = 0.0
    else:
        df["last_eps_surprise_pct"] = (
            pd.to_numeric(df["last_eps_surprise_pct"], errors="coerce").fillna(0.0)
        )

    # Winsorize insane returns (bad prints / splits) — keep honest rows, drop junk tails
    MAX_ABS_RET = 0.50  # ±50% 1d/8d move kept for specialist training

    if mode == "post1d":
        label = "y_up_post_1d"
        pnl = "post_ret_1d"
        feats = POST_FEATURES
        if pnl not in df.columns:
            raise ValueError("event table missing post_ret_1d — rebuild event tables")
        df = df.dropna(subset=[pnl]).copy()
        df[pnl] = pd.to_numeric(df[pnl], errors="coerce")
        df = df[df[pnl].abs() <= MAX_ABS_RET].copy()
        df[label] = (df[pnl].astype(float) > 0).astype(float)
        df["pnl"] = df[pnl].astype(float)
    elif mode == "pre8":
        label = "y_up_pre8"
        pnl = "pre_ret_8d"
        feats = PRE8_FEATURES
        if pnl not in df.columns:
            raise ValueError(
                "event table missing pre_ret_8d — rebuild with scripts/build_earnings_event_tables.py"
            )
        # need entry features too
        need = ["mom_20_at_t8", "mom_5_at_t8", "ret_1_at_t8", "trail_vol_20"]
        for c in need:
            if c not in df.columns:
                df[c] = np.nan
        df = df.dropna(subset=[pnl]).copy()
        df[pnl] = pd.to_numeric(df[pnl], errors="coerce")
        df = df[df[pnl].abs() <= MAX_ABS_RET].copy()
        df[label] = (df[pnl].astype(float) > 0).astype(float)
        df["pnl"] = df[pnl].astype(float)
    else:
        raise ValueError(f"unknown mode {mode}")

    return df, label, feats


def _attach_train_z(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tr, te = train.copy(), test.copy()
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
    mode: Mode = "post1d",
    train_frac: float = 0.7,
    min_confidence: float = 0.55,
    write: bool = True,
) -> EarningsSpecialistResult:
    events = load_event_table(universe)
    df, label_col, feature_cols = prepare_frame(events, mode)
    if len(df) < 100:
        raise RuntimeError(f"not enough labeled events for {universe}/{mode}: {len(df)}")

    dates = sorted(df["earnings_date"].unique())
    cut_idx = int(len(dates) * train_frac)
    cut_idx = min(max(cut_idx, 5), len(dates) - 5)
    cut = dates[cut_idx]

    train = df[df["earnings_date"] < cut].copy()
    test = df[df["earnings_date"] >= cut].copy()
    train, test = _attach_train_z(train, test)

    for c in feature_cols:
        if c not in train.columns:
            train[c] = 0.0
            test[c] = 0.0
        train[c] = train[c].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        test[c] = test[c].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    scorer = LogisticScorer(
        feature_cols=feature_cols,
        label_col=label_col,
        epochs=120,
        lr=0.08,
        l2=1e-3,
    )
    scorer.fit(train)
    proba = scorer.predict_proba(test)
    y = test[label_col].to_numpy(dtype=float)
    pred = (proba >= 0.5).astype(float)
    acc = float((pred == y).mean()) if len(y) else 0.0
    brier = float(np.mean((proba - y) ** 2)) if len(y) else 1.0
    base = float(y.mean()) if len(y) else 0.5
    lift = acc - max(base, 1.0 - base)

    pnl = test["pnl"].to_numpy(dtype=float)
    long_m = float(pnl[proba >= min_confidence].mean()) if (proba >= min_confidence).any() else None
    short_m = (
        float(pnl[proba <= (1.0 - min_confidence)].mean())
        if (proba <= 1.0 - min_confidence).any()
        else None
    )

    vol_spike_mean = None
    if "vol_spike_8" in test.columns:
        vs = pd.to_numeric(test["vol_spike_8"], errors="coerce")
        if vs.notna().any():
            vol_spike_mean = float(vs.mean())

    weights = {}
    if scorer.w is not None:
        for c, w in zip(scorer.feature_cols, scorer.w):
            weights[c] = float(w)

    strategy = (
        "buy_rumor_sell_news_t8_to_t1"
        if mode == "pre8"
        else "post_print_direction_1d"
    )

    result = EarningsSpecialistResult(
        universe=universe,
        mode=mode,
        strategy=strategy,
        window="2018-01-01→2026-07-10",
        n_events=int(len(df)),
        n_train=int(len(train)),
        n_test=int(len(test)),
        train_frac=train_frac,
        accuracy=acc,
        brier=brier,
        base_rate=base,
        lift=lift,
        long_mean_pnl=long_m,
        short_mean_pnl=short_m,
        mean_vol_spike_8_oos=vol_spike_mean,
        feature_weights=weights,
        cut_date=str(pd.Timestamp(cut).date()),
        written_at=datetime.now(timezone.utc).isoformat(),
    )

    if write:
        require_lacie()
        out_dir = PROCESSED / "research"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"earnings_specialist_{universe}_{mode}.json"
        # also write legacy name for post1d so cockpit keeps working
        payload: dict[str, Any] = asdict(result)
        payload["label"] = label_col
        payload["features"] = list(feature_cols)
        payload["long_only_mean_post_1d"] = long_m if mode == "post1d" else None
        payload["short_only_mean_post_1d"] = short_m if mode == "post1d" else None
        payload["long_only_mean_pre8"] = long_m if mode == "pre8" else None
        payload["short_only_mean_pre8"] = short_m if mode == "pre8" else None
        payload["note"] = (
            "Index constituents only. pre8 = enter T-8 exit T-1 (sell before news). "
            "Features at entry exclude the 8d run-up itself (no label leak)."
            if mode == "pre8"
            else "Pre-release features only; no epsActual."
        )
        path.write_text(json.dumps(payload, indent=2, default=str))
        if mode == "post1d":
            (out_dir / f"earnings_specialist_{universe}.json").write_text(
                json.dumps(payload, indent=2, default=str)
            )
        result.path = str(path)

        scored = test[
            ["symbol", "earnings_date", "time", "pnl", label_col]
            + [c for c in feature_cols if c in test.columns]
        ].copy()
        if "vol_spike_8" in test.columns:
            scored["vol_spike_8"] = test["vol_spike_8"].values
        if "pre_ret_8d" in test.columns:
            scored["pre_ret_8d"] = test["pre_ret_8d"].values
        if "sell_news_ret" in test.columns:
            scored["sell_news_ret"] = test["sell_news_ret"].values
        scored["p_up"] = proba
        scored_path = out_dir / f"earnings_specialist_{universe}_{mode}_oos.parquet"
        scored.to_parquet(scored_path, index=False)

    return result
