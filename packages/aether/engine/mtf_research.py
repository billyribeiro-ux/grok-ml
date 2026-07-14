"""
Multi-TF research flight using completed LaCie chart packs.

Supports SP500 / IWM / NASDAQ (whatever non-empty charts exist on disk).
Local only — no network.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from aether.engine.scorer import LogisticScorer
from aether.features.intraday import build_intraday_features
from aether.loaders.mtf_charts import chart_dir, load_chart_panel
from aether.paths import PROCESSED, require_lacie

MTF_FEATURES = (
    "ret_1",
    "ret_5",
    "ret_20",
    "vol_20",
    "rvol_20",
    "range_pct",
    "gap_pct",
    "px_vs_sma20",
    "px_vs_sma50",
    "rsi_14",
    "mom_20",
)

SUPPORTED_UNIVERSES = ("sp500", "iwm", "nasdaq")


@dataclass
class MtfResearchResult:
    universe: str
    interval: str
    n_symbols: int
    n_bars: int
    n_train: int
    n_test: int
    label: str
    accuracy: float
    brier: float
    base_rate: float
    lift: float
    mean_fwd_when_long: float | None
    mean_fwd_when_short: float | None
    cut_date: str
    feature_weights: dict[str, float]
    written_at: str
    path: str | None = None


def _universe_symbols(universe: str, interval: str, limit: int | None = None) -> list[str]:
    require_lacie()
    d = chart_dir(universe, interval)
    if not d.exists():
        raise FileNotFoundError(f"missing {d}")
    syms = sorted(
        p.stem
        for p in d.glob("*.json")
        if not p.name.startswith("._") and p.stat().st_size > 500
    )
    if limit:
        syms = syms[:limit]
    return syms


def run_mtf_research(
    *,
    universe: str = "sp500",
    interval: str = "15min",
    label: str = "y_up_5",
    train_frac: float = 0.7,
    min_confidence: float = 0.55,
    symbol_limit: int | None = None,
    write: bool = True,
) -> MtfResearchResult:
    """
    Time-cut logistic on multi-TF bars for a universe.
    symbol_limit: optional cap for faster research (None = all with files).
    """
    u = universe.strip().lower()
    if u not in SUPPORTED_UNIVERSES:
        raise ValueError(f"universe must be one of {SUPPORTED_UNIVERSES}")
    if label not in ("y_up_1", "y_up_5"):
        raise ValueError("label must be y_up_1 or y_up_5")
    syms = _universe_symbols(u, interval, symbol_limit)
    panel = load_chart_panel(syms, interval=interval, universe=u)
    if panel.empty:
        raise RuntimeError(f"empty multi-TF panel — charts missing on LaCie for {u}/{interval}")
    feats = build_intraday_features(panel)
    if feats.empty or label not in feats.columns:
        raise RuntimeError("failed to build intraday features")

    work = feats.dropna(subset=[label, "ret_1"]).copy()
    for c in MTF_FEATURES:
        if c not in work.columns:
            work[c] = 0.0
        work[c] = work[c].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # subsample if huge (all-bars is truer; cap for RAM)
    if len(work) > 2_000_000:
        work = work.sample(n=2_000_000, random_state=7).sort_values("date")

    dates = sorted(work["date"].unique())
    if len(dates) < 50:
        raise RuntimeError(f"not enough unique bar dates: {len(dates)}")
    cut_idx = int(len(dates) * train_frac)
    cut_idx = min(max(cut_idx, 10), len(dates) - 10)
    cut = dates[cut_idx]
    train = work[work["date"] < cut]
    test = work[work["date"] >= cut]

    scorer = LogisticScorer(
        feature_cols=MTF_FEATURES,
        label_col=label,
        epochs=60,
        lr=0.05,
        l2=1e-3,
    )
    scorer.fit(train)
    proba = scorer.predict_proba(test)
    y = test[label].to_numpy(dtype=float)
    pred = (proba >= 0.5).astype(float)
    acc = float((pred == y).mean())
    brier = float(np.mean((proba - y) ** 2))
    base = float(y.mean())
    lift = acc - max(base, 1.0 - base)

    fwd_col = "fwd_ret_5" if label == "y_up_5" else "fwd_ret_1"
    fwd = (
        test[fwd_col].to_numpy(dtype=float)
        if fwd_col in test.columns
        else np.full(len(test), np.nan)
    )
    long_m = (
        float(np.nanmean(fwd[proba >= min_confidence])) if (proba >= min_confidence).any() else None
    )
    short_m = (
        float(np.nanmean(fwd[proba <= (1.0 - min_confidence)]))
        if (proba <= 1.0 - min_confidence).any()
        else None
    )

    weights: dict[str, float] = {}
    if scorer.w is not None:
        for c, w in zip(scorer.feature_cols, scorer.w):
            weights[c] = float(w)

    result = MtfResearchResult(
        universe=u,
        interval=interval,
        n_symbols=int(work["symbol"].nunique()),
        n_bars=int(len(work)),
        n_train=int(len(train)),
        n_test=int(len(test)),
        label=label,
        accuracy=acc,
        brier=brier,
        base_rate=base,
        lift=lift,
        mean_fwd_when_long=long_m,
        mean_fwd_when_short=short_m,
        cut_date=str(pd.Timestamp(cut)),
        feature_weights=weights,
        written_at=datetime.now(timezone.utc).isoformat(),
    )

    if write:
        require_lacie()
        out = PROCESSED / "research"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"mtf_research_{u}_{interval}_{label}.json"
        payload: dict[str, Any] = asdict(result)
        payload["features"] = list(MTF_FEATURES)
        payload["note"] = (
            f"LaCie {u} multi-TF only; time-cut OOS; no invented bars. "
            "Uses whatever non-empty charts exist on disk."
        )
        path.write_text(json.dumps(payload, indent=2, default=str))
        result.path = str(path)
    return result


def run_sp500_mtf_research(
    *,
    interval: str = "15min",
    label: str = "y_up_5",
    train_frac: float = 0.7,
    min_confidence: float = 0.55,
    symbol_limit: int | None = None,
    write: bool = True,
) -> MtfResearchResult:
    """Back-compat wrapper — SP500 only."""
    return run_mtf_research(
        universe="sp500",
        interval=interval,
        label=label,
        train_frac=train_frac,
        min_confidence=min_confidence,
        symbol_limit=symbol_limit,
        write=write,
    )
