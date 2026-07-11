"""Core engine types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from aether.engine.money import Money


class Side(str, Enum):
    FLAT = "flat"
    LONG = "long"
    SHORT = "short"  # short via inverse ETF or short equity later


class Mode(str, Enum):
    """Capital allocation mode — STAND_DOWN is a successful action."""

    STAND_DOWN = "stand_down"
    FARMER = "farmer"  # mean-revert / range
    HUNTER = "hunter"  # directional / break
    SCANNER = "scanner"
    HEDGE = "hedge"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    ts: datetime  # bar end time / session date as datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float | None = None

    @property
    def px(self) -> float:
        return float(self.adj_close if self.adj_close is not None else self.close)


@dataclass(frozen=True, slots=True)
class RegimeState:
    """Latent market state axes + uncertainty (0–1 higher = less sure)."""

    as_of: date
    trend_energy: float  # -1..+1
    breadth_integrity: float  # 0..1
    vol_regime: float  # 0 calm .. 1 extreme
    liquidity_stress: float  # 0..1
    corr_dispersion: float  # higher = more dispersion (risk-on dispersion)
    uncertainty: float  # 0..1
    raw: dict[str, float] = field(default_factory=dict)

    def allow_risk(self, max_uncertainty: float = 0.75) -> bool:
        return self.uncertainty <= max_uncertainty


@dataclass(frozen=True, slots=True)
class Signal:
    """Machine decision candidate — may still be rejected by risk."""

    symbol: str
    side: Side
    mode: Mode
    as_of: date
    confidence: float  # calibrated probability-ish 0..1
    expected_edge: float  # expected return after costs (fraction)
    stop_pct: float
    target_pct: float
    time_stop_bars: int
    size_fraction: float  # of equity risk budget 0..1
    reason: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    side: Side
    qty: int  # whole shares
    entry_px: float
    entry_date: date
    stop_px: float
    target_px: float
    bars_held: int = 0
    mode: Mode = Mode.HUNTER


@dataclass
class PortfolioState:
    equity_cents: int
    cash_cents: int
    positions: dict[str, Position]
    day_pnl_cents: int = 0
    peak_equity_cents: int = 0

    @property
    def equity(self) -> Money:
        return Money(self.equity_cents)

    @property
    def drawdown(self) -> float:
        if self.peak_equity_cents <= 0:
            return 0.0
        return max(0.0, 1.0 - self.equity_cents / self.peak_equity_cents)
