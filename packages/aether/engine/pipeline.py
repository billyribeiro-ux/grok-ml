"""End-to-end offline pipeline: data → features → labels → scorer → backtest → telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

import pandas as pd

from aether.engine.backtest import BacktestResult, PaperBroker
from aether.engine.calibration import reliability_table
from aether.engine.data_source import MarketDataSource
from aether.engine.labels import add_forward_labels
from aether.engine.mock_data import MockDailySource
from aether.engine.scored_policy import ScoredPolicy
from aether.engine.scorer import LogisticScorer
from aether.engine.state import estimate_regime_panel
from aether.engine.telemetry import flight_from_backtest
from aether.features.daily import build_daily_features


@dataclass
class PipelineResult:
    features: pd.DataFrame
    labels: pd.DataFrame
    regime: pd.DataFrame
    backtest: BacktestResult
    calibration: dict
    telemetry_path: Path | None
    train_rows: int
    test_rows: int


def run_offline_pipeline(
    source: MarketDataSource | None = None,
    symbols: Sequence[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    start_equity_usd: float = 100_000.0,
    train_frac: float = 0.7,
    write_telemetry: bool = True,
    offline_telemetry: bool = False,
    flight_name: str = "offline_flight",
) -> PipelineResult:
    """
    Fully offline engine flight using MockDailySource by default.
    Walk-forward: train logistic scorer on first train_frac dates, trade after.
    """
    src = source or MockDailySource(symbols=list(symbols) if symbols else None)
    panel = src.panel(symbols=symbols, start=start, end=end)
    if panel.empty:
        raise RuntimeError("empty panel from data source")

    features = build_daily_features(panel)
    features = _attach_cross_section_breadth(features)
    features = features.merge(
        estimate_regime_panel(features),
        on=["symbol", "date"],
        how="left",
        suffixes=("", "_dup"),
    )
    # clean dup columns
    features = features[[c for c in features.columns if not c.endswith("_dup")]]

    labels = add_forward_labels(features)
    labeled = labels.dropna(subset=["y_up_5d", "ret_1d"]).copy()

    dates = sorted(labeled["date"].unique())
    cut = dates[int(len(dates) * train_frac)] if dates else None
    if cut is None:
        raise RuntimeError("not enough labeled rows")

    train = labeled[labeled["date"] < cut]
    test = labeled[labeled["date"] >= cut]

    scorer = LogisticScorer(label_col="y_up_5d").fit(train)
    test_scored = scorer.score_frame(test)

    # calibration on test
    cal = reliability_table(
        test_scored["y_up_5d"].to_numpy(),
        test_scored["p_up"].to_numpy(),
    )
    calibration = {"n": cal.n, "brier": cal.brier, "bins": cal.bins}

    # backtest only on test window with scored policy
    policy = ScoredPolicy(scorer=scorer)
    broker = PaperBroker(start_equity_usd=start_equity_usd, policy=policy)
    # need full feature rows for test dates including regime cols
    test_feat = features[features["date"] >= cut].dropna(subset=["ret_1d"])
    # attach p_up for telemetry later
    test_feat = test_feat.merge(
        test_scored[["symbol", "date", "p_up"]],
        on=["symbol", "date"],
        how="left",
    )
    bt = broker.run(test_feat)

    tel_path = None
    if write_telemetry:
        src_name = type(src).__name__
        tel_path = flight_from_backtest(
            bt,
            name=flight_name,
            source=src_name,
            symbols=list(symbols) if symbols else src.symbols(),
            offline=offline_telemetry,
            extra={
                "train_frac": train_frac,
                "cut_date": str(cut),
                "calibration_brier": cal.brier,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
            },
        )

    return PipelineResult(
        features=features,
        labels=labels,
        regime=estimate_regime_panel(features),
        backtest=bt,
        calibration=calibration,
        telemetry_path=tel_path,
        train_rows=int(len(train)),
        test_rows=int(len(test)),
    )


def _attach_cross_section_breadth(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
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
