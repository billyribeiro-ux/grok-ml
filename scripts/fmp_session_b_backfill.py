#!/usr/bin/env python3
"""
Backfill Session B misses:
  - EOD: MFLA (ETN), ICDXF, WISSF (bonds)
  - 5m + 1m: 27 ETN symbols that returned empty in the first cap attempt.

Single-threaded, atomic writes, honest logging.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

SLEEP = float(os.getenv("FMP_SESSION_B_SLEEP", "1.0"))
if SLEEP < 1.0:
    SLEEP = 1.0

BASE = "https://financialmodelingprep.com/stable"
EOD_FROM = "2015-01-01"
EOD_TO = "2026-07-10"
INTRADAY_FROM = "2024-07-10"
INTRADAY_TO = "2026-07-10"

MIN_EOD_BYTES = 80
MIN_INTRADAY_BYTES = 80

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherSessionBBackfill/1.0"})


def log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def safe_filename(sym: str) -> str:
    return sym.replace("/", "_").replace("\\", "_").replace("^", "_")


def get_json(path: str, params: dict | None = None, retries: int = 5) -> tuple[int, any]:
    params = {**(params or {}), "apikey": API_KEY}
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            time.sleep(SLEEP)
            r = SESSION.get(url, params=params, timeout=120)
            if r.status_code == 429:
                wait = min(180, 10 * (attempt + 1))
                log(f"429 on {path} wait {wait}s")
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(2 + attempt)
                continue
            if r.status_code != 200:
                return r.status_code, None
            try:
                data = r.json()
            except Exception:
                return r.status_code, None
            return r.status_code, data
        except Exception as e:
            log(f"ERR {path}: {e}")
            time.sleep(2 + attempt)
    return 0, None


def save_atomic(path: Path, data: any, min_bytes: int = 10) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, indent=2, default=str).encode("utf-8")
    if len(body) < min_bytes:
        return False
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_bytes(body)
    partial.rename(path)
    return True


def fetch_save(name: str, api_path: str, params: dict, out_path: Path, min_bytes: int) -> str:
    if out_path.exists() and out_path.stat().st_size >= min_bytes:
        return "skip"
    status, data = get_json(api_path, params)
    if status != 200 or data is None:
        return f"miss status={status}"
    if isinstance(data, list) and len(data) == 0:
        return "miss empty"
    if save_atomic(out_path, data, min_bytes=min_bytes):
        return f"ok {len(json.dumps(data))} bytes"
    return "miss small"


def main() -> int:
    log("Starting Session B backfill")

    # EOD misses
    eod_misses = [
        ("MFLA", Path("/Volumes/LaCie/Aether/data/raw/fmp/etn/ohlcv_eod/MFLA.json")),
        ("ICDXF", Path("/Volumes/LaCie/Aether/data/raw/fmp/bonds/ohlcv_eod/ICDXF.json")),
        ("WISSF", Path("/Volumes/LaCie/Aether/data/raw/fmp/bonds/ohlcv_eod/WISSF.json")),
    ]
    for sym, out in eod_misses:
        res = fetch_save(
            f"eod_{sym}",
            "historical-price-eod/full",
            {"symbol": sym, "from": EOD_FROM, "to": EOD_TO},
            out,
            MIN_EOD_BYTES,
        )
        log(f"EOD {sym}: {res}")

    # ETN 5m/1m misses
    etn_5m_misses = [
        "DVHL", "BJO", "DJCB", "OIL", "JJSB", "BDCL", "COW", "DWT", "FIEU",
        "UGAZF", "GRWN", "ZIV", "BDD", "DLBR", "MJO", "UBC", "ULBR", "FNGA",
        "BNKO", "XXXX", "FLAT", "HEVY", "JJTFF", "MLPQ", "ZIVZF", "JJA", "AMJL",
    ]
    for sym in etn_5m_misses:
        safe = safe_filename(sym)
        for tf in ("5min", "1min"):
            out_dir = Path(f"/Volumes/LaCie/Aether/data/raw/fmp/etn/ohlcv_{tf}")
            out = out_dir / f"{safe}.json"
            res = fetch_save(
                f"{tf}_{sym}",
                f"historical-chart/{tf}",
                {"symbol": sym, "from": INTRADAY_FROM, "to": INTRADAY_TO},
                out,
                MIN_INTRADAY_BYTES,
            )
            log(f"{tf} {sym}: {res}")

    log("Backfill complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
