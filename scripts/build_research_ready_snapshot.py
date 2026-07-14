#!/usr/bin/env python3
"""
Write a single READY snapshot of what the main prompt can run *now* vs still downloading.

OUT: /Volumes/LaCie/Aether/data/processed/research/ready_snapshot.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aether.paths import FMP_RAW, PROCESSED, require_lacie


def count(d: Path) -> int:
    if not d.exists():
        return 0
    return sum(1 for p in d.iterdir() if p.is_file() and not p.name.startswith("._"))


def main() -> int:
    require_lacie()
    research = PROCESSED / "research"
    mtf = {}
    for name, root, target in (
        ("sp500", FMP_RAW / "sp500_full", 503),
        ("iwm", FMP_RAW / "iwm_russell2000", 1972),
        ("nasdaq", FMP_RAW / "nasdaq_full", 14213),
    ):
        row = {"target": target}
        for iv in ("eod", "1hour", "15min", "5min", "1min"):
            n = count(root / f"ohlcv_{iv}")
            row[iv] = n
            row[f"{iv}_complete"] = n >= target if iv != "eod" or name != "nasdaq" else n >= 14000
        # eod for nasdaq ~14216
        if name == "nasdaq":
            row["eod_complete"] = row["eod"] >= 14000
        else:
            row["eod_complete"] = row["eod"] >= target
        mtf[name] = row

    specialists = {}
    for p in sorted(research.glob("earnings_specialist_*_{pre8,post1d}.json".replace("{pre8,post1d}", "*"))):
        if p.name.startswith("._") or not p.name.endswith(".json"):
            continue
        if "_oos" in p.name:
            continue
        try:
            d = json.loads(p.read_text())
            specialists[p.stem] = {
                "mode": d.get("mode"),
                "strategy": d.get("strategy"),
                "n_events": d.get("n_events"),
                "n_test": d.get("n_test"),
                "accuracy": d.get("accuracy"),
                "long_mean_pnl": d.get("long_mean_pnl"),
                "short_mean_pnl": d.get("short_mean_pnl"),
                "mean_vol_spike_8_oos": d.get("mean_vol_spike_8_oos"),
            }
        except Exception:
            continue

    # glob simpler
    specialists = {}
    for p in research.glob("earnings_specialist_*.json"):
        if p.name.startswith("._") or p.name.endswith("_oos.json"):
            continue
        try:
            d = json.loads(p.read_text())
            if "mode" not in d and "accuracy" not in d:
                continue
            specialists[p.stem] = {
                "mode": d.get("mode"),
                "strategy": d.get("strategy"),
                "universe": d.get("universe"),
                "n_events": d.get("n_events"),
                "n_test": d.get("n_test"),
                "accuracy": d.get("accuracy"),
                "long_mean_pnl": d.get("long_mean_pnl")
                or d.get("long_only_mean_pre8")
                or d.get("long_only_mean_post_1d"),
                "short_mean_pnl": d.get("short_mean_pnl")
                or d.get("short_only_mean_pre8")
                or d.get("short_only_mean_post_1d"),
                "mean_vol_spike_8_oos": d.get("mean_vol_spike_8_oos"),
            }
        except Exception:
            continue

    mission = None
    mp = PROCESSED / "telemetry" / "latest_flight.json"
    if mp.exists():
        try:
            m = json.loads(mp.read_text())
            mission = {
                "name": m.get("name"),
                "stats": m.get("stats"),
                "promoted_to_mission_at": m.get("promoted_to_mission_at"),
            }
        except Exception:
            pass

    ready = {
        "eod_mission_brain": True,
        "sp500_all_mtf": all(mtf["sp500"][f"{iv}_complete"] for iv in ("eod", "1hour", "15min", "5min", "1min")),
        "iwm_eod_1h_15m": mtf["iwm"]["eod_complete"]
        and mtf["iwm"]["1hour"] >= 1972
        and mtf["iwm"]["15min"] >= 1972,
        "iwm_5m": mtf["iwm"]["5min"] >= 1972,
        "iwm_1m": mtf["iwm"]["1min"] >= 1972,
        "iwm_5m_1m": mtf["iwm"]["5min"] >= 1972 and mtf["iwm"]["1min"] >= 1972,
        "nasdaq_eod": mtf["nasdaq"]["eod_complete"],
        "nasdaq_full_mtf": all(
            mtf["nasdaq"][iv] >= 14000 for iv in ("1hour", "15min", "5min", "1min")
        ),
        "earnings_index_post1d": all(
            f"earnings_specialist_{u}_post1d" in specialists or f"earnings_specialist_{u}" in specialists
            for u in ("sp500", "iwm", "nasdaq")
        ),
        "earnings_index_pre8": all(
            f"earnings_specialist_{u}_pre8" in specialists for u in ("sp500", "iwm", "nasdaq")
        ),
    }

    out = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "window": "2018-01-01→2026-07-10",
        "ready": ready,
        "mtf": mtf,
        "specialists": specialists,
        "mission": mission,
        "still_waiting": [k for k, v in ready.items() if not v],
        "can_run_now": [k for k, v in ready.items() if v],
    }
    research.mkdir(parents=True, exist_ok=True)
    path = research / "ready_snapshot.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
