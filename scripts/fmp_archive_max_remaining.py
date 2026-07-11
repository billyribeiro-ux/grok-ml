#!/usr/bin/env python3
"""
Aether — Remaining high-value FMP archive before Ultimate expires 2026-07-12.

Context: Fri 2026-07-10 last US session; Sun 7/12 sub dies; Mon 7/13 opens without us.
Pull everything still missing that is bulk/high-leverage. Skip-if-exists. LaCie only.

Does NOT re-download full eod-bulk (see fmp_eod_bulk_parallel.py).
"""

from __future__ import annotations

import json
import os
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

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry")
if not Path("/Volumes/LaCie/Aether").exists():
    raise SystemExit("LaCie not mounted — refuse")
OUT.mkdir(parents=True, exist_ok=True)

INTERVAL = float(os.getenv("FMP_ARCHIVE_INTERVAL", "0.06"))
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherFMPMaxRemaining/1.0"})
_last = 0.0
_ok = _skip = _fail = 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def throttle() -> None:
    global _last
    dt = time.time() - _last
    if dt < INTERVAL:
        time.sleep(INTERVAL - dt)
    _last = time.time()


def fetch(path: str, params: dict | None = None, retries: int = 10) -> tuple[int, bytes, str]:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        throttle()
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=600)
            if r.status_code == 429:
                time.sleep(min(120, 2 ** min(attempt, 6)))
                continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            return r.status_code, r.content, r.headers.get("content-type", "")
        except Exception:
            time.sleep(1 + attempt)
    return 0, b"", ""


def save(name: str, path: str, params: dict | None, rel: str, min_bytes: int = 50) -> bool:
    global _ok, _skip, _fail
    out = OUT / rel
    if out.exists() and out.stat().st_size >= min_bytes:
        _skip += 1
        return True
    st, body, ctype = fetch(path, params)
    if st != 200 or len(body) < min_bytes:
        _fail += 1
        print(f"  MISS {name} {st} {len(body)}", flush=True)
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    if "csv" in ctype or (b"," in body[:80] and body[:1] in (b'"', b"s", b"S", b"0", b"1", b"A")):
        if out.suffix != ".csv":
            out = out.with_suffix(".csv")
    elif out.suffix not in (".json", ".csv"):
        try:
            json.loads(body)
            out = out.with_suffix(".json")
        except Exception:
            pass
    out.write_bytes(body)
    _ok += 1
    print(f"  OK {name} ({len(body)/1e6:.2f} MB)", flush=True)
    return True


def main() -> int:
    print("=" * 70, flush=True)
    print("FMP MAX REMAINING ARCHIVE (pre-expiry weekend)", flush=True)
    print(f"OUT={OUT}  as_of={ASOF}", flush=True)
    print("=" * 70, flush=True)
    (OUT / "max_remaining_start.json").write_text(
        json.dumps({"started": now(), "as_of": ASOF.isoformat(), "expiry": "2026-07-12"}, indent=2)
    )

    # --- Extra bulk financials years (archive already has 2022-2025) ---
    print("\n[1] BULK STATEMENTS deeper years + more quarters", flush=True)
    for year in (2019, 2020, 2021, 2026):
        for stem, ep in [
            ("income", "income-statement-bulk"),
            ("balance", "balance-sheet-statement-bulk"),
            ("cash", "cash-flow-statement-bulk"),
        ]:
            save(f"{stem}_{year}", ep, {"year": year, "period": "annual"}, f"bulk/{stem}_{year}.csv", min_bytes=100)
    for year in (2022, 2023, 2026):
        for stem, ep in [
            ("income_q", "income-statement-bulk"),
            ("balance_q", "balance-sheet-statement-bulk"),
            ("cash_q", "cash-flow-statement-bulk"),
        ]:
            save(f"{stem}_{year}", ep, {"year": year, "period": "quarter"}, f"bulk/{stem}_{year}.csv", min_bytes=100)

    # more bulk product dumps if available
    print("\n[2] EXTRA BULK PRODUCTS", flush=True)
    for name, path, params in [
        ("earnings_surprises_bulk", "earnings-surprises-bulk", {}),
        ("stock_peers_bulk", "stock-peers-bulk", {}),
        ("profile_bulk", "profile-bulk", {}),
        ("stock_rating_bulk", "rating-bulk", {}),
        ("financial_scores_bulk", "scores-bulk", {}),
        ("key_metrics_bulk_2024", "key-metrics-bulk", {"year": 2024}),
        ("key_metrics_bulk_2025", "key-metrics-bulk", {"year": 2025}),
        ("ratios_bulk_2024", "ratios-bulk", {"year": 2024}),
        ("ratios_bulk_2025", "ratios-bulk", {"year": 2025}),
    ]:
        save(name, path, params, f"bulk/{name}.csv", min_bytes=50)

    # --- Directory / universe freeze as of Friday close ---
    print("\n[3] DIRECTORY FREEZE (as of last session)", flush=True)
    for name, path, params in [
        ("stock_list", "stock-list", {}),
        ("etf_list", "etf-list", {}),
        ("actively_trading", "actively-trading-list", {}),
        ("financial_statement_symbols", "financial-statement-symbol-list", {}),
        ("index_list", "index-list", {}),
        ("commodities_list", "commodities-list", {}),
        ("forex_list", "forex-list", {}),
        ("crypto_list", "cryptocurrency-list", {}),
        ("available_exchanges", "available-exchanges", {}),
        ("available_sectors", "available-sectors", {}),
        ("available_industries", "available-industries", {}),
        ("cik_list", "cik-list", {}),
        ("symbol_changes", "symbol-change", {}),
    ]:
        save(name, path, params, f"directory/{name}.json")
    for page in range(0, 20):
        save(f"delisted_{page}", "delisted-companies", {"page": page}, f"directory/delisted_p{page:02d}.json")

    # --- Live Friday batch quotes freeze (already have eod snapshot; refresh) ---
    print("\n[4] BATCH QUOTE FREEZE", flush=True)
    for name, path in [
        ("batch_etf", "batch-etf-quotes"),
        ("batch_index", "batch-index-quotes"),
        ("batch_forex", "batch-forex-quotes"),
        ("batch_crypto", "batch-crypto-quotes"),
        ("batch_commodity", "batch-commodity-quotes"),
        ("batch_mutualfund", "batch-mutualfund-quotes"),
        ("batch_exchange_nasdaq", "batch-exchange-quote"),
        ("batch_exchange_nyse", "batch-exchange-quote"),
        ("batch_exchange_amex", "batch-exchange-quote"),
    ]:
        params = {}
        if "nasdaq" in name:
            params = {"exchange": "NASDAQ"}
        elif "nyse" in name:
            params = {"exchange": "NYSE"}
        elif "amex" in name:
            params = {"exchange": "AMEX"}
        save(name, path, params, f"quotes/{name}.json")

    # --- Market movers / breadth freeze ---
    print("\n[5] BREADTH / MOVERS FREEZE", flush=True)
    for name, path, params in [
        ("gainers", "biggest-gainers", {}),
        ("losers", "biggest-losers", {}),
        ("actives", "most-actives", {}),
        ("sector_perf", "sector-performance-snapshot", {}),
        ("industry_perf", "industry-performance-snapshot", {}),
        ("sector_pe", "sector-pe-snapshot", {}),
        ("industry_pe", "industry-pe-snapshot", {}),
    ]:
        save(name, path, params, f"breadth/{name}.json")

    # --- Forex + crypto (archive value; multi-strategy later) ---
    print("\n[6] FOREX + CRYPTO 5Y EOD + 1H", flush=True)
    save("forex_list2", "forex-list", {}, "forex/list.json")
    save("crypto_list2", "cryptocurrency-list", {}, "crypto/list.json")
    fx = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "AUDJPY", "CADJPY", "EURAUD",
        "USDMXN", "USDZAR", "USDCNH", "EURSEK", "USDNOK", "USDTRY",
    ]
    coins = [
        "BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "ADAUSD", "DOGEUSD",
        "AVAXUSD", "DOTUSD", "LINKUSD", "MATICUSD", "LTCUSD", "BCHUSD", "ATOMUSD",
        "NEARUSD", "APTUSD", "ARBUSD", "OPUSD", "SUIUSD", "PEPEUSD",
    ]
    start = (ASOF - timedelta(days=365 * 5 + 2)).isoformat()
    end = ASOF.isoformat()
    for sym in fx:
        save(f"fx_eod_{sym}", "historical-price-eod/full", {"symbol": sym, "from": start, "to": end}, f"forex/eod/{sym}.json")
        save(f"fx_1h_{sym}", "historical-chart/1hour", {"symbol": sym, "from": (ASOF - timedelta(days=730)).isoformat(), "to": end}, f"forex/1hour/{sym}.json")
    for sym in coins:
        save(f"crypto_eod_{sym}", "historical-price-eod/full", {"symbol": sym, "from": start, "to": end}, f"crypto/eod/{sym}.json")
        save(f"crypto_1h_{sym}", "historical-chart/1hour", {"symbol": sym, "from": (ASOF - timedelta(days=730)).isoformat(), "to": end}, f"crypto/1hour/{sym}.json")

    for page in range(0, 30):
        save(f"forex_news_{page}", "news/forex", {"page": page, "limit": 100}, f"forex/news/p{page:02d}.json")
        save(f"crypto_news_{page}", "news/crypto", {"page": page, "limit": 100}, f"crypto/news/p{page:02d}.json")
        save(f"stock_news_{page}", "news/stock", {"page": page, "limit": 100}, f"news/stock/p{page:02d}.json")
        save(f"general_news_{page}", "news/general-latest", {"page": page, "limit": 100}, f"news/general/p{page:02d}.json")
        save(f"press_{page}", "news/press-releases-latest", {"page": page, "limit": 100}, f"news/press/p{page:02d}.json")

    # --- Calendars as-of Friday ---
    print("\n[7] CALENDARS", flush=True)
    for name, path, params in [
        ("earnings_calendar", "earnings-calendar", {"from": (ASOF - timedelta(days=30)).isoformat(), "to": (ASOF + timedelta(days=90)).isoformat()}),
        ("ipo_calendar", "ipos-calendar", {"from": (ASOF - timedelta(days=90)).isoformat(), "to": (ASOF + timedelta(days=90)).isoformat()}),
        ("splits_calendar", "splits-calendar", {"from": (ASOF - timedelta(days=90)).isoformat(), "to": (ASOF + timedelta(days=90)).isoformat()}),
        ("dividends_calendar", "dividends-calendar", {"from": (ASOF - timedelta(days=30)).isoformat(), "to": (ASOF + timedelta(days=90)).isoformat()}),
        ("economic_calendar", "economic-calendar", {"from": (ASOF - timedelta(days=30)).isoformat(), "to": (ASOF + timedelta(days=90)).isoformat()}),
    ]:
        save(name, path, params, f"calendars/{name}.json")

    summary = {"finished": now(), "ok": _ok, "fail": _fail, "skip": _skip, "out": str(OUT)}
    (OUT / "max_remaining_done.json").write_text(json.dumps(summary, indent=2))
    print(f"\nDONE max remaining ok={_ok} fail={_fail} skip={_skip}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
