"""LaCie-first paths. Refuse silent local fallbacks for production data."""

from __future__ import annotations

import os
from pathlib import Path

# Primary archive (external drive)
LACIE_ROOT = Path(os.getenv("AETHER_LACIE_ROOT", "/Volumes/LaCie/Aether"))
RAW = LACIE_ROOT / "data" / "raw"
FMP_RAW = RAW / "fmp"
DATABENTO_RAW = RAW / "databento"

# Processed feature store (also on LaCie — not git)
PROCESSED = LACIE_ROOT / "data" / "processed"
FEATURE_STORE = PROCESSED / "feature_store"
INTEGRITY_DIR = PROCESSED / "integrity"

# Important FMP subtrees
EOD_BULK = FMP_RAW / "archive_expiry" / "eod_bulk"
EOD_FRIDAY = FMP_RAW / "eod_2026-07-10"
IWM = FMP_RAW / "iwm_russell2000"
SECTOR_ETFS = FMP_RAW / "sector_etfs"
UNIVERSE = FMP_RAW / "universe"
MARKET_INTERNALS = FMP_RAW / "market_internals"
VIX = FMP_RAW / "vix_internals"

# F1 default core universe (expand later)
F1_CORE_SYMBOLS = (
    "SPY",
    "QQQ",
    "IWM",
    "AAPL",
    "NVDA",
    "TSLA",
    "AMZN",
    "NFLX",
    "CSCO",
    "SQQQ",
    "SPXU",
    "TZA",
    "SH",
    "PSQ",
    "RWM",
)


class LaCieNotMountedError(RuntimeError):
    """Raised when the primary archive volume is missing."""


def require_lacie() -> Path:
    """Return LaCie root or raise. Never invent data paths."""
    if not LACIE_ROOT.exists():
        raise LaCieNotMountedError(
            f"LaCie not mounted at {LACIE_ROOT}. "
            "Mount the drive before running Aether data jobs."
        )
    return LACIE_ROOT


def ensure_processed_dirs() -> None:
    require_lacie()
    FEATURE_STORE.mkdir(parents=True, exist_ok=True)
    INTEGRITY_DIR.mkdir(parents=True, exist_ok=True)
