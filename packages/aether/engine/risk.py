"""Risk governor — hard laws (thermal limits). Money in cents."""

from __future__ import annotations

from dataclasses import dataclass

from aether.engine.money import Money
from aether.engine.types import PortfolioState, Side, Signal


@dataclass(frozen=True, slots=True)
class RiskConfig:
    max_risk_per_trade: float = 0.01  # 1% equity
    max_day_loss: float = 0.03  # 3%
    max_drawdown: float = 0.15  # 15% from peak
    max_positions: int = 5
    max_gross_exposure: float = 1.0  # 100% of equity notionals
    min_confidence: float = 0.55
    max_uncertainty: float = 0.75
    min_edge_after_cost: float = 0.0005  # 5 bps


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allowed: bool
    reason: str
    size_shares: int = 0
    risk_cents: int = 0


class RiskGovernor:
    def __init__(self, cfg: RiskConfig | None = None) -> None:
        self.cfg = cfg or RiskConfig()

    def evaluate(
        self,
        signal: Signal,
        portfolio: PortfolioState,
        price: float,
        *,
        regime_uncertainty: float,
    ) -> RiskDecision:
        cfg = self.cfg

        if signal.side == Side.FLAT:
            return RiskDecision(False, "flat_signal")

        # integer bps comparison — avoid float edge at exact threshold
        peak = portfolio.peak_equity_cents
        eq = portfolio.equity_cents
        if peak > 0:
            dd_bps = (peak - eq) * 10_000 // peak
            if dd_bps >= int(cfg.max_drawdown * 10_000):
                return RiskDecision(False, "max_drawdown_breach")

        if portfolio.equity_cents > 0:
            day_loss_frac = -portfolio.day_pnl_cents / portfolio.equity_cents
            if day_loss_frac >= cfg.max_day_loss:
                return RiskDecision(False, "max_day_loss_breach")

        if len(portfolio.positions) >= cfg.max_positions and signal.symbol not in portfolio.positions:
            return RiskDecision(False, "max_positions")

        if signal.confidence < cfg.min_confidence:
            return RiskDecision(False, "confidence_below_min")

        if regime_uncertainty > cfg.max_uncertainty:
            return RiskDecision(False, "regime_uncertainty_high")

        if signal.expected_edge < cfg.min_edge_after_cost:
            return RiskDecision(False, "edge_below_cost_floor")

        if price <= 0:
            return RiskDecision(False, "invalid_price")

        # risk capital in cents
        risk_budget = int(portfolio.equity_cents * cfg.max_risk_per_trade * signal.size_fraction)
        if risk_budget <= 0:
            return RiskDecision(False, "zero_risk_budget")

        stop = max(signal.stop_pct, 1e-4)
        # shares so that stop distance * shares ≈ risk_budget
        # risk per share in cents ≈ price * stop * 100
        risk_per_share_cents = max(1, int(round(price * stop * 100)))
        shares = risk_budget // risk_per_share_cents
        if shares <= 0:
            return RiskDecision(False, "shares_round_to_zero")

        notional_cents = int(round(shares * price * 100))
        if notional_cents > int(portfolio.equity_cents * cfg.max_gross_exposure):
            shares = int(portfolio.equity_cents * cfg.max_gross_exposure) // max(
                1, int(round(price * 100))
            )
            if shares <= 0:
                return RiskDecision(False, "gross_exposure_cap")
            notional_cents = int(round(shares * price * 100))

        if notional_cents > portfolio.cash_cents and signal.side == Side.LONG:
            shares = portfolio.cash_cents // max(1, int(round(price * 100)))
            if shares <= 0:
                return RiskDecision(False, "insufficient_cash")

        return RiskDecision(
            True,
            "ok",
            size_shares=shares,
            risk_cents=shares * risk_per_share_cents,
        )
