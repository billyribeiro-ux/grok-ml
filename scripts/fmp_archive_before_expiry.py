#!/usr/bin/env python3
"""
Aether — Max-value FMP archive before subscription expiry (2026-07-12).

Goal: burn remaining Ultimate bandwidth on high-leverage dumps.
Does NOT mean the model must use every file — storage for later selection.

Focus:
  - Bulk CSVs (full market)
  - EOD bulk for many calendar days
  - Forex + crypto full lists + batch quotes + EOD for liquid pairs/coins
  - Extra bulk statement years

OUT: /Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/
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
# pull EOD bulk for last ~400 calendar days (skip weekends lightly)
EOD_DAYS = int(os.getenv("FMP_EOD_BULK_DAYS", "400"))

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry")
if not Path("/Volumes/LaCie/Aether").exists():
    OUT = ROOT / "data" / "fmp" / "archive_expiry"
OUT.mkdir(parents=True, exist_ok=True)

INTERVAL = float(os.getenv("FMP_ARCHIVE_INTERVAL", "0.05"))  # ~20 rps, under 3000/min
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherFMPArchive/1.0"})
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
    print(f"  OK {name} ({len(body)/1e6:.2f} MB) → {out.name}", flush=True)
    return True


def main() -> int:
    print("=" * 70, flush=True)
    print("FMP ARCHIVE BEFORE EXPIRY — MAX VALUE", flush=True)
    print(f"OUT={OUT}  EOD bulk days={EOD_DAYS}", flush=True)
    print("Forex+crypto included for archive; model need not use them.", flush=True)
    print("=" * 70, flush=True)
    (OUT / "run_start.json").write_text(
        json.dumps({"started": now(), "expiry_target": "2026-07-12", "out": str(OUT)}, indent=2)
    )

    # --- Full-market bulk dumps ---
    print("\n[1] BULK DUMPS", flush=True)
    for name, path, params in [
        ("rating_bulk", "rating-bulk", {}),
        ("dcf_bulk", "dcf-bulk", {}),
        ("scores_bulk", "scores-bulk", {}),
        ("key_metrics_ttm_bulk", "key-metrics-ttm-bulk", {}),
        ("ratios_ttm_bulk", "ratios-ttm-bulk", {}),
        ("peers_bulk", "peers-bulk", {}),
        ("price_target_summary_bulk", "price-target-summary-bulk", {}),
        ("upgrades_downgrades_consensus_bulk", "upgrades-downgrades-consensus-bulk", {}),
        ("income_2022", "income-statement-bulk", {"year": 2022, "period": "annual"}),
        ("income_2023", "income-statement-bulk", {"year": 2023, "period": "annual"}),
        ("income_2024", "income-statement-bulk", {"year": 2024, "period": "annual"}),
        ("income_2025", "income-statement-bulk", {"year": 2025, "period": "annual"}),
        ("balance_2022", "balance-sheet-statement-bulk", {"year": 2022, "period": "annual"}),
        ("balance_2023", "balance-sheet-statement-bulk", {"year": 2023, "period": "annual"}),
        ("balance_2024", "balance-sheet-statement-bulk", {"year": 2024, "period": "annual"}),
        ("balance_2025", "balance-sheet-statement-bulk", {"year": 2025, "period": "annual"}),
        ("cash_2022", "cash-flow-statement-bulk", {"year": 2022, "period": "annual"}),
        ("cash_2023", "cash-flow-statement-bulk", {"year": 2023, "period": "annual"}),
        ("cash_2024", "cash-flow-statement-bulk", {"year": 2024, "period": "annual"}),
        ("cash_2025", "cash-flow-statement-bulk", {"year": 2025, "period": "annual"}),
        ("income_q_2024", "income-statement-bulk", {"year": 2024, "period": "quarter"}),
        ("income_q_2025", "income-statement-bulk", {"year": 2025, "period": "quarter"}),
        ("balance_q_2024", "balance-sheet-statement-bulk", {"year": 2024, "period": "quarter"}),
        ("balance_q_2025", "balance-sheet-statement-bulk", {"year": 2025, "period": "quarter"}),
        ("cash_q_2024", "cash-flow-statement-bulk", {"year": 2024, "period": "quarter"}),
        ("cash_q_2025", "cash-flow-statement-bulk", {"year": 2025, "period": "quarter"}),
    ]:
        save(name, path, params, f"bulk/{name}.csv", min_bytes=100)

    # --- EOD bulk many days (huge value for scanners) ---
    print("\n[2] EOD BULK multi-day", flush=True)
    for i in range(EOD_DAYS):
        d = ASOF - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        ds = d.isoformat()
        save(f"eod_{ds}", "eod-bulk", {"date": ds}, f"eod_bulk/{ds}.csv", min_bytes=1000)

    # --- Forex + crypto archive ---
    print("\n[3] FOREX + CRYPTO ARCHIVE", flush=True)
    save("forex_list", "forex-list", {}, "forex/list.json")
    save("crypto_list", "cryptocurrency-list", {}, "crypto/list.json")
    save("batch_forex", "batch-forex-quotes", {}, "forex/batch_quotes.json")
    save("batch_crypto", "batch-crypto-quotes", {}, "crypto/batch_quotes.json")

    fx = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "AUDJPY", "CADJPY", "EURAUD",
    ]
    coins = [
        "BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "ADAUSD", "DOGEUSD",
        "AVAXUSD", "DOTUSD", "LINKUSD", "MATICUSD", "LTCUSD", "BCHUSD", "ATOMUSD",
    ]
    start = (ASOF - timedelta(days=365 * 5 + 2)).isoformat()
    end = ASOF.isoformat()
    for sym in fx:
        save(f"fx_eod_{sym}", "historical-price-eod/full", {"symbol": sym, "from": start, "to": end}, f"forex/eod/{sym}.json")
        save(f"fx_1h_{sym}", "historical-chart/1hour", {"symbol": sym, "from": (ASOF - timedelta(days=730)).isoformat(), "to": end}, f"forex/1hour/{sym}.json")
    for sym in coins:
        save(f"crypto_eod_{sym}", "historical-price-eod/full", {"symbol": sym, "from": start, "to": end}, f"crypto/eod/{sym}.json")
        save(f"crypto_1h_{sym}", "historical-chart/1hour", {"symbol": sym, "from": (ASOF - timedelta(days=730)).isoformat(), "to": end}, f"crypto/1hour/{sym}.json")

    # news pages
    for page in range(0, 25):
        save(f"forex_news_{page}", "news/forex", {"page": page, "limit": 100}, f"forex/news/p{page:02d}.json")
        save(f"crypto_news_{page}", "news/crypto", {"page": page, "limit": 100}, f"crypto/news/p{page:02d}.json")

    # --- Directory refreshes ---
    print("\n[4] DIRECTORY REFRESH", flush=True)
    for name, path, params in [
        ("stock_list", "stock-list", {}),
        ("etf_list", "etf-list", {}),
        ("actively_trading", "actively-trading-list", {}),
        ("financial_statement_symbols", "financial-statement-symbol-list", {}),
        ("index_list", "index-list", {}),
        ("commodities_list", "commodities-list", {}),
        ("delisted_0", "delisted-companies", {"page": 0}),
    ]:
        save(name, path, params, f"directory/{name}.json")

    summary = {"finished": now(), "ok": _ok, "fail": _fail, "skip": _skip, "out": str(OUT)}
    (OUT / "run_done.json").write_text(json.dumps(summary, indent=2))
    print(f"\nDONE archive ok={_ok} fail={_fail} skip={_skip}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
