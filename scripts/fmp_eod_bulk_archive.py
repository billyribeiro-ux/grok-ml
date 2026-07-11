#!/usr/bin/env python3
"""
Download eod-bulk for ~5 years of trading days (max swing/scanner value).

Skip weekends. Skip-if-exists. High bandwidth, high value.
OUT: /Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk/
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
YEARS = int(os.getenv("FMP_EOD_YEARS", "5"))
OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk")
if not Path("/Volumes/LaCie/Aether").exists():
    OUT = ROOT / "data" / "fmp" / "archive_expiry" / "eod_bulk"
OUT.mkdir(parents=True, exist_ok=True)

INTERVAL = 0.05
_last = 0.0
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherEODBulk/1.0"})


def throttle() -> None:
    global _last
    dt = time.time() - _last
    if dt < INTERVAL:
        time.sleep(INTERVAL - dt)
    _last = time.time()


def main() -> int:
    start = ASOF - timedelta(days=365 * YEARS + 30)
    ok = skip = fail = 0
    d = start
    print(f"EOD bulk archive {start} → {ASOF} → {OUT}", flush=True)
    while d <= ASOF:
        if d.weekday() < 5:
            path = OUT / f"{d.isoformat()}.csv"
            if path.exists() and path.stat().st_size > 1000:
                skip += 1
            else:
                for attempt in range(8):
                    throttle()
                    try:
                        r = SESSION.get(
                            f"{BASE}/eod-bulk",
                            params={"date": d.isoformat(), "apikey": API_KEY},
                            timeout=300,
                        )
                        if r.status_code == 429:
                            time.sleep(min(90, 2 ** attempt))
                            continue
                        if r.status_code == 200 and len(r.content) > 1000:
                            path.write_bytes(r.content)
                            ok += 1
                            if ok % 20 == 0:
                                print(f"  ok={ok} skip={skip} fail={fail} last={d}", flush=True)
                            break
                        if r.status_code == 200:
                            # empty holiday
                            skip += 1
                            break
                        fail += 1
                        break
                    except Exception:
                        time.sleep(1 + attempt)
                else:
                    fail += 1
        d += timedelta(days=1)
    print(f"DONE ok={ok} skip={skip} fail={fail}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
