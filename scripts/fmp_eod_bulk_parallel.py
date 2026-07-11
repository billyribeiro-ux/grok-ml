#!/usr/bin/env python3
"""
Aether — Parallel multi-year eod-bulk archive (pre FMP Ultimate expiry 2026-07-12).

Friday 2026-07-10 is the last US equity session before sub dies Sunday.
Default history: 2019-01-01 → 2026-07-10 (regime shift / COVID / post-COVID / 2022 bear /
AI melt-up). Override with FMP_EOD_START / FMP_EOD_END. Skip-if-exists. LaCie only.

OUT: /Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk/{YYYY-MM-DD}.csv
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


# Prefer explicit start (2019+) over YEARS. YEARS kept for backward compat.
END = _parse_date(os.getenv("FMP_EOD_END"), ASOF)
if os.getenv("FMP_EOD_START"):
    START = _parse_date(os.getenv("FMP_EOD_START"), date(2019, 1, 1))
else:
    years = int(os.getenv("FMP_EOD_YEARS", "0"))
    if years > 0:
        START = END - timedelta(days=365 * years + 30)
    else:
        START = date(2019, 1, 1)  # default: deep history through regime change

WORKERS = int(os.getenv("FMP_EOD_WORKERS", "3"))
RPS = float(os.getenv("FMP_EOD_RPS", "2.5"))  # eod-bulk is heavy; stay gentle

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk")
if not Path("/Volumes/LaCie/Aether").exists():
    raise SystemExit("LaCie not mounted at /Volumes/LaCie/Aether — refuse local write")
OUT.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_tokens = RPS
_last = time.monotonic()
_tls = threading.local()
stats = {"ok": 0, "skip": 0, "fail": 0, "empty": 0}


def sess() -> requests.Session:
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.headers.update({"User-Agent": "AetherEODBulkParallel/1.0"})
        _tls.s = s
    return _tls.s


def rate_wait() -> None:
    global _tokens, _last
    with _lock:
        t = time.monotonic()
        elapsed = t - _last
        _last = t
        _tokens = min(RPS, _tokens + elapsed * RPS)
        if _tokens < 1:
            time.sleep((1 - _tokens) / RPS)
            _tokens = 0
        else:
            _tokens -= 1


def pull_day(d: date) -> str:
    path = OUT / f"{d.isoformat()}.csv"
    if path.exists() and path.stat().st_size > 1000:
        with _lock:
            stats["skip"] += 1
        return "skip"
    for attempt in range(10):
        rate_wait()
        try:
            r = sess().get(
                f"{BASE}/eod-bulk",
                params={"date": d.isoformat(), "apikey": API_KEY},
                timeout=300,
            )
            if r.status_code == 429:
                wait = min(180, 3 * (2 ** min(attempt, 6)))
                print(f"  429 {d} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code == 200 and len(r.content) > 1000:
                tmp = path.with_suffix(".csv.partial")
                tmp.write_bytes(r.content)
                tmp.replace(path)
                with _lock:
                    stats["ok"] += 1
                    n = stats["ok"]
                if n % 25 == 0:
                    print(
                        f"  progress ok={stats['ok']} skip={stats['skip']} "
                        f"fail={stats['fail']} empty={stats['empty']} last={d}",
                        flush=True,
                    )
                return "ok"
            if r.status_code == 200:
                # holiday / empty
                with _lock:
                    stats["empty"] += 1
                return "empty"
            with _lock:
                stats["fail"] += 1
            print(f"  FAIL {d} status={r.status_code} len={len(r.content)}", flush=True)
            return "fail"
        except Exception as e:
            time.sleep(1 + attempt)
            if attempt == 9:
                with _lock:
                    stats["fail"] += 1
                print(f"  FAIL {d} {e}", flush=True)
                return "fail"
    with _lock:
        stats["fail"] += 1
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
    # newest first — lock Friday + recent history before deep history
    days.sort(reverse=True)
    print("=" * 70, flush=True)
    print("PARALLEL EOD-BULK PRE-EXPIRY ARCHIVE (deep history)", flush=True)
    print(f"  range {START} → {END}  weekdays={len(days)}", flush=True)
    print(f"  OUT={OUT}  workers={WORKERS} rps={RPS}", flush=True)
    present = sum(
        1
        for x in days
        if (OUT / f"{x.isoformat()}.csv").exists()
        and (OUT / f"{x.isoformat()}.csv").stat().st_size > 1000
    )
    print(f"  already present: {present}  remaining≈{len(days) - present}", flush=True)
    print("=" * 70, flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(pull_day, day) for day in days]
        for _ in as_completed(futs):
            pass
    elapsed = time.time() - t0
    print(
        f"\nDONE ok={stats['ok']} skip={stats['skip']} empty={stats['empty']} "
        f"fail={stats['fail']} elapsed={elapsed/60:.1f}m",
        flush=True,
    )
    present = list(OUT.glob("*.csv"))
    present = [p for p in present if not p.name.startswith("._")]
    print(f"files on disk: {len(present)}  size_mb={sum(p.stat().st_size for p in present)/1e6:.0f}", flush=True)
    return 0 if stats["fail"] < 50 else 1


if __name__ == "__main__":
    sys.exit(main())
