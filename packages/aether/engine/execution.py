"""Execution cost model — no mid-price fantasy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostModel:
    """Proportional costs + adverse selection haircut on edge."""

    half_spread_bps: float = 1.0  # per side
    slip_bps: float = 1.5
    adv_participation_penalty_bps: float = 0.0  # set higher for small caps later

    def round_trip_frac(self) -> float:
        # entry + exit
        return 2.0 * (self.half_spread_bps + self.slip_bps + self.adv_participation_penalty_bps) / 1e4

    def apply_entry(self, mid: float, side: str) -> float:
        """side: long|short — pay the spread."""
        hair = (self.half_spread_bps + self.slip_bps) / 1e4
        if side == "long":
            return mid * (1.0 + hair)
        return mid * (1.0 - hair)

    def apply_exit(self, mid: float, side: str) -> float:
        hair = (self.half_spread_bps + self.slip_bps) / 1e4
        # exiting long sells at bid
        if side == "long":
            return mid * (1.0 - hair)
        return mid * (1.0 + hair)

    def edge_after_cost(self, raw_edge: float) -> float:
        return raw_edge - self.round_trip_frac()
