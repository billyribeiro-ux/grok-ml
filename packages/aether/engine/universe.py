"""Universe definitions — code-first; data binding later."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Universe:
    name: str
    symbols: tuple[str, ...]


CORE_LONGS = Universe(
    "core_longs",
    ("AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO", "SPY", "QQQ", "IWM"),
)

CORE_INVERSES = Universe(
    "core_inverses",
    ("SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA", "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS"),
)

F1_TRADEABLE = Universe(
    "f1_tradeable",
    CORE_LONGS.symbols + ("SQQQ", "TZA", "SH", "PSQ", "RWM", "SPXU"),
)

SECTOR_SPDR = Universe(
    "sector_spdr",
    ("XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLK", "XLU"),
)


def all_named() -> dict[str, Universe]:
    return {
        CORE_LONGS.name: CORE_LONGS,
        CORE_INVERSES.name: CORE_INVERSES,
        F1_TRADEABLE.name: F1_TRADEABLE,
        SECTOR_SPDR.name: SECTOR_SPDR,
    }
