"""Engine tests — fully offline (mock data, no LaCie)."""

from __future__ import annotations

from aether.engine.money import Money
from aether.engine.mock_data import MockDailySource
from aether.engine.pipeline import run_offline_pipeline
from aether.engine.risk import RiskConfig, RiskGovernor
from aether.engine.types import Mode, PortfolioState, Side, Signal
from datetime import date


def test_money_cents():
    m = Money.from_usd(100.505)
    assert isinstance(m.cents, int)
    assert m + Money(50) == Money(m.cents + 50)


def test_mock_source_has_calendar():
    src = MockDailySource(symbols=["SPY", "QQQ"], seed=1)
    assert len(src.calendar()) > 100
    h = src.history("SPY")
    assert set(["open", "high", "low", "close", "volume"]).issubset(h.columns)
    assert h["close"].isna().sum() == 0


def test_risk_stand_down_on_drawdown():
    gov = RiskGovernor(RiskConfig(max_drawdown=0.1))
    port = PortfolioState(
        equity_cents=90_000_00,
        cash_cents=90_000_00,
        positions={},
        peak_equity_cents=100_000_00,
    )
    # drawdown 10% exactly at limit — >=
    sig = Signal(
        symbol="SPY",
        side=Side.LONG,
        mode=Mode.HUNTER,
        as_of=date(2024, 1, 2),
        confidence=0.9,
        expected_edge=0.02,
        stop_pct=0.02,
        target_pct=0.04,
        time_stop_bars=5,
        size_fraction=1.0,
        reason="test",
    )
    d = gov.evaluate(sig, port, 100.0, regime_uncertainty=0.1)
    assert d.allowed is False
    assert d.reason == "max_drawdown_breach"


def test_offline_pipeline_runs():
    src = MockDailySource(symbols=["SPY", "QQQ", "SQQQ", "SH"], seed=7)
    result = run_offline_pipeline(
        source=src,
        start_equity_usd=100_000,
        write_telemetry=True,
        offline_telemetry=True,
    )
    assert len(result.features) > 0
    assert "ret_1d" in result.features.columns
    assert "fwd_ret_5d" in result.labels.columns
    assert result.backtest.final_equity_cents > 0
    assert "n_stand_down" in result.backtest.stats
    assert result.backtest.stats["n_signals"] > 0
    assert result.calibration.get("brier") is not None
    assert result.train_rows > 0 and result.test_rows > 0
    assert result.telemetry_path is not None
    assert result.telemetry_path.exists()
