#!/usr/bin/env python3
"""
Aether — Multi-year full-market eod-bulk archive (pre FMP Ultimate expiry 2026-07-12).

Default: 2018-01-01 → 2026-07-10 (hard pin). Skip-if-exists. LaCie only.
Sequential by default — eod-bulk 429s hard under concurrency.

OUT: /Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk/{YYYY-MM-DD}.csv

Env:
  FMP_EOD_START=2018-01-01
  FMP_EOD_END=2026-07-10
  FMP_EOD_SLEEP=1.25   seconds between successful requests
  FMP_EOD_WORKERS=1    >1 only if rate limit is healthy
"""

from __future__ import annotations

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
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


def _parse_date(s: str | None, default: date) -> date:
    if not s:
        return default
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


END = _parse_date(os.getenv("FMP_EOD_END"), ASOF)
if os.getenv("FMP_EOD_START"):
    START = _parse_date(os.getenv("FMP_EOD_START"), date(2018, 1, 1))
else:
    years = int(os.getenv("FMP_EOD_YEARS", "0"))
    START = END - timedelta(days=365 * years + 30) if years > 0 else date(2018, 1, 1)

WORKERS = int(os.getenv("FMP_EOD_WORKERS", "1"))
SLEEP = float(os.getenv("FMP_EOD_SLEEP", "1.25"))

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk")
if not Path("/Volumes/LaCie/Aether").exists():
    raise SystemExit("LaCie not mounted at /Volumes/LaCie/Aether — refuse local write")
OUT.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_tls = threading.local()
stats = {"ok": 0, "skip": 0, "fail": 0, "empty": 0, "bytes": 0}


def sess() -> requests.Session:
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.headers.update({"User-Agent": "AetherEODBulkDeep/2.0"})
        _tls.s = s
    return _tls.s


def pull_day(d: date) -> str:
    path = OUT / f"{d.isoformat()}.csv"
    if path.exists() and path.stat().st_size > 1000:
        with _lock:
            stats["skip"] += 1
        return "skip"

    attempt = 0
    while attempt < 40:  # patient — do not abandon days
        attempt += 1
        try:
            r = sess().get(
                f"{BASE}/eod-bulk",
                params={"date": d.isoformat(), "apikey": API_KEY},
                timeout=300,
            )
            if r.status_code == 429:
                wait = min(300, 5 * (2 ** min(attempt - 1, 6)))
                print(f"  429 {d} attempt={attempt} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(min(60, 2 + attempt))
                continue
            if r.status_code == 200 and len(r.content) > 1000:
                tmp = path.with_suffix(".csv.partial")
                tmp.write_bytes(r.content)
                tmp.replace(path)
                with _lock:
                    stats["ok"] += 1
                    stats["bytes"] += len(r.content)
                    n = stats["ok"]
                print(
                    f"  OK {d} ({len(r.content)/1e6:.2f} MB) "
                    f"ok={stats['ok']} skip={stats['skip']} fail={stats['fail']}",
                    flush=True,
                )
                if n % 50 == 0:
                    print(
                        f"  --- checkpoint ok={stats['ok']} "
                        f"mb={stats['bytes']/1e6:.0f} last={d} ---",
                        flush=True,
                    )
                time.sleep(SLEEP)
                return "ok"
            if r.status_code == 200:
                with _lock:
                    stats["empty"] += 1
                print(f"  empty/holiday {d} len={len(r.content)}", flush=True)
                time.sleep(SLEEP * 0.5)
                return "empty"
            print(f"  FAIL {d} status={r.status_code} len={len(r.content)}", flush=True)
            with _lock:
                stats["fail"] += 1
            time.sleep(SLEEP)
            return "fail"
        except Exception as e:
            print(f"  err {d}: {e}", flush=True)
            time.sleep(min(60, 2 + attempt))

    with _lock:
        stats["fail"] += 1
    print(f"  GIVE UP {d} after {attempt} attempts", flush=True)
    return "fail"


def main() -> int:
    if START > END:
        raise SystemExit(f"START {START} > END {END}")

    days: list[date] = []
    d = START
    while d <= END:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    # newest first
    days.sort(reverse=True)

    present = sum(
        1
        for x in days
        if (OUT / f"{x.isoformat()}.csv").exists()
        and (OUT / f"{x.isoformat()}.csv").stat().st_size > 1000
    )
    todo = [x for x in days if not ((OUT / f"{x.isoformat()}.csv").exists() and (OUT / f"{x.isoformat()}.csv").stat().st_size > 1000)]

    print("=" * 70, flush=True)
    print("EOD-BULK DEEP HISTORY ARCHIVE", flush=True)
    print(f"  range {START} → {END}  weekdays={len(days)}", flush=True)
    print(f"  present={present}  todo={len(todo)}", flush=True)
    print(f"  OUT={OUT}  workers={WORKERS} sleep={SLEEP}s", flush=True)
    print("=" * 70, flush=True)

    t0 = time.time()
    if WORKERS <= 1:
        for day in todo:
            pull_day(day)
    else:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(pull_day, day) for day in todo]
            for _ in as_completed(futs):
                pass

    elapsed = time.time() - t0
    files = [p for p in OUT.glob("*.csv") if not p.name.startswith("._")]
    print(
        f"\nDONE ok={stats['ok']} skip={stats['skip']} empty={stats['empty']} "
        f"fail={stats['fail']} elapsed={elapsed/60:.1f}m",
        flush=True,
    )
    print(
        f"files on disk: {len(files)}  size_mb={sum(p.stat().st_size for p in files)/1e6:.0f}",
        flush=True,
    )
    return 0 if stats["fail"] < 100 else 1


if __name__ == "__main__":
    sys.exit(main())
