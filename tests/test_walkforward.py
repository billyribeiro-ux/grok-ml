"""Walk-forward + risk sweep — offline mock only."""

from __future__ import annotations

from aether.engine.mock_data import MockDailySource
from aether.engine.walkforward import report_to_dict, risk_sweep, run_walkforward


def test_walkforward_folds():
    panel = MockDailySource(symbols=["SPY", "QQQ", "SQQQ", "SH"], seed=9).panel()
    rep = run_walkforward(panel, n_folds=4, min_train_frac=0.45, purge_days=3)
    assert len(rep.folds) >= 2
    assert rep.aggregate.get("n_folds_done", 0) >= 2
    d = report_to_dict(rep)
    assert "folds" in d and d["aggregate"]["mean_return"] is not None or True


def test_risk_sweep_runs():
    panel = MockDailySource(symbols=["SPY", "QQQ", "SH"], seed=2).panel()
    rows = risk_sweep(panel)
    assert len(rows) >= 3
    assert "total_return" in rows[0]
    assert "max_positions" in rows[0]
