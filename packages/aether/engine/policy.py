"""Hierarchical policy — mode router + signal inventor (F1 baseline)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from aether.engine.execution import CostModel
from aether.engine.state import estimate_regime_from_features
from aether.engine.types import Mode, RegimeState, Side, Signal


class ModeRouter:
    """Map regime → mode. STAND_DOWN is the default success path."""

    def __init__(self, max_uncertainty: float = 0.72, storm_vol: float = 0.75) -> None:
        self.max_uncertainty = max_uncertainty
        self.storm_vol = storm_vol

    def route(self, state: RegimeState) -> Mode:
        if state.uncertainty >= self.max_uncertainty:
            return Mode.STAND_DOWN
        if state.vol_regime >= self.storm_vol or state.liquidity_stress >= 0.85:
            return Mode.HEDGE if abs(state.trend_energy) > 0.2 else Mode.STAND_DOWN
        if abs(state.trend_energy) >= 0.35 and state.breadth_integrity >= 0.45:
            return Mode.HUNTER
        if state.vol_regime < 0.45 and abs(state.trend_energy) < 0.25:
            return Mode.FARMER
        return Mode.STAND_DOWN


class BaselinePolicy:
    """
    Simple, auditable policy on daily features.
    Machine invents stop/target/size from features; risk may still reject.
    """

    def __init__(
        self,
        costs: CostModel | None = None,
        router: ModeRouter | None = None,
    ) -> None:
        self.costs = costs or CostModel()
        self.router = router or ModeRouter()

    def decide_row(self, row: pd.Series, symbol: str | None = None) -> Signal | None:
        sym = symbol or str(row.get("symbol", ""))
        as_of = pd.Timestamp(row["date"]).date()
        state = estimate_regime_from_features(row, as_of=as_of)
        mode = self.router.route(state)

        if mode == Mode.STAND_DOWN:
            return Signal(
                symbol=sym,
                side=Side.FLAT,
                mode=Mode.STAND_DOWN,
                as_of=as_of,
                confidence=1.0 - state.uncertainty,
                expected_edge=0.0,
                stop_pct=0.0,
                target_pct=0.0,
                time_stop_bars=0,
                size_fraction=0.0,
                reason="stand_down",
                meta={"uncertainty": state.uncertainty, "vol_regime": state.vol_regime},
            )

        ret5 = float(row.get("ret_5d") or 0.0)
        rsi = float(row.get("rsi_14") or 50.0)
        px_sma = float(row.get("px_vs_sma20") or 0.0)
        atr_pct = float(row.get("atr_pct") or 0.02)
        if np.isnan(atr_pct) or atr_pct <= 0:
            atr_pct = 0.02

        side = Side.FLAT
        raw_edge = 0.0
        conf = 0.5
        reason = "no_setup"

        if mode == Mode.HUNTER:
            # trend continuation with stack
            stack = float(row.get("trend_stack") or 0.0)
            if stack >= 2 and ret5 > 0 and px_sma > 0:
                side = Side.LONG
                raw_edge = min(0.02, abs(ret5) * 0.5)
                conf = 0.55 + min(0.25, stack * 0.08)
                reason = "hunter_trend_long"
            elif stack <= 1 and ret5 < 0 and px_sma < 0 and sym in {"SQQQ", "TZA", "SH", "PSQ", "SPXU", "RWM"}:
                # inverse names as short expression when market weak
                side = Side.LONG  # long the inverse ETF
                raw_edge = min(0.02, abs(ret5) * 0.45)
                conf = 0.55 + min(0.2, abs(ret5) * 2)
                reason = "hunter_inverse_long"
        elif mode == Mode.FARMER:
            if rsi < 30 and px_sma < -0.03:
                side = Side.LONG
                raw_edge = 0.008
                conf = 0.58
                reason = "farmer_oversold_bounce"
            elif rsi > 70 and px_sma > 0.03:
                # mean-revert short via inverse if available else skip (F1: skip short stock)
                side = Side.FLAT
                reason = "farmer_overbought_no_short_stock"
        elif mode == Mode.HEDGE:
            if sym in {"SH", "SQQQ", "PSQ"} and state.trend_energy < -0.2:
                side = Side.LONG
                raw_edge = 0.006
                conf = 0.56
                reason = "hedge_inverse"
            else:
                side = Side.FLAT
                reason = "hedge_no_instrument"

        edge = self.costs.edge_after_cost(raw_edge)
        stop = float(np.clip(1.2 * atr_pct, 0.01, 0.08))
        target = float(np.clip(2.0 * stop, 0.015, 0.15))
        # size fraction scales with confidence and inverse uncertainty
        size_frac = float(np.clip(conf * (1.0 - state.uncertainty), 0.15, 1.0))

        return Signal(
            symbol=sym,
            side=side,
            mode=mode,
            as_of=as_of,
            confidence=float(np.clip(conf, 0, 1)),
            expected_edge=float(edge),
            stop_pct=stop,
            target_pct=target,
            time_stop_bars=5 if mode == Mode.FARMER else 10,
            size_fraction=size_frac,
            reason=reason,
            meta={
                "trend_energy": state.trend_energy,
                "vol_regime": state.vol_regime,
                "uncertainty": state.uncertainty,
                "raw_edge": raw_edge,
            },
        )
