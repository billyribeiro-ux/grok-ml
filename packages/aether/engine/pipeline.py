"""End-to-end offline pipeline: data → features → labels → scorer → backtest → telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from aether.engine.backtest import BacktestResult, PaperBroker
from aether.engine.calibration import reliability_table
from aether.engine.data_source import MarketDataSource
from aether.engine.labels import add_forward_labels
from aether.engine.mock_data import MockDailySource
from aether.engine.risk import RiskConfig, RiskGovernor
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
    scorer: LogisticScorer | None = None
    cut_date: object | None = None


def run_offline_pipeline(
    source: MarketDataSource | None = None,
    symbols: Sequence[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    start_equity_usd: float = 100_000.0,
    train_frac: float = 0.7,
    purge_days: int = 5,
    write_telemetry: bool = True,
    offline_telemetry: bool = False,
    flight_name: str = "offline_flight",
    label_col: str = "y_up_5d",
    risk: RiskConfig | None = None,
    promote_latest: bool = True,
) -> PipelineResult:
    """
    Fully offline engine flight using MockDailySource by default.

    Walk-forward: train logistic scorer on first train_frac dates, optional
    purge gap (in calendar unique dates) before OOS trade window to reduce
    label leakage near the cut.
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
    features = features[[c for c in features.columns if not c.endswith("_dup")]]
    # Optional Session B TTM fundamentals (static freeze; NaN if missing)
    try:
        from aether.loaders.fundamentals import attach_static_fundamentals

        features = attach_static_fundamentals(
            features,
            symbols=list(symbols) if symbols is not None else None,
        )
    except Exception:
        pass

    labels = add_forward_labels(features)
    if label_col not in labels.columns:
        raise RuntimeError(f"label column missing: {label_col}")
    labeled = labels.dropna(subset=[label_col, "ret_1d"]).copy()

    dates = sorted(labeled["date"].unique())
    if len(dates) < 30:
        raise RuntimeError("not enough labeled dates")

    cut_idx = int(len(dates) * train_frac)
    cut_idx = min(max(cut_idx, 10), len(dates) - 5)
    cut = dates[cut_idx]
    # purge: drop last purge_days of train labels that leak into OOS horizon
    purge = max(0, int(purge_days))
    train_end_idx = max(0, cut_idx - purge)
    train_end = dates[train_end_idx] if train_end_idx < len(dates) else cut

    train = labeled[labeled["date"] < train_end]
    test = labeled[labeled["date"] >= cut]

    scorer = LogisticScorer(label_col=label_col).fit(train)
    test_scored = scorer.score_frame(test)

    cal = reliability_table(
        test_scored[label_col].to_numpy(),
        test_scored["p_up"].to_numpy(),
    )
    calibration = {"n": cal.n, "brier": cal.brier, "bins": cal.bins}

    policy = ScoredPolicy(scorer=scorer)
    risk_cfg = risk or RiskConfig()
    broker = PaperBroker(
        start_equity_usd=start_equity_usd,
        policy=policy,
        risk=RiskGovernor(risk_cfg),
    )
    test_feat = features[features["date"] >= cut].dropna(subset=["ret_1d"])
    test_feat = test_feat.merge(
        test_scored[["symbol", "date", "p_up"]],
        on=["symbol", "date"],
        how="left",
    )
    bt = broker.run(test_feat)

    # daily regime snapshot for cockpit (median across symbols)
    regime_snap = _regime_daily_snapshot(features[features["date"] >= cut])

    model = scorer.export_model()
    _maybe_write_model_export(model, flight_name=flight_name, offline=offline_telemetry)
    tel_path = None
    if write_telemetry:
        src_name = type(src).__name__
        sym_list = list(symbols) if symbols else src.symbols()
        oos_feat = test_feat.copy()
        tel_path = flight_from_backtest(
            bt,
            name=flight_name,
            source=src_name,
            symbols=sym_list,
            offline=offline_telemetry,
            features=oos_feat,
            calibration=calibration,
            model=model,
            promote_latest=promote_latest,
            extra={
                "train_frac": train_frac,
                "purge_days": purge,
                "cut_date": str(cut),
                "train_end_date": str(train_end),
                "label_col": label_col,
                "calibration_brier": cal.brier,
                "calibration_n": int(cal.n),
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "start_equity_usd": start_equity_usd,
                "n_feature_rows": int(len(features)),
                "n_oos_feature_rows": int(len(oos_feat)),
                "n_unique_dates": int(len(dates)),
                "regime_daily": regime_snap,
                "risk": {
                    "max_positions": risk_cfg.max_positions,
                    "max_risk_per_trade": risk_cfg.max_risk_per_trade,
                    "min_confidence": risk_cfg.min_confidence,
                    "max_drawdown": risk_cfg.max_drawdown,
                    "max_day_loss": risk_cfg.max_day_loss,
                },
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
        scorer=scorer,
        cut_date=cut,
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


def _maybe_write_model_export(
    model: dict,
    *,
    flight_name: str,
    offline: bool,
) -> Path | None:
    """Write scorer export next to models/ for audit (LaCie preferred)."""
    import json
    from datetime import datetime, timezone

    from aether.paths import LACIE_ROOT

    try:
        if offline or not LACIE_ROOT.exists():
            root = Path(__file__).resolve().parents[3] / ".aether" / "models"
        else:
            root = LACIE_ROOT / "data" / "models" / "exports"
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = root / f"{flight_name}_{stamp}.json"
        payload = {
            "flight_name": flight_name,
            "written_at": datetime.now(timezone.utc).isoformat(),
            "model": model,
        }
        path.write_text(json.dumps(payload, indent=2, default=str))
        (root / "latest_model.json").write_text(json.dumps(payload, indent=2, default=str))
        return path
    except Exception:
        return None


def _regime_daily_snapshot(df: pd.DataFrame, max_points: int = 400) -> list[dict]:
    """Cross-section median regime axes per day for cockpit strip."""
    if df.empty:
        return []
    cols = [c for c in ("trend_energy", "breadth_integrity", "vol_regime", "uncertainty") if c in df.columns]
    if not cols or "date" not in df.columns:
        return []
    g = df.groupby("date", sort=True)[cols].median().reset_index()
    if len(g) > max_points:
        idx = np.linspace(0, len(g) - 1, max_points).round().astype(int)
        g = g.iloc[sorted(set(idx))]
    rows = []
    for r in g.itertuples(index=False):
        item = {"date": str(getattr(r, "date"))[:10]}
        for c in cols:
            v = getattr(r, c, None)
            if v is not None and pd.notna(v):
                item[c] = round(float(v), 4)
        rows.append(item)
    return rows
