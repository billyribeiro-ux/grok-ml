"""End-to-end offline pipeline: data → features → labels → regime → backtest."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

import pandas as pd

from aether.engine.backtest import BacktestResult, PaperBroker
from aether.engine.data_source import MarketDataSource
from aether.engine.labels import add_forward_labels
from aether.engine.mock_data import MockDailySource
from aether.engine.state import estimate_regime_panel
from aether.features.daily import build_daily_features


@dataclass
class PipelineResult:
    features: pd.DataFrame
    labels: pd.DataFrame
    regime: pd.DataFrame
    backtest: BacktestResult


def run_offline_pipeline(
    source: MarketDataSource | None = None,
    symbols: Sequence[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    start_equity_usd: float = 100_000.0,
) -> PipelineResult:
    """
    Fully offline engine flight using MockDailySource by default.
    Swap `source` for a LaCie-backed implementation later — same API.
    """
    src = source or MockDailySource(symbols=list(symbols) if symbols else None)
    panel = src.panel(symbols=symbols, start=start, end=end)
    if panel.empty:
        raise RuntimeError("empty panel from data source")

    features = build_daily_features(panel)
    labels = add_forward_labels(features)
    regime = estimate_regime_panel(features)

    # merge regime onto features for policy convenience
    feat2 = features.merge(
        regime.drop(columns=[], errors="ignore"),
        on=["symbol", "date"],
        how="left",
        suffixes=("", "_reg"),
    )
    # policy reads row features; attach uncertainty etc already in state estimator from row
    # also attach breadth from cross-section simple: fraction symbols above sma20 that day
    feat2 = _attach_cross_section_breadth(feat2)

    broker = PaperBroker(start_equity_usd=start_equity_usd)
    bt = broker.run(feat2.dropna(subset=["ret_1d"]))

    return PipelineResult(features=feat2, labels=labels, regime=regime, backtest=bt)


def _attach_cross_section_breadth(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # drop any prior breadth columns from merges
    drop_cols = [c for c in out.columns if c == "breadth_integrity" or c.startswith("breadth_integrity_")]
    if drop_cols:
        out = out.drop(columns=drop_cols)
    if "px_vs_sma20" not in out.columns:
        out["breadth_integrity"] = 0.5
        return out
    tmp = out[["date", "px_vs_sma20"]].copy()
    tmp["_above"] = (tmp["px_vs_sma20"] > 0).astype(float)
    br = tmp.groupby("date", sort=False)["_above"].transform("mean")
    out["breadth_integrity"] = br.fillna(0.5).values
    return out
