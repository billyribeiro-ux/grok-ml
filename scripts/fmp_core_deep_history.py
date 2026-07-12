#!/usr/bin/env python3
"""
Deep EOD + multi-TF history for Aether core symbols from 2018-01-01 → 2026-07-10.

Complements full-market eod-bulk (which is one row/day/symbol) with long per-symbol
histories for longs, inverses, sectors, indices, vol complex.

OUT: /Volumes/LaCie/Aether/data/raw/fmp/deep_history_2019/  (legacy dir name; window is 2018→2026-07-10)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
START = os.getenv("FMP_DEEP_START", "2018-01-01")
END = os.getenv("FMP_DEEP_END", "2026-07-10")
# 1hour only needs ~3y to stay useful without huge bandwidth
HOUR_FROM = os.getenv("FMP_DEEP_HOUR_FROM", "2023-01-01")

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/deep_history_2019")
if not Path("/Volumes/LaCie/Aether").exists():
    raise SystemExit("LaCie not mounted")
OUT.mkdir(parents=True, exist_ok=True)

CORE = [
    "AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO",
    "SPY", "QQQ", "IWM", "DIA", "MDY", "VTI", "VOO",
    "SH", "PSQ", "RWM", "DOG", "SQQQ", "SPXU", "TZA", "SDOW", "SRTY",
    "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS",
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLC", "XLRE",
    "SMH", "SOXX", "XBI", "KRE", "XOP", "XHB", "GDX", "TLT", "HYG", "LQD", "GLD", "USO",
    "UVXY", "SVXY", "VIXY", "VXX",
]
INDICES = [
    "^GSPC", "^DJI", "^IXIC", "^RUT", "^NYA",
    "^VIX", "^VIX1D", "^VIX9D", "^VIX3M", "^VIX6M", "^VIX1Y", "^VVIX",
    "^VXN", "^RVX", "^MOVE", "^TNX", "^IRX", "^FVX", "^TYX",
    "^OVX", "^GVZ",
]

INTERVAL = float(os.getenv("FMP_DEEP_INTERVAL", "0.35"))
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherDeepHistory2019/1.0"})
_last = 0.0
_ok = _skip = _fail = 0


def throttle() -> None:
    global _last
    dt = time.time() - _last
    if dt < INTERVAL:
        time.sleep(INTERVAL - dt)
    _last = time.time()


def save(name: str, path: str, params: dict, rel: str, min_bytes: int = 100) -> bool:
    global _ok, _skip, _fail
    out = OUT / rel
    if out.exists() and out.stat().st_size >= min_bytes:
        _skip += 1
        return True
    for attempt in range(10):
        throttle()
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params={**params, "apikey": API_KEY}, timeout=300)
            if r.status_code == 429:
                wait = min(180, 3 * (2 ** min(attempt, 6)))
                print(f"  429 {name} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code == 200 and len(r.content) >= min_bytes:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(r.content)
                _ok += 1
                print(f"  OK {name} ({len(r.content)/1e6:.2f} MB)", flush=True)
                return True
            if r.status_code == 200:
                _fail += 1
                print(f"  MISS {name} empty len={len(r.content)}", flush=True)
                return False
            _fail += 1
            print(f"  MISS {name} status={r.status_code}", flush=True)
            return False
        except Exception as e:
            time.sleep(1 + attempt)
            if attempt == 9:
                _fail += 1
                print(f"  MISS {name} {e}", flush=True)
                return False
    return False


def main() -> int:
    print("=" * 70, flush=True)
    print(f"DEEP HISTORY {START} → {END}", flush=True)
    print(f"OUT={OUT}", flush=True)
    print("=" * 70, flush=True)
    (OUT / "run_start.json").write_text(
        json.dumps(
            {
                "started": datetime.now(timezone.utc).isoformat(),
                "start": START,
                "end": END,
                "n_core": len(CORE),
                "n_indices": len(INDICES),
            },
            indent=2,
        )
    )

    symbols = CORE + INDICES
    print(f"\n[1] EOD full ({len(symbols)} symbols)", flush=True)
    for sym in symbols:
        safe = sym.replace("^", "")
        save(
            f"eod_{safe}",
            "historical-price-eod/full",
            {"symbol": sym, "from": START, "to": END},
            f"eod/{safe}.json",
            min_bytes=200,
        )

    print(f"\n[2] 1hour from {HOUR_FROM}", flush=True)
    for sym in CORE + ["^GSPC", "^VIX", "^RUT", "^IXIC"]:
        safe = sym.replace("^", "")
        save(
            f"1h_{safe}",
            "historical-chart/1hour",
            {"symbol": sym, "from": HOUR_FROM, "to": END},
            f"1hour/{safe}.json",
            min_bytes=100,
        )

    # daily technicals for core equities (regime features)
    print("\n[3] daily technicals (RSI/EMA/ADX)", flush=True)
    for sym in ["SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "SQQQ", "TZA"]:
        for tech, extra in [
            ("rsi", {"periodLength": 14}),
            ("ema", {"periodLength": 20}),
            ("sma", {"periodLength": 50}),
            ("adx", {"periodLength": 14}),
        ]:
            save(
                f"{tech}_{sym}",
                f"technical-indicators/{tech}",
                {"symbol": sym, "timeframe": "1day", "from": START, "to": END, **extra},
                f"technicals/{sym}_{tech}.json",
                min_bytes=100,
            )

    summary = {
        "finished": datetime.now(timezone.utc).isoformat(),
        "ok": _ok,
        "skip": _skip,
        "fail": _fail,
        "out": str(OUT),
    }
    (OUT / "run_done.json").write_text(json.dumps(summary, indent=2))
    print(f"\nDONE deep history ok={_ok} skip={_skip} fail={_fail}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
