#!/usr/bin/env python3
"""
Fill missing NASDAQ top-300 5m and top-100 1m gaps.

Reads the NASDAQ batch freeze, sorts by volume, and downloads only the
ohlcv_5min/ohlcv_1min files that are missing or too small. Skip-if-exists.
Slow, compliant FMP rate limiting.
"""

from __future__ import annotations

import json
import os
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
END = ASOF.isoformat()
START_5M = os.getenv("FMP_NASDAQ_5M_FROM", "2024-07-10")
START_1M = os.getenv("FMP_NASDAQ_1M_FROM", (ASOF - timedelta(days=90)).isoformat())
SLEEP = float(os.getenv("FMP_NASDAQ_SLEEP", "0.7"))
TOP_5M = int(os.getenv("FMP_NASDAQ_TOP_5M", "300"))
TOP_1M = int(os.getenv("FMP_NASDAQ_TOP_1M", "100"))

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full")
OUT.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherNasdaqGapFill/1.0"})
_ok = _skip = _fail = 0


def get(path: str, params: dict | None = None, retries: int = 12) -> tuple[int, bytes]:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        if attempt == 0:
            time.sleep(SLEEP)
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=300)
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


def save(name: str, api: str, params: dict | None, out: Path, min_bytes: int = 80) -> bool:
    global _ok, _skip, _fail
    if out.exists() and out.stat().st_size >= min_bytes:
        _skip += 1
        return True
    st, body = get(api, params)
    if st != 200 or len(body) < min_bytes:
        _fail += 1
        if st == 200:
            print(f"  empty {name} len={len(body)}", flush=True)
        else:
            print(f"  MISS {name} status={st} len={len(body)}", flush=True)
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix not in (".json", ".csv"):
        try:
            json.loads(body)
            out = out.with_suffix(".json")
        except Exception:
            if b"," in body[:100]:
                out = out.with_suffix(".csv")
    out.write_bytes(body)
    _ok += 1
    print(f"  OK {name} ({len(body)/1e6:.2f} MB)", flush=True)
    return True


def main() -> int:
    batch_path = OUT / "batch_exchange_nasdaq.json"
    if not batch_path.exists():
        print("MISS batch_exchange_nasdaq.json")
        return 1

    rows = json.loads(batch_path.read_text())
    rows = [r for r in rows if isinstance(r, dict) and r.get("symbol")]
    rows.sort(key=lambda r: float(r.get("volume") or 0), reverse=True)

    top5m = rows[:TOP_5M]
    top1m = rows[:TOP_1M]

    print(f"\n[5m] Filling {len(top5m)} symbols", flush=True)
    for i, r in enumerate(top5m, 1):
        sym = str(r.get("symbol")).strip()
        safe = sym.replace("/", "_")
        save(
            f"nq5m_{sym}",
            "historical-chart/5min",
            {"symbol": sym, "from": START_5M, "to": END},
            OUT / "ohlcv_5min" / f"{safe}.json",
            min_bytes=80,
        )
        if i % 20 == 0:
            print(f"  progress 5m {i}/{len(top5m)} ok={_ok} skip={_skip} fail={_fail}", flush=True)

    print(f"\n[1m] Filling {len(top1m)} symbols", flush=True)
    for i, r in enumerate(top1m, 1):
        sym = str(r.get("symbol")).strip()
        safe = sym.replace("/", "_")
        save(
            f"nq1m_{sym}",
            "historical-chart/1min",
            {"symbol": sym, "from": START_1M, "to": END},
            OUT / "ohlcv_1min" / f"{safe}.json",
            min_bytes=80,
        )
        if i % 10 == 0:
            print(f"  progress 1m {i}/{len(top1m)} ok={_ok} skip={_skip} fail={_fail}", flush=True)

    print(f"\nDONE fill ok={_ok} skip={_skip} fail={_fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
