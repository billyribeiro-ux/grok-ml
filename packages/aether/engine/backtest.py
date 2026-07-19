"""Paper backtest loop — event-driven on daily bars, costs on, STAND_DOWN honored."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from aether.engine.execution import CostModel
from aether.engine.policy import BaselinePolicy
from aether.engine.risk import RiskConfig, RiskGovernor
from aether.engine.types import Mode, PortfolioState, Position, Side, Signal


@dataclass
class Fill:
    date: date
    symbol: str
    side: str  # buy|sell
    qty: int
    px: float
    reason: str


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    fills: list[Fill]
    signals: list[Signal]
    rejections: list[dict]
    final_equity_cents: int
    stats: dict = field(default_factory=dict)


class PaperBroker:
    def __init__(
        self,
        start_equity_usd: float = 100_000.0,
        costs: CostModel | None = None,
        risk: RiskGovernor | None = None,
        policy: BaselinePolicy | None = None,
    ) -> None:
        cents = int(round(start_equity_usd * 100))
        self.portfolio = PortfolioState(
            equity_cents=cents,
            cash_cents=cents,
            positions={},
            peak_equity_cents=cents,
        )
        self.costs = costs or CostModel()
        self.risk = risk or RiskGovernor(RiskConfig())
        self.policy = policy or BaselinePolicy(costs=self.costs)
        self.fills: list[Fill] = []
        self.signals: list[Signal] = []
        self.rejections: list[dict] = []
        self._equity_rows: list[dict] = []

    def run(self, features: pd.DataFrame) -> BacktestResult:
        """
        features: multi-symbol daily feature panel sorted by date.
        On each date: mark positions, check exits, generate signals, maybe enter.
        """
        df = features.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        dates = sorted(df["date"].unique())

        # Signals decided on bar t are executed on bar t+1. Features at t are
        # computed from t's close (features/daily.py), so filling at t's close
        # would mean observing the closing print and transacting at it — not
        # executable. Holding them one bar and filling at the next open is the
        # earliest price genuinely available after the decision.
        pending: list[Signal] = []

        for ts in dates:
            d = pd.Timestamp(ts).date()
            day = df[df["date"] == ts]
            # mark-to-market
            self._mark(day, d)
            self._exits(day, d)

            # --- execute signals decided on the PREVIOUS bar, at this bar's open
            if pending:
                px_by_sym = {}
                for _, row in day.iterrows():
                    if "open" not in row or pd.isna(row["open"]):
                        # Fail loud: silently falling back to close would
                        # reintroduce the same-bar fill this lag exists to remove.
                        raise ValueError(
                            f"{row['symbol']} on {d}: missing 'open'; cannot fill "
                            "a lagged decision without reintroducing same-bar execution"
                        )
                    px_by_sym[row["symbol"]] = float(row["open"])
                for sig in pending:
                    if sig.symbol in self.portfolio.positions:
                        continue
                    px = px_by_sym.get(sig.symbol)
                    if px is None or px <= 0:
                        # Not tradable on the fill bar (halt/delist/gap in data).
                        self.rejections.append(
                            {"date": d.isoformat(), "symbol": sig.symbol, "reason": "not_tradable_on_fill_bar"}
                        )
                        continue
                    unc = float(sig.meta.get("uncertainty", 0.5))
                    decision = self.risk.evaluate(
                        sig, self.portfolio, px, regime_uncertainty=unc
                    )
                    if not decision.allowed:
                        self.rejections.append(
                            {"date": d.isoformat(), "symbol": sig.symbol, "reason": decision.reason}
                        )
                        continue
                    self._enter(sig, decision.size_shares, px, d)
                pending = []

            # --- decide from THIS bar's features; queue for the next bar
            for _, row in day.iterrows():
                sig = self.policy.decide_row(row)
                if sig is None:
                    continue
                self.signals.append(sig)
                if sig.side == Side.FLAT or sig.mode == Mode.STAND_DOWN:
                    continue
                if sig.symbol in self.portfolio.positions:
                    continue
                pending.append(sig)

            self._equity_rows.append(
                {
                    "date": d,
                    "equity_cents": self.portfolio.equity_cents,
                    "cash_cents": self.portfolio.cash_cents,
                    "n_pos": len(self.portfolio.positions),
                    "day_pnl_cents": self.portfolio.day_pnl_cents,
                    "drawdown": self.portfolio.drawdown,
                }
            )
            # reset day pnl accumulator boundary
            self.portfolio.day_pnl_cents = 0

        eq = pd.DataFrame(self._equity_rows)
        stats = _stats(eq, self.fills, self.signals, self.rejections)
        return BacktestResult(
            equity_curve=eq,
            fills=self.fills,
            signals=self.signals,
            rejections=self.rejections,
            final_equity_cents=self.portfolio.equity_cents,
            stats=stats,
        )

    def _mark(self, day: pd.DataFrame, d: date) -> None:
        px_map = {str(r.symbol): float(r.close) for r in day.itertuples()}
        equity = self.portfolio.cash_cents
        for sym, pos in self.portfolio.positions.items():
            px = px_map.get(sym, pos.entry_px)
            equity += int(round(pos.qty * px * 100))
        # positions are frozen dataclass — rebuild with bars_held
        new_pos = {}
        for sym, pos in self.portfolio.positions.items():
            new_pos[sym] = Position(
                symbol=pos.symbol,
                side=pos.side,
                qty=pos.qty,
                entry_px=pos.entry_px,
                entry_date=pos.entry_date,
                stop_px=pos.stop_px,
                target_px=pos.target_px,
                bars_held=pos.bars_held + 1,
                mode=pos.mode,
            )
        self.portfolio.positions = new_pos
        prev = self.portfolio.equity_cents
        self.portfolio.equity_cents = equity
        self.portfolio.day_pnl_cents += equity - prev
        self.portfolio.peak_equity_cents = max(self.portfolio.peak_equity_cents, equity)

    def _exits(self, day: pd.DataFrame, d: date) -> None:
        px_map = {str(r.symbol): float(r.close) for r in day.itertuples()}
        hi_map = {str(r.symbol): float(r.high) for r in day.itertuples()}
        lo_map = {str(r.symbol): float(r.low) for r in day.itertuples()}
        to_close: list[tuple[str, str]] = []
        for sym, pos in list(self.portfolio.positions.items()):
            if sym not in px_map:
                continue
            hi, lo, cl = hi_map[sym], lo_map[sym], px_map[sym]
            reason = None
            if pos.side == Side.LONG:
                if lo <= pos.stop_px:
                    reason = "stop"
                    cl = pos.stop_px
                elif hi >= pos.target_px:
                    reason = "target"
                    cl = pos.target_px
                elif pos.bars_held >= 10:
                    reason = "time_stop"
            if reason:
                to_close.append((sym, reason))
                self._close(sym, cl, d, reason)
        # silence lint
        _ = to_close

    def _enter(self, sig: Signal, shares: int, mid: float, d: date) -> None:
        side = "long" if sig.side == Side.LONG else "short"
        px = self.costs.apply_entry(mid, "long" if sig.side == Side.LONG else "short")
        cost = int(round(shares * px * 100))
        if cost > self.portfolio.cash_cents:
            return
        self.portfolio.cash_cents -= cost
        stop_px = px * (1.0 - sig.stop_pct) if sig.side == Side.LONG else px * (1.0 + sig.stop_pct)
        target_px = px * (1.0 + sig.target_pct) if sig.side == Side.LONG else px * (1.0 - sig.target_pct)
        self.portfolio.positions[sig.symbol] = Position(
            symbol=sig.symbol,
            side=sig.side,
            qty=shares,
            entry_px=px,
            entry_date=d,
            stop_px=stop_px,
            target_px=target_px,
            bars_held=0,
            mode=sig.mode,
        )
        self.fills.append(Fill(d, sig.symbol, "buy", shares, px, sig.reason))

    def _close(self, sym: str, mid: float, d: date, reason: str) -> None:
        pos = self.portfolio.positions.pop(sym, None)
        if pos is None:
            return
        px = self.costs.apply_exit(mid, "long" if pos.side == Side.LONG else "short")
        proceeds = int(round(pos.qty * px * 100))
        self.portfolio.cash_cents += proceeds
        self.fills.append(Fill(d, sym, "sell", pos.qty, px, reason))


def _stats(eq: pd.DataFrame, fills: list[Fill], signals: list[Signal], rejections: list[dict]) -> dict:
    if eq.empty:
        return {}
    e = eq["equity_cents"].astype(float).values
    rets = np.diff(e) / e[:-1]
    rets = rets[np.isfinite(rets)]
    total_ret = e[-1] / e[0] - 1.0 if e[0] else 0.0
    vol = float(np.std(rets) * np.sqrt(252)) if len(rets) else 0.0
    sharpe = float(np.mean(rets) / (np.std(rets) + 1e-12) * np.sqrt(252)) if len(rets) else 0.0
    stand = sum(1 for s in signals if s.mode == Mode.STAND_DOWN)
    actionable = sum(1 for s in signals if s.side != Side.FLAT and s.mode != Mode.STAND_DOWN)
    return {
        "total_return": total_ret,
        "ann_vol": vol,
        "sharpe_like": sharpe,
        "max_drawdown": float(eq["drawdown"].max()) if "drawdown" in eq.columns else None,
        "n_fills": len(fills),
        "n_signals": len(signals),
        "n_stand_down": stand,
        "n_actionable_signals": actionable,
        "n_rejections": len(rejections),
        "final_equity_usd": e[-1] / 100.0,
    }
