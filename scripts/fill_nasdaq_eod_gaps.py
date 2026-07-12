#!/usr/bin/env python3
"""Download EOD for the ~46 NASDAQ symbols the bulk extraction missed."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
START = os.getenv("FMP_NASDAQ_START", "2018-01-01")
END = "2026-07-10"
SLEEP = float(os.getenv("FMP_NASDAQ_SLEEP", "0.7"))

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full/ohlcv_eod")
OUT.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherNasdaqEODGapFill/1.0"})
_ok = _fail = 0


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


def save(sym: str) -> bool:
    global _ok, _fail
    safe = sym.replace("/", "_")
    out = OUT / f"{safe}.json"
    if out.exists() and out.stat().st_size >= 80:
        return True
    st, body = get("historical-price-eod/full", {"symbol": sym, "from": START, "to": END})
    if st != 200 or len(body) < 80:
        _fail += 1
        print(f"  MISS/empty nq_eod_{sym} status={st} len={len(body)}", flush=True)
        return False
    try:
        json.loads(body)
        out.write_bytes(body)
        _ok += 1
        print(f"  OK nq_eod_{sym} ({len(body)/1e6:.2f} MB)", flush=True)
        return True
    except Exception:
        out.write_bytes(body)
        _ok += 1
        print(f"  OK nq_eod_{sym} ({len(body)/1e6:.2f} MB)", flush=True)
        return True


def main() -> int:
    batch_path = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full/batch_exchange_nasdaq.json")
    rows = json.loads(batch_path.read_text())
    existing = {p.stem for p in OUT.glob("*.json")}
    missing = []
    for r in rows:
        sym = str(r.get("symbol", "")).strip()
        if sym and sym.replace("/", "_") not in existing:
            missing.append(sym)

    print(f"Filling {len(missing)} missing NASDAQ EOD symbols", flush=True)
    for i, sym in enumerate(missing, 1):
        save(sym)
        if i % 10 == 0:
            print(f"  progress {i}/{len(missing)} ok={_ok} fail={_fail}", flush=True)

    print(f"DONE nasdaq eod gaps ok={_ok} fail={_fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
