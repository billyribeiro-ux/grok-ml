"""F0 integrity checks — honest inventory of what exists on LaCie."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from aether.paths import (
    DATABENTO_RAW,
    EOD_BULK,
    EOD_FRIDAY,
    FMP_RAW,
    IWM,
    INTEGRITY_DIR,
    LACIE_ROOT,
    SECTOR_ETFS,
    ensure_processed_dirs,
    require_lacie,
)


@dataclass
class IntegrityReport:
    checked_at: str
    lacie_root: str
    lacie_mounted: bool
    eod_bulk_files: int = 0
    eod_bulk_min: str | None = None
    eod_bulk_max: str | None = None
    eod_bulk_has_friday: bool = False
    eod_friday_meta: bool = False
    iwm_eod_files: int = 0
    sector_etf_1day: int = 0
    databento_zst: int = 0
    fmp_disk_hint: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _count_csv(dir_path: Path) -> tuple[int, str | None, str | None]:
    if not dir_path.is_dir():
        return 0, None, None
    dates: list[str] = []
    for p in dir_path.glob("*.csv"):
        if p.name.startswith("._"):
            continue
        if p.stat().st_size < 1000:
            continue
        dates.append(p.stem)
    if not dates:
        return 0, None, None
    dates.sort()
    return len(dates), dates[0], dates[-1]


def _count_files(dir_path: Path, pattern: str) -> int:
    if not dir_path.is_dir():
        return 0
    return sum(
        1
        for p in dir_path.rglob(pattern)
        if p.is_file() and not p.name.startswith("._")
    )


def run_integrity(write: bool = True) -> IntegrityReport:
    """Scan LaCie for critical archives. Does not invent missing data."""
    report = IntegrityReport(
        checked_at=datetime.now(timezone.utc).isoformat(),
        lacie_root=str(LACIE_ROOT),
        lacie_mounted=LACIE_ROOT.exists(),
    )
    if not report.lacie_mounted:
        report.errors.append("LaCie not mounted")
        report.ok = False
        return report

    n, dmin, dmax = _count_csv(EOD_BULK)
    report.eod_bulk_files = n
    report.eod_bulk_min = dmin
    report.eod_bulk_max = dmax
    report.eod_bulk_has_friday = (EOD_BULK / "2026-07-10.csv").exists()
    report.eod_friday_meta = (EOD_FRIDAY / "meta_done.json").exists()

    report.iwm_eod_files = _count_files(IWM / "ohlcv_eod", "*.parquet") + _count_files(
        IWM / "ohlcv_eod", "*.json"
    )
    report.sector_etf_1day = _count_files(SECTOR_ETFS / "ohlcv" / "1day", "*.parquet")
    report.databento_zst = _count_files(DATABENTO_RAW, "*.zst")

    if report.eod_bulk_files < 1000:
        report.warnings.append(
            f"eod_bulk only {report.eod_bulk_files} days (expect 1900+ for 2019–2026)"
        )
    if not report.eod_bulk_has_friday:
        report.errors.append("Missing eod_bulk/2026-07-10.csv")
    if not FMP_RAW.is_dir():
        report.errors.append(f"Missing FMP raw root {FMP_RAW}")

    # F0 ok = mount + friday bulk present (enough to build F1 core features)
    report.ok = report.lacie_mounted and report.eod_bulk_has_friday and not report.errors

    if write:
        ensure_processed_dirs()
        out = INTEGRITY_DIR / "latest.json"
        out.write_text(json.dumps(report.to_dict(), indent=2))
        stamp = INTEGRITY_DIR / f"integrity_{date.today().isoformat()}.json"
        stamp.write_text(json.dumps(report.to_dict(), indent=2))

    return report
