"""Mission telemetry — write flight reports for cockpit / postmortems."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aether.engine.backtest import BacktestResult
from aether.paths import LACIE_ROOT, PROCESSED, require_lacie


def telemetry_dir(offline: bool = False) -> Path:
    """Prefer LaCie processed/; fall back to repo .aether/telemetry if unmounted."""
    if not offline:
        try:
            require_lacie()
            d = PROCESSED / "telemetry"
            d.mkdir(parents=True, exist_ok=True)
            return d
        except Exception:
            pass
    # local fallback for pure offline dev
    root = Path(__file__).resolve().parents[3]
    d = root / ".aether" / "telemetry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_flight_report(
    *,
    name: str,
    stats: dict[str, Any],
    source: str,
    symbols: list[str],
    extra: dict[str, Any] | None = None,
    offline: bool = False,
) -> Path:
    payload = {
        "name": name,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "symbols": symbols,
        "stats": stats,
        "extra": extra or {},
        "laws": {
            "L0_truth": True,
            "note": "Mock flights are plumbing only; not live edge.",
        },
    }
    d = telemetry_dir(offline=offline)
    path = d / f"{name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
    latest = d / "latest_flight.json"
    latest.write_text(json.dumps(payload, indent=2, default=str))
    return path


def flight_from_backtest(
    bt: BacktestResult,
    *,
    name: str,
    source: str,
    symbols: list[str],
    offline: bool = False,
    extra: dict[str, Any] | None = None,
) -> Path:
    return write_flight_report(
        name=name,
        stats=bt.stats,
        source=source,
        symbols=symbols,
        extra=extra,
        offline=offline,
    )
