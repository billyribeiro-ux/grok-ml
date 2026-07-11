#!/usr/bin/env python3
"""
Aether — Full NASDAQ book + comprehensive inverse ETF archive (FMP Ultimate).

LaCie only. Skip-if-exists. Patient 429 backoff.

1) NASDAQ exchange batch freeze + full symbol list
2) Per-symbol EOD 2015-01-01 → 2026-07-10 for every NASDAQ batch symbol
3) Screener pack (profile / key-metrics / ratios / float) for liquid NASDAQ
   (volume>0 on freeze, else top N by any price)
4) Comprehensive US inverse/short/vol ETFs from etf-list name filter
   + hand list, with EOD + 5m + ETF structure enrichment

Note: full-market eod-bulk already has daily bars for all names; this pack
builds clean per-symbol files + screener features for the NASDAQ book.

OUT: /Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full/
     /Volumes/LaCie/Aether/data/raw/fmp/inverses_full/
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")
if not Path("/Volumes/LaCie/Aether").exists():
    raise SystemExit("LaCie not mounted")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
START = os.getenv("FMP_NASDAQ_START", "2015-01-01")
END = ASOF.isoformat()
START_5M = os.getenv("FMP_NASDAQ_5M_FROM", "2024-07-10")  # 2y would be huge; default ~1y
START_1M = os.getenv("FMP_NASDAQ_1M_FROM", (ASOF - timedelta(days=90)).isoformat())  # 90d default
SLEEP = float(os.getenv("FMP_NASDAQ_SLEEP", "0.65"))
SCREENER_MAX = int(os.getenv("FMP_NASDAQ_SCREENER_MAX", "4000"))  # liquid first
TOP_5M = int(os.getenv("FMP_NASDAQ_TOP_5M", "300"))  # liquid NASDAQ 5m
TOP_1M = int(os.getenv("FMP_NASDAQ_TOP_1M", "100"))  # liquid NASDAQ 1m

OUT_NQ = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full")
OUT_INV = Path("/Volumes/LaCie/Aether/data/raw/fmp/inverses_full")
OUT_NQ.mkdir(parents=True, exist_ok=True)
OUT_INV.mkdir(parents=True, exist_ok=True)

# Hand-curated US inverse / short / vol (complements name filter)
HAND_INVERSES = [
    "SH", "PSQ", "DOG", "RWM", "HDGE", "EUM", "EFZ", "YXI", "BZQ", "EWV",
    "SDS", "QID", "DXD", "TWM", "SKF", "SEF", "REK", "SRS", "ERY", "DUG",
    "SPXU", "SPXS", "SQQQ", "SDOW", "SRTY", "TZA", "TECS", "SOXS", "FAZ", "LABD",
    "FNGD", "BERZ", "WEBS", "HIBS", "SMDD", "MIDZ", "DPST", "NAIL", "DRIP", "GASX",
    "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS", "NVD", "NVDQ", "TSLQ", "AMDS",
    "MSFD", "GOOSD", "METD", "SMCZ", "MAXI",
    "UVXY", "SVXY", "VIXY", "VIXM", "UVIX", "SVIX", "VXX", "VXZ", "VIXM", "TAIL",
    "SVOL", "ZIV", "XIV", "TVIX", "UVIX",
    "SARK", "WEBS", "HIBS", "SIJ", "SSG", "SDP", "SCC", "SZK", "BIS", "RXD",
    "DULL", "GLL", "ZSL", "SCO", "KOLD", "BOIL", "UCO",  # some leveraged commodity
    "TBT", "TBF", "TBX", "PST", "TTT", "TYD", "TYO",  # rates shortish
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherFMPNasdaqFull/1.0"})
_ok = _skip = _fail = 0
_bytes = 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def save(name: str, api: str, params: dict | None, out: Path, min_bytes: int = 30) -> bool:
    global _ok, _skip, _fail, _bytes
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
    _bytes += len(body)
    print(f"  OK {name} ({len(body)/1e6:.2f} MB)", flush=True)
    return True


def is_us_symbol(sym: str) -> bool:
    if not sym or len(sym) > 12:
        return False
    if any(sym.endswith(sfx) for sfx in (".L", ".DE", ".PA", ".AS", ".SW", ".MI", ".HK", ".T", ".AX", ".TO", ".V")):
        return False
    if re.search(r"[./]", sym) and not re.match(r"^[A-Z0-9.-]+$", sym):
        return False
    return bool(re.match(r"^[A-Z][A-Z0-9.-]{0,9}$", sym))


def inverse_name(name: str, sym: str) -> bool:
    u = f"{name} {sym}".upper()
    keys = [
        "INVERSE", "ULTRASHORT", "ULTRA SHORT", "BEAR ", " -1X", "-1X ", "-2X", "-3X",
        "SHORT S&P", "SHORT QQQ", "SHORT DOW", "SHORT RUSSELL", "SHORT SEMI",
        "DAILY BEAR", "BEARISH", "ANTI-", "FADE ",
    ]
    # exclude obvious non-inverse false positives
    if "SHORT DURATION" in u or "SHORT-TERM" in u or "SHORT TERM BOND" in u:
        return False
    if "SHORT MATURITY" in u or "SHORT TREASURY" in u and "BEAR" not in u and "INVERSE" not in u:
        # T-bill short duration funds
        if "BEAR" not in u and "INVERSE" not in u and "-1X" not in u and "-2X" not in u:
            return False
    return any(k in u for k in keys)


def phase_nasdaq_universe() -> list[dict]:
    print("\n[1] NASDAQ batch freeze + universe", flush=True)
    st, body = get("batch-exchange-quote", {"exchange": "NASDAQ"})
    if st != 200 or len(body) < 1000:
        print("  FATAL nasdaq batch failed", flush=True)
        return []
    path = OUT_NQ / "batch_exchange_nasdaq.json"
    path.write_bytes(body)
    rows = json.loads(body)
    print(f"  batch symbols={len(rows)}", flush=True)
    # sort liquid first
    def vol(r: dict) -> float:
        try:
            return float(r.get("volume") or 0)
        except Exception:
            return 0.0

    rows = [r for r in rows if isinstance(r, dict) and r.get("symbol")]
    rows.sort(key=vol, reverse=True)
    (OUT_NQ / "universe_meta.json").write_text(
        json.dumps(
            {
                "as_of": END,
                "n": len(rows),
                "start_eod": START,
                "source": "batch-exchange-quote?exchange=NASDAQ",
                "top20_by_volume": [
                    {"symbol": r.get("symbol"), "volume": r.get("volume"), "price": r.get("price")}
                    for r in rows[:20]
                ],
            },
            indent=2,
        )
    )
    # also stock-list + actively trading for reference
    save("stock_list", "stock-list", {}, OUT_NQ / "reference/stock_list.json", 1000)
    save("actively_trading", "actively-trading-list", {}, OUT_NQ / "reference/actively_trading.json", 1000)
    return rows


def phase_nasdaq_eod(rows: list[dict]) -> None:
    print(f"\n[2] NASDAQ per-symbol EOD {START}→{END} n={len(rows)}", flush=True)
    for i, r in enumerate(rows, 1):
        sym = str(r.get("symbol", "")).strip()
        if not sym:
            continue
        # FMP symbols can include dots
        safe = sym.replace("/", "_")
        out = OUT_NQ / "ohlcv_eod" / f"{safe}.json"
        save(
            f"nq_eod_{sym}",
            "historical-price-eod/full",
            {"symbol": sym, "from": START, "to": END},
            out,
            min_bytes=80,
        )
        if i % 50 == 0:
            print(f"  progress eod {i}/{len(rows)} ok={_ok} skip={_skip} fail={_fail}", flush=True)


def phase_nasdaq_screener(rows: list[dict]) -> None:
    # liquid first
    liquid = []
    for r in rows:
        try:
            v = float(r.get("volume") or 0)
        except Exception:
            v = 0
        if v > 0:
            liquid.append(r)
    if len(liquid) < 500:
        liquid = rows[:SCREENER_MAX]
    else:
        liquid = liquid[:SCREENER_MAX]
    print(f"\n[3] NASDAQ screener enrichment n={len(liquid)} (cap {SCREENER_MAX})", flush=True)
    for i, r in enumerate(liquid, 1):
        sym = str(r.get("symbol", "")).strip()
        if not sym:
            continue
        safe = sym.replace("/", "_")
        base = OUT_NQ / "screener" / safe
        # save freeze quote
        qpath = base / "quote.json"
        if not qpath.exists():
            qpath.parent.mkdir(parents=True, exist_ok=True)
            qpath.write_text(json.dumps(r, indent=2))
        save(f"{sym}_profile", "profile", {"symbol": sym}, base / "profile.json", 40)
        save(f"{sym}_float", "shares-float", {"symbol": sym}, base / "float.json", 8)
        save(f"{sym}_key", "key-metrics-ttm", {"symbol": sym}, base / "key_metrics_ttm.json", 20)
        save(f"{sym}_ratios", "ratios-ttm", {"symbol": sym}, base / "ratios_ttm.json", 20)
        if i % 25 == 0:
            print(f"  progress screener {i}/{len(liquid)} ok={_ok} fail={_fail}", flush=True)


def phase_nasdaq_5m(rows: list[dict]) -> None:
    top = rows[:TOP_5M]
    print(f"\n[4] NASDAQ top-{TOP_5M} by volume → 5min from {START_5M}", flush=True)
    for i, r in enumerate(top, 1):
        sym = str(r.get("symbol", "")).strip()
        if not sym:
            continue
        safe = sym.replace("/", "_")
        save(
            f"nq5m_{sym}",
            "historical-chart/5min",
            {"symbol": sym, "from": START_5M, "to": END},
            OUT_NQ / "ohlcv_5min" / f"{safe}.json",
            min_bytes=80,
        )
        if i % 20 == 0:
            print(f"  progress 5m {i}/{len(top)} ok={_ok}", flush=True)


def phase_nasdaq_1m(rows: list[dict]) -> None:
    top = rows[:TOP_1M]
    print(f"\n[4b] NASDAQ top-{TOP_1M} by volume → 1min from {START_1M}", flush=True)
    for i, r in enumerate(top, 1):
        sym = str(r.get("symbol", "")).strip()
        if not sym:
            continue
        safe = sym.replace("/", "_")
        save(
            f"nq1m_{sym}",
            "historical-chart/1min",
            {"symbol": sym, "from": START_1M, "to": END},
            OUT_NQ / "ohlcv_1min" / f"{safe}.json",
            min_bytes=80,
        )
        if i % 10 == 0:
            print(f"  progress 1m {i}/{len(top)} ok={_ok}", flush=True)


def build_inverse_list() -> list[str]:
    print("\n[5] Build inverse ETF universe", flush=True)
    st, body = get("etf-list", {})
    inv: list[str] = []
    seen: set[str] = set()
    if st == 200 and body:
        (OUT_INV / "etf_list.json").write_bytes(body)
        try:
            rows = json.loads(body)
        except Exception:
            rows = []
        if isinstance(rows, list):
            for r in rows:
                if not isinstance(r, dict):
                    continue
                sym = str(r.get("symbol") or "").strip()
                name = str(r.get("name") or r.get("companyName") or "")
                if not is_us_symbol(sym):
                    continue
                if inverse_name(name, sym) or sym in HAND_INVERSES:
                    if sym not in seen:
                        seen.add(sym)
                        inv.append(sym)
    for sym in HAND_INVERSES:
        if is_us_symbol(sym) and sym not in seen:
            seen.add(sym)
            inv.append(sym)
    inv = sorted(inv)
    (OUT_INV / "inverse_universe.json").write_text(
        json.dumps({"as_of": END, "n": len(inv), "symbols": inv}, indent=2)
    )
    print(f"  inverse US symbols={len(inv)}", flush=True)
    return inv


def phase_inverses(symbols: list[str]) -> None:
    print(f"\n[6] Inverse ETF deep pack n={len(symbols)}", flush=True)
    for i, sym in enumerate(symbols, 1):
        base = OUT_INV / "etfs" / sym
        print(f"--- inverse {i}/{len(symbols)} {sym} ---", flush=True)
        save(f"{sym}_eod", "historical-price-eod/full", {"symbol": sym, "from": START, "to": END}, base / "eod.json", 80)
        save(f"{sym}_profile", "profile", {"symbol": sym}, base / "profile.json", 30)
        save(f"{sym}_5m", "historical-chart/5min", {"symbol": sym, "from": START_5M, "to": END}, base / "ohlcv_5min.json", 50)
        save(f"{sym}_info", "etf/info", {"symbol": sym}, base / "etf_info.json", 15)
        save(f"{sym}_hold", "etf/holdings", {"symbol": sym}, base / "holdings.json", 20)
        save(f"{sym}_sec", "etf/sector-weightings", {"symbol": sym}, base / "sector_weightings.json", 8)
        save(f"{sym}_mcap", "historical-market-capitalization", {"symbol": sym, "from": START, "to": END}, base / "market_cap.json", 15)


def main() -> int:
    print("=" * 70, flush=True)
    print("NASDAQ FULL + INVERSE ETFs ARCHIVE", flush=True)
    print(f"OUT_NQ={OUT_NQ}", flush=True)
    print(f"OUT_INV={OUT_INV}", flush=True)
    print(f"EOD {START}→{END}  sleep={SLEEP}s screener_max={SCREENER_MAX} top5m={TOP_5M} top1m={TOP_1M}", flush=True)
    print("=" * 70, flush=True)
    (OUT_NQ / "run_start.json").write_text(json.dumps({"started": now(), "as_of": END}, indent=2))
    (OUT_INV / "run_start.json").write_text(json.dumps({"started": now(), "as_of": END}, indent=2))

    rows = phase_nasdaq_universe()
    if rows:
        # Daily EOD is foundational — do screener, then EOD for all, then intraday 5m/1m
        phase_nasdaq_screener(rows)
        phase_nasdaq_eod(rows)
        phase_nasdaq_5m(rows)
        phase_nasdaq_1m(rows)

    inv = build_inverse_list()
    phase_inverses(inv)

    summary = {
        "finished": now(),
        "ok": _ok,
        "skip": _skip,
        "fail": _fail,
        "bytes": _bytes,
        "mb": round(_bytes / 1e6, 1),
        "nasdaq_n": len(rows) if rows else 0,
        "inverse_n": len(inv),
    }
    (OUT_NQ / "run_done.json").write_text(json.dumps(summary, indent=2))
    (OUT_INV / "run_done.json").write_text(json.dumps(summary, indent=2))
    print(f"\nDONE nasdaq+inverses ok={_ok} skip={_skip} fail={_fail} mb={summary['mb']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
