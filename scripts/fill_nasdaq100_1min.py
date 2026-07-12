#!/usr/bin/env python3
"""
Helper agent: NASDAQ-100 1min gap fill.
Runs in parallel with the main MTF process, but with gentler rate limits.
Skip-if-exists so it doesn't duplicate work.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
END = ASOF.isoformat()
START_1M = os.getenv("FMP_NASDAQ100_1M_FROM", (ASOF - timedelta(days=90)).isoformat())
WORKERS = int(os.getenv("FMP_NASDAQ100_1MIN_WORKERS", "2"))
SLEEP = float(os.getenv("FMP_NASDAQ100_1MIN_SLEEP", "0.3"))

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full/ohlcv_1min")
OUT.mkdir(parents=True, exist_ok=True)

_ok = _skip = _fail = 0
_lock = None


def get(path: str, params: dict | None = None, retries: int = 8) -> tuple[int, bytes]:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        time.sleep(SLEEP)
        try:
            r = requests.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=300)
            if r.status_code == 429:
                wait = min(240, 5 * (2 ** min(attempt, 6)))
                print(f"  429 {path} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            return r.status_code, r.content
        except Exception as e:
            print(f"  err {path}: {e}", flush=True)
            time.sleep(1 + attempt)
    return 0, b""


def download_sym(sym: str) -> None:
    global _ok, _skip, _fail
    safe = sym.replace("/", "_")
    out = OUT / f"{safe}.json"
    if out.exists() and out.stat().st_size >= 80:
        with _lock:
            _skip += 1
        return
    st, body = get("historical-chart/1min", {"symbol": sym, "from": START_1M, "to": END})
    if st != 200 or len(body) < 80:
        with _lock:
            _fail += 1
        print(f"  MISS/empty nq1m_{sym} status={st} len={len(body)}", flush=True)
        return
    try:
        json.loads(body)
        out = out.with_suffix(".json")
    except Exception:
        if b"," in body[:100]:
            out = out.with_suffix(".csv")
    out.write_bytes(body)
    with _lock:
        _ok += 1
    print(f"  OK nq1m_{sym} ({len(body)/1e6:.2f} MB)", flush=True)


def main() -> int:
    global _lock
    _lock = __import__('threading').Lock()

    tickers_path = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full/nasdaq100_tickers.json")
    if not tickers_path.exists():
        print("MISS nasdaq100_tickers.json")
        return 1

    syms = json.loads(tickers_path.read_text())
    syms = [str(s).strip() for s in syms if s]
    print(f"NASDAQ-100 1min helper: {len(syms)} symbols, workers={WORKERS}, sleep={SLEEP}", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(download_sym, syms))

    print(f"DONE nasdaq100 1min helper ok={_ok} skip={_skip} fail={_fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
