#!/usr/bin/env python3
"""
Capture full end-of-day snapshot for 2026-07-10 from FMP Ultimate.

Saves under:
  /Volumes/LaCie/Aether/data/raw/fmp/eod_2026-07-10/
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

ASOF = date(2026, 7, 10)
DS = ASOF.isoformat()
BASE = "https://financialmodelingprep.com/stable"

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp") / f"eod_{DS}"
if not Path("/Volumes/LaCie/Aether").exists():
    OUT = ROOT / "data" / "fmp" / f"eod_{DS}"
OUT.mkdir(parents=True, exist_ok=True)

CORE = [
    "AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO",
    "SPY", "QQQ", "IWM", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA",
    "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS",
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLC", "XLRE",
    "SMH", "SOXX", "XBI", "KRE", "XOP",
]
INDICES = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^VIX1D", "^VVIX", "^TNX", "^MOVE", "^VXN", "^RVX"]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherEOD20260710/1.0"})
_ok = _fail = 0


def get(path: str, params: dict | None = None, retries: int = 12) -> tuple[int, bytes, str]:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=300)
            if r.status_code == 429:
                wait = min(180, 5 * (attempt + 1))
                print(f"  429 on {path} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(2 + attempt)
                continue
            return r.status_code, r.content, r.headers.get("content-type", "")
        except Exception as e:
            print(f"  err {path}: {e}", flush=True)
            time.sleep(2 + attempt)
    return 0, b"", ""


def save(name: str, path: str, params: dict | None, rel: str, min_bytes: int = 10) -> bool:
    global _ok, _fail
    out = OUT / rel
    if out.exists() and out.stat().st_size >= min_bytes:
        print(f"  skip {name}", flush=True)
        return True
    st, body, ctype = get(path, params)
    if st != 200 or len(body) < min_bytes:
        _fail += 1
        print(f"  MISS {name} status={st} len={len(body)}", flush=True)
        # save error body for debug
        if body:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.with_suffix(out.suffix + ".err").write_bytes(body)
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    if "csv" in ctype or (len(body) > 20 and body[:1] in (b'"', b"s", b"S") and b"," in body[:100]):
        if out.suffix != ".csv":
            out = out.with_suffix(".csv")
    out.write_bytes(body)
    _ok += 1
    print(f"  OK {name} ({len(body)/1e6:.2f} MB)", flush=True)
    return True


def main() -> int:
    print("=" * 70, flush=True)
    print(f"EOD SNAPSHOT {DS}", flush=True)
    print(f"OUT={OUT}", flush=True)
    print("=" * 70, flush=True)

    meta = {"as_of": DS, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "purpose": "end-of-day close capture"}
    (OUT / "meta_start.json").write_text(json.dumps(meta, indent=2))

    # 1) Full-market EOD bulk (retry hard — rate limited)
    print("\n[1] EOD BULK full market", flush=True)
    save("eod_bulk", "eod-bulk", {"date": DS}, f"eod_bulk_{DS}.csv", min_bytes=1000)

    # 2) Full quote batches (live-ish end of day)
    print("\n[2] BATCH QUOTES", flush=True)
    for name, path, params in [
        ("batch_index", "batch-index-quotes", {}),
        ("batch_etf", "batch-etf-quotes", {}),
        ("batch_commodity", "batch-commodity-quotes", {}),
        ("batch_forex", "batch-forex-quotes", {}),
        ("batch_crypto", "batch-crypto-quotes", {}),
        ("batch_nasdaq", "batch-exchange-quote", {"exchange": "NASDAQ"}),
        ("batch_nyse", "batch-exchange-quote", {"exchange": "NYSE"}),
        ("batch_amex", "batch-exchange-quote", {"exchange": "AMEX"}),
        ("batch_core", "batch-quote", {"symbols": ",".join(CORE)}),
        ("batch_indices_core", "batch-quote", {"symbols": ",".join(INDICES)}),
    ]:
        save(name, path, params, f"quotes/{name}.json")

    # 3) Core individual full quotes + aftermarket
    print("\n[3] CORE QUOTES + AFTERMARKET", flush=True)
    for sym in CORE + INDICES:
        safe = sym.replace("^", "")
        save(f"quote_{safe}", "quote", {"symbol": sym}, f"core/quote_{safe}.json")
        save(f"quote_short_{safe}", "quote-short", {"symbol": sym}, f"core/quote_short_{safe}.json")
        if not sym.startswith("^"):
            save(f"am_trade_{safe}", "aftermarket-trade", {"symbol": sym}, f"core/aftermarket_trade_{safe}.json")
            save(f"am_quote_{safe}", "aftermarket-quote", {"symbol": sym}, f"core/aftermarket_quote_{safe}.json")
            save(f"change_{safe}", "stock-price-change", {"symbol": sym}, f"core/change_{safe}.json")

    # 4) Market internals / breadth for the day
    print("\n[4] MARKET PERFORMANCE", flush=True)
    save("sector_perf", "sector-performance-snapshot", {"date": DS}, f"breadth/sector_{DS}.json")
    save("industry_perf", "industry-performance-snapshot", {"date": DS}, f"breadth/industry_{DS}.json")
    save("sector_pe", "sector-pe-snapshot", {"date": DS}, f"breadth/sector_pe_{DS}.json")
    save("industry_pe", "industry-pe-snapshot", {"date": DS}, f"breadth/industry_pe_{DS}.json")
    save("gainers", "biggest-gainers", {}, "breadth/gainers.json")
    save("losers", "biggest-losers", {}, "breadth/losers.json")
    save("actives", "most-actives", {}, "breadth/actives.json")

    # 5) Charts — last day multi-TF for core (captures full session)
    print("\n[5] INTRADAY CHARTS CORE (full session)", flush=True)
    for sym in CORE + ["^GSPC", "^VIX", "^RUT", "^IXIC"]:
        safe = sym.replace("^", "")
        for tf in ("1min", "5min", "15min", "30min", "1hour"):
            save(
                f"{safe}_{tf}",
                f"historical-chart/{tf}",
                {"symbol": sym, "from": DS, "to": DS},
                f"charts/{tf}/{safe}.json",
            )
        save(
            f"{safe}_eod_full",
            "historical-price-eod/full",
            {"symbol": sym, "from": DS, "to": DS},
            f"charts/eod/{safe}.json",
        )

    # 6) IWM holdings refresh + quote
    print("\n[6] IWM HOLDINGS + QUOTE", flush=True)
    save("iwm_holdings", "etf/holdings", {"symbol": "IWM"}, "iwm/holdings.json")
    save("iwm_info", "etf/info", {"symbol": "IWM"}, "iwm/info.json")
    save("iwm_quote", "quote", {"symbol": "IWM"}, "iwm/quote.json")

    # 7) News today pages
    print("\n[7] NEWS", flush=True)
    for page in range(0, 10):
        save(f"general_{page}", "news/general-latest", {"page": page, "limit": 100}, f"news/general_p{page}.json")
        save(f"fmp_{page}", "fmp-articles", {"page": page, "limit": 100}, f"news/fmp_p{page}.json")
    for sym in CORE[:12]:
        save(f"news_{sym}", "news/stock", {"symbols": sym, "limit": 50}, f"news/stock_{sym}.json")

    # 8) Bulk dumps dated today where applicable
    print("\n[8] BULK SNAPSHOTS", flush=True)
    for name, path, params in [
        ("rating_bulk", "rating-bulk", {}),
        ("dcf_bulk", "dcf-bulk", {}),
        ("scores_bulk", "scores-bulk", {}),
        ("key_metrics_ttm_bulk", "key-metrics-ttm-bulk", {}),
        ("ratios_ttm_bulk", "ratios-ttm-bulk", {}),
        ("peers_bulk", "peers-bulk", {}),
        ("price_target_summary_bulk", "price-target-summary-bulk", {}),
        ("upgrades_downgrades_consensus_bulk", "upgrades-downgrades-consensus-bulk", {}),
    ]:
        save(name, path, params, f"bulk/{name}.csv", min_bytes=100)

    # 9) Retry eod-bulk last if earlier failed
    print("\n[9] EOD BULK RETRY", flush=True)
    save("eod_bulk_retry", "eod-bulk", {"date": DS}, f"eod_bulk_{DS}.csv", min_bytes=1000)

    done = {
        "as_of": DS,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": _ok,
        "fail": _fail,
        "out": str(OUT),
    }
    (OUT / "meta_done.json").write_text(json.dumps(done, indent=2))
    print(f"\nDONE EOD {DS} ok={_ok} fail={_fail}", flush=True)
    print(f"Saved: {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    import time
    import json

    sys.exit(main())
