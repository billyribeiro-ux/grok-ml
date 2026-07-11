"""Policy that blends baseline rules with logistic P(up) when trained."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aether.engine.execution import CostModel
from aether.engine.policy import BaselinePolicy, ModeRouter
from aether.engine.scorer import LogisticScorer
from aether.engine.state import estimate_regime_from_features
from aether.engine.types import Mode, Side, Signal


class ScoredPolicy(BaselinePolicy):
    """
    Uses scorer P(up) to set confidence/edge when available.
    Falls back to baseline rules if scorer untrained.
    """

    def __init__(
        self,
        scorer: LogisticScorer | None = None,
        costs: CostModel | None = None,
        router: ModeRouter | None = None,
        p_long: float = 0.58,
        p_short_inv: float = 0.42,
    ) -> None:
        super().__init__(costs=costs, router=router)
        self.scorer = scorer
        self.p_long = p_long
        self.p_short_inv = p_short_inv

    def decide_row(self, row: pd.Series, symbol: str | None = None) -> Signal | None:
        base = super().decide_row(row, symbol=symbol)
        if base is None or self.scorer is None or self.scorer.w is None:
            return base

        sym = symbol or str(row.get("symbol", ""))
        as_of = pd.Timestamp(row["date"]).date()
        state = estimate_regime_from_features(row, as_of=as_of)
        mode = self.router.route(state)
        if mode == Mode.STAND_DOWN:
            return base

        p = float(self.scorer.predict_proba(pd.DataFrame([row]))[0])
        edge_raw = (p - 0.5) * 0.04  # map to rough edge scale
        edge = self.costs.edge_after_cost(abs(edge_raw))
        atr_pct = float(row.get("atr_pct") or 0.02)
        if np.isnan(atr_pct) or atr_pct <= 0:
            atr_pct = 0.02
        stop = float(np.clip(1.2 * atr_pct, 0.01, 0.08))
        target = float(np.clip(2.0 * stop, 0.015, 0.15))

        inv = {"SQQQ", "TZA", "SH", "PSQ", "RWM", "SPXU"}
        side = Side.FLAT
        reason = "scorer_no_edge"
        conf = max(p, 1.0 - p)

        if p >= self.p_long and mode in (Mode.HUNTER, Mode.FARMER):
            side = Side.LONG
            reason = f"scorer_long_p={p:.3f}"
            conf = p
        elif p <= self.p_short_inv and sym in inv and mode in (Mode.HUNTER, Mode.HEDGE):
            side = Side.LONG  # long inverse
            reason = f"scorer_inverse_p={p:.3f}"
            conf = 1.0 - p

        if side == Side.FLAT:
            # keep baseline if it had a setup
            if base.side != Side.FLAT:
                return base
            return Signal(
                symbol=sym,
                side=Side.FLAT,
                mode=mode,
                as_of=as_of,
                confidence=conf,
                expected_edge=0.0,
                stop_pct=0.0,
                target_pct=0.0,
                time_stop_bars=0,
                size_fraction=0.0,
                reason=reason,
                meta={"p_up": p, "uncertainty": state.uncertainty},
            )

        # size: confidence × (1 − regime uncertainty). Trend-damp A/B (0.15–0.35)
        # cut OOS return more than risk — left off until better regime sizing exists.
        te = float(getattr(state, "trend_energy", 0.0) or 0.0)

        return Signal(
            symbol=sym,
            side=side,
            mode=mode,
            as_of=as_of,
            confidence=float(np.clip(conf, 0, 1)),
            expected_edge=float(edge if side != Side.FLAT else 0.0),
            stop_pct=stop,
            target_pct=target,
            time_stop_bars=5 if mode == Mode.FARMER else 10,
            size_fraction=float(np.clip(conf * (1.0 - state.uncertainty), 0.15, 1.0)),
            reason=reason,
            meta={
                "p_up": p,
                "uncertainty": state.uncertainty,
                "vol_regime": state.vol_regime,
                "trend_energy": te,
            },
        )
