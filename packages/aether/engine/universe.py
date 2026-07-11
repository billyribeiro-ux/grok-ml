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

# Benchmarks + sectors + liquid inverses — eod_bulk complete for these
RESEARCH_LIQUID = Universe(
    "research_liquid",
    CORE_LONGS.symbols
    + SECTOR_SPDR.symbols
    + ("SQQQ", "TZA", "SH", "PSQ", "RWM", "SPXU", "TQQQ", "UPRO", "UVXY", "VIXY"),
)

MEGA_PLUS_BENCH = Universe(
    "mega_plus_bench",
    ("SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO", "MSFT", "META", "GOOGL"),
)

# Best multi-fold reliability in research (mean sharpe ~1.03, 100% positive folds)
HYBRID_SECTOR_MISSION = Universe(
    "hybrid_sector_mission",
    ("SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "SQQQ", "SH", "AAPL", "NVDA"),
)

MISSION_BEST_RISK = Universe(
    "mission_best_risk",
    ("SPY", "QQQ", "IWM", "SQQQ", "SH", "AAPL", "NVDA"),
)

# Research champion (multifold): hybrid + mega tech, conf 0.58, max_pos 3
HYBRID_PLUS_MEGA = Universe(
    "hybrid_plus_mega",
    (
        "SPY",
        "QQQ",
        "IWM",
        "XLK",
        "XLF",
        "XLE",
        "SQQQ",
        "SH",
        "AAPL",
        "NVDA",
        "MSFT",
        "META",
        "GOOGL",
    ),
)

# Expanded liquid research book (multifold weaker than hybrid; single-cut can look fine)
LIQUID_US_30 = Universe(
    "liquid_us_30",
    (
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "GOOGL",
        "TSLA",
        "NFLX",
        "AMD",
        "AVGO",
        "JPM",
        "XOM",
        "JNJ",
        "UNH",
        "V",
        "MA",
        "SQQQ",
        "TQQQ",
        "SH",
        "PSQ",
        "XLK",
        "XLF",
        "XLE",
        "XLV",
        "XLI",
        "SMH",
    ),
)


def all_named() -> dict[str, Universe]:
    return {
        CORE_LONGS.name: CORE_LONGS,
        CORE_INVERSES.name: CORE_INVERSES,
        F1_TRADEABLE.name: F1_TRADEABLE,
        SECTOR_SPDR.name: SECTOR_SPDR,
        RESEARCH_LIQUID.name: RESEARCH_LIQUID,
        MEGA_PLUS_BENCH.name: MEGA_PLUS_BENCH,
        HYBRID_SECTOR_MISSION.name: HYBRID_SECTOR_MISSION,
        MISSION_BEST_RISK.name: MISSION_BEST_RISK,
        HYBRID_PLUS_MEGA.name: HYBRID_PLUS_MEGA,
        LIQUID_US_30.name: LIQUID_US_30,
    }
