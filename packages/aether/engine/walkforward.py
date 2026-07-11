"""Multi-fold purged walk-forward research — honest OOS folds only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import pandas as pd

from aether.engine.backtest import PaperBroker
from aether.engine.calibration import reliability_table
from aether.engine.labels import add_forward_labels
from aether.engine.pipeline import _attach_cross_section_breadth
from aether.engine.risk import RiskConfig, RiskGovernor
from aether.engine.scored_policy import ScoredPolicy
from aether.engine.scorer import LogisticScorer
from aether.engine.state import estimate_regime_panel
from aether.features.daily import build_daily_features


@dataclass
class FoldResult:
    fold: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_rows: int
    test_rows: int
    brier: float | None
    stats: dict[str, Any] = field(default_factory=dict)
    top_weights: list[dict] = field(default_factory=list)


@dataclass
class WalkForwardReport:
    n_folds: int
    purge_days: int
    label_col: str
    symbols: list[str]
    folds: list[FoldResult]
    aggregate: dict[str, Any]


def run_walkforward(
    panel: pd.DataFrame,
    *,
    n_folds: int = 5,
    min_train_frac: float = 0.4,
    purge_days: int = 5,
    label_col: str = "y_up_5d",
    start_equity_usd: float = 100_000.0,
    risk: RiskConfig | None = None,
    symbols: Sequence[str] | None = None,
) -> WalkForwardReport:
    """
    Expanding-window walk-forward:
    - train on [0, cut_i), purge last purge_days of train dates
    - test on [cut_i, cut_{i+1}) for intermediate folds; last fold to end
    """
    if panel.empty:
        raise RuntimeError("empty panel")

    features = build_daily_features(panel)
    features = _attach_cross_section_breadth(features)
    features = features.merge(
        estimate_regime_panel(features),
        on=["symbol", "date"],
        how="left",
        suffixes=("", "_dup"),
    )
    features = features[[c for c in features.columns if not c.endswith("_dup")]]
    labels = add_forward_labels(features)
    if label_col not in labels.columns:
        raise RuntimeError(f"missing label {label_col}")
    labeled = labels.dropna(subset=[label_col, "ret_1d"]).copy()
    dates = sorted(labeled["date"].unique())
    if len(dates) < 80:
        raise RuntimeError(f"not enough dates for walk-forward: {len(dates)}")

    n_folds = max(2, int(n_folds))
    # cuts after min_train_frac of calendar, then equal OOS slices
    train0 = int(len(dates) * min_train_frac)
    train0 = max(train0, 40)
    remaining = len(dates) - train0
    if remaining < n_folds * 5:
        n_folds = max(2, remaining // 5)
    oos_len = remaining // n_folds
    cuts = [train0 + i * oos_len for i in range(n_folds)]
    cuts.append(len(dates))  # end

    risk_cfg = risk or RiskConfig()
    folds: list[FoldResult] = []
    rets: list[float] = []
    briers: list[float] = []
    sharpes: list[float] = []
    dds: list[float] = []

    for i in range(n_folds):
        cut_i = cuts[i]
        cut_j = cuts[i + 1]
        if cut_j <= cut_i + 2:
            continue
        train_end_idx = max(0, cut_i - purge_days)
        train_end = dates[train_end_idx]
        cut = dates[cut_i]
        test_end = dates[cut_j - 1]

        train = labeled[labeled["date"] < train_end]
        test = labeled[(labeled["date"] >= cut) & (labeled["date"] <= test_end)]
        if len(train) < 50 or len(test) < 20:
            continue

        scorer = LogisticScorer(label_col=label_col).fit(train)
        test_scored = scorer.score_frame(test)
        cal = reliability_table(
            test_scored[label_col].to_numpy(),
            test_scored["p_up"].to_numpy(),
        )
        policy = ScoredPolicy(scorer=scorer)
        broker = PaperBroker(
            start_equity_usd=start_equity_usd,
            policy=policy,
            risk=RiskGovernor(risk_cfg),
        )
        test_feat = features[
            (features["date"] >= cut) & (features["date"] <= test_end)
        ].dropna(subset=["ret_1d"])
        test_feat = test_feat.merge(
            test_scored[["symbol", "date", "p_up"]],
            on=["symbol", "date"],
            how="left",
        )
        bt = broker.run(test_feat)
        fr = FoldResult(
            fold=i + 1,
            train_start=str(dates[0])[:10],
            train_end=str(train_end)[:10],
            test_start=str(cut)[:10],
            test_end=str(test_end)[:10],
            train_rows=int(len(train)),
            test_rows=int(len(test)),
            brier=float(cal.brier),
            stats=dict(bt.stats),
            top_weights=scorer.coefficient_table()[:8],
        )
        folds.append(fr)
        if bt.stats.get("total_return") is not None:
            rets.append(float(bt.stats["total_return"]))
        if cal.brier is not None:
            briers.append(float(cal.brier))
        if bt.stats.get("sharpe_like") is not None:
            sharpes.append(float(bt.stats["sharpe_like"]))
        if bt.stats.get("max_drawdown") is not None:
            dds.append(float(bt.stats["max_drawdown"]))

    agg = {
        "n_folds_done": len(folds),
        "mean_return": float(np.mean(rets)) if rets else None,
        "median_return": float(np.median(rets)) if rets else None,
        "std_return": float(np.std(rets)) if len(rets) > 1 else 0.0,
        "mean_sharpe": float(np.mean(sharpes)) if sharpes else None,
        "mean_brier": float(np.mean(briers)) if briers else None,
        "mean_max_dd": float(np.mean(dds)) if dds else None,
        "worst_return": float(np.min(rets)) if rets else None,
        "best_return": float(np.max(rets)) if rets else None,
        "pct_positive_folds": float(np.mean([r > 0 for r in rets])) if rets else None,
    }
    syms = list(symbols) if symbols else sorted(panel["symbol"].unique().tolist())
    return WalkForwardReport(
        n_folds=n_folds,
        purge_days=purge_days,
        label_col=label_col,
        symbols=syms,
        folds=folds,
        aggregate=agg,
    )


def risk_sweep(
    panel: pd.DataFrame,
    *,
    configs: list[RiskConfig] | None = None,
    train_frac: float = 0.7,
    purge_days: int = 5,
    label_col: str = "y_up_5d",
    start_equity_usd: float = 100_000.0,
) -> list[dict[str, Any]]:
    """Single-cut OOS backtest across risk configs (research, not live)."""
    if configs is None:
        configs = [
            RiskConfig(max_positions=3, max_risk_per_trade=0.008),
            RiskConfig(max_positions=5, max_risk_per_trade=0.01),
            RiskConfig(max_positions=8, max_risk_per_trade=0.01),
            RiskConfig(max_positions=10, max_risk_per_trade=0.012),
            RiskConfig(max_positions=5, min_confidence=0.58, max_risk_per_trade=0.01),
            RiskConfig(max_positions=5, min_confidence=0.52, max_risk_per_trade=0.01),
            RiskConfig(max_positions=8, max_drawdown=0.12, max_day_loss=0.025),
        ]

    features = build_daily_features(panel)
    features = _attach_cross_section_breadth(features)
    features = features.merge(
        estimate_regime_panel(features),
        on=["symbol", "date"],
        how="left",
        suffixes=("", "_dup"),
    )
    features = features[[c for c in features.columns if not c.endswith("_dup")]]
    labels = add_forward_labels(features)
    labeled = labels.dropna(subset=[label_col, "ret_1d"]).copy()
    dates = sorted(labeled["date"].unique())
    cut_idx = int(len(dates) * train_frac)
    cut_idx = min(max(cut_idx, 20), len(dates) - 10)
    train_end = dates[max(0, cut_idx - purge_days)]
    cut = dates[cut_idx]
    train = labeled[labeled["date"] < train_end]
    test = labeled[labeled["date"] >= cut]
    scorer = LogisticScorer(label_col=label_col).fit(train)
    test_scored = scorer.score_frame(test)
    test_feat = features[features["date"] >= cut].dropna(subset=["ret_1d"])
    test_feat = test_feat.merge(
        test_scored[["symbol", "date", "p_up"]],
        on=["symbol", "date"],
        how="left",
    )

    rows: list[dict[str, Any]] = []
    for i, cfg in enumerate(configs):
        policy = ScoredPolicy(scorer=scorer)
        broker = PaperBroker(
            start_equity_usd=start_equity_usd,
            policy=policy,
            risk=RiskGovernor(cfg),
        )
        bt = broker.run(test_feat)
        rows.append(
            {
                "id": i + 1,
                "max_positions": cfg.max_positions,
                "max_risk_per_trade": cfg.max_risk_per_trade,
                "min_confidence": cfg.min_confidence,
                "max_drawdown": cfg.max_drawdown,
                "max_day_loss": cfg.max_day_loss,
                **bt.stats,
            }
        )
    rows.sort(key=lambda r: (r.get("sharpe_like") is None, -(r.get("sharpe_like") or -999)))
    return rows


def report_to_dict(rep: WalkForwardReport) -> dict[str, Any]:
    return {
        "n_folds": rep.n_folds,
        "purge_days": rep.purge_days,
        "label_col": rep.label_col,
        "symbols": rep.symbols,
        "aggregate": rep.aggregate,
        "folds": [
            {
                "fold": f.fold,
                "train_start": f.train_start,
                "train_end": f.train_end,
                "test_start": f.test_start,
                "test_end": f.test_end,
                "train_rows": f.train_rows,
                "test_rows": f.test_rows,
                "brier": f.brier,
                "stats": f.stats,
                "top_weights": f.top_weights,
            }
            for f in rep.folds
        ],
    }
