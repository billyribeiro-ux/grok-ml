#!/usr/bin/env python3
"""
Aether — High-value FMP bandwidth burn before Ultimate expiry (~2026-07-12).

User meter: ~22/150 GB used → burn remaining on data we still need.
Writes ONLY to LaCie. Skip-if-exists. Patient 429 backoff.

Priority:
  1) Bulk financials deeper years (cheap GB, huge fundamental history)
  2) Wide calendars, float, congress, treasury, directories
  3) Commodity + index EOD deep history
  4) Core/IWM enrichment (mkt cap, estimates, grades, growth, ETF holdings)
  5) Full-market eod-bulk 2015-01-01 → 2018-12-31 (extends 2019+ archive)
  6) Liquid 5-min charts for core day-trade names (last ~2y)

OUT: /Volumes/LaCie/Aether/data/raw/fmp/bandwidth_burn/
     + archive_expiry/eod_bulk/ (2015-2018 days)
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

if not Path("/Volumes/LaCie/Aether").exists():
    raise SystemExit("LaCie not mounted — refuse")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/bandwidth_burn")
EOD_OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk")
OUT.mkdir(parents=True, exist_ok=True)
EOD_OUT.mkdir(parents=True, exist_ok=True)

SLEEP = float(os.getenv("FMP_BURN_SLEEP", "0.4"))
EOD_SLEEP = float(os.getenv("FMP_EOD_SLEEP", "1.5"))
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherFMPBandwidthBurn/1.0"})

CORE = [
    "AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO",
    "SPY", "QQQ", "IWM", "DIA", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA",
    "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS",
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLC", "XLRE",
    "SMH", "SOXX", "XBI", "KRE", "XOP", "TLT", "HYG", "GLD", "USO", "UVXY", "SVXY",
]
INDICES = [
    "^GSPC", "^DJI", "^IXIC", "^RUT", "^NYA",
    "^VIX", "^VIX1D", "^VIX9D", "^VIX3M", "^VIX6M", "^VIX1Y", "^VVIX",
    "^VXN", "^RVX", "^VXD", "^MOVE", "^TNX", "^IRX", "^FVX", "^TYX",
    "^OVX", "^GVZ", "^COR1M", "^COR3M", "^COR6M",
]
COMMODITIES = [
    "GCUSD", "SIUSD", "CLUSD", "BZUSD", "NGUSD", "HGUSD",
    "ESUSD", "NQUSD", "YMUSD", "RTYUSD", "DXUSD",
    "ZBUSD", "ZNUSD", "ZFUSD", "ZTUSD", "PLUSD", "PAUSD",
]
ECON = [
    "GDP", "realGDP", "realGDPPerCapita", "federalFunds", "CPI", "inflationRate",
    "unemploymentRate", "totalNonfarmPayroll", "initialClaims", "retailSales",
    "consumerSentiment", "industrialProductionTotalIndex",
    "smoothedUSRecessionProbabilities",
    "15YearFixedRateMortgageAverage", "30YearFixedRateMortgageAverage",
    "newPrivatelyOwnedHousingUnitsStartedTotalUnits",
]

_ok = _skip = _fail = 0
_bytes = 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get(path: str, params: dict | None = None, retries: int = 14) -> tuple[int, bytes]:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        time.sleep(SLEEP if attempt == 0 else 0)
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=600)
            if r.status_code == 429:
                wait = min(240, 4 * (2 ** min(attempt, 6)))
                print(f"  429 {path} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(2 + attempt)
                continue
            return r.status_code, r.content
        except Exception as e:
            print(f"  err {path}: {e}", flush=True)
            time.sleep(2 + attempt)
    return 0, b""


def save(name: str, path: str, params: dict | None, rel: Path, min_bytes: int = 40) -> bool:
    global _ok, _skip, _fail, _bytes
    out = OUT / rel
    if out.exists() and out.stat().st_size >= min_bytes:
        _skip += 1
        return True
    st, body = get(path, params)
    if st != 200 or len(body) < min_bytes:
        _fail += 1
        print(f"  MISS {name} status={st} len={len(body)}", flush=True)
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    # extension
    if out.suffix not in (".json", ".csv"):
        if body[:1] in (b'"', b"s", b"S") and b"," in body[:120]:
            out = out.with_suffix(".csv")
        else:
            try:
                json.loads(body)
                out = out.with_suffix(".json")
            except Exception:
                pass
    out.write_bytes(body)
    _ok += 1
    _bytes += len(body)
    print(f"  OK {name} ({len(body)/1e6:.2f} MB)", flush=True)
    return True


def phase_bulk_statements() -> None:
    print("\n[1] BULK STATEMENTS 2015-2018 + more quarters", flush=True)
    for year in range(2015, 2019):
        for stem, ep in [
            ("income", "income-statement-bulk"),
            ("balance", "balance-sheet-statement-bulk"),
            ("cash", "cash-flow-statement-bulk"),
        ]:
            save(f"{stem}_{year}", ep, {"year": year, "period": "annual"}, Path(f"bulk/{stem}_{year}.csv"), 500)
    for year in (2018, 2019, 2020, 2021):
        for stem, ep in [
            ("income_q", "income-statement-bulk"),
            ("balance_q", "balance-sheet-statement-bulk"),
            ("cash_q", "cash-flow-statement-bulk"),
        ]:
            save(f"{stem}_{year}", ep, {"year": year, "period": "quarter"}, Path(f"bulk/{stem}_{year}.csv"), 500)
    # refresh TTM / scores
    for name, path in [
        ("rating_bulk", "rating-bulk"),
        ("dcf_bulk", "dcf-bulk"),
        ("scores_bulk", "scores-bulk"),
        ("key_metrics_ttm_bulk", "key-metrics-ttm-bulk"),
        ("ratios_ttm_bulk", "ratios-ttm-bulk"),
        ("peers_bulk", "peers-bulk"),
        ("price_target_summary_bulk", "price-target-summary-bulk"),
        ("upgrades_downgrades_consensus_bulk", "upgrades-downgrades-consensus-bulk"),
    ]:
        save(name, path, {}, Path(f"bulk/{name}.csv"), 100)


def phase_calendars_macro() -> None:
    print("\n[2] CALENDARS + MACRO + FLOAT + CONGRESS", flush=True)
    # chunk earnings calendar by year (API may cap range)
    for y0, y1 in [(2015, 2017), (2017, 2019), (2019, 2021), (2021, 2023), (2023, 2025), (2025, 2026)]:
        fr = f"{y0}-01-01"
        to = f"{min(y1, 2026)}-07-10" if y1 >= 2026 else f"{y1}-12-31"
        if date.fromisoformat(fr) > ASOF:
            continue
        to = min(date.fromisoformat(to), ASOF).isoformat()
        save(f"earnings_{fr}_{to}", "earnings-calendar", {"from": fr, "to": to}, Path(f"calendars/earnings_{fr}_{to}.json"))
        save(f"dividends_{fr}_{to}", "dividends-calendar", {"from": fr, "to": to}, Path(f"calendars/dividends_{fr}_{to}.json"))
        save(f"splits_{fr}_{to}", "splits-calendar", {"from": fr, "to": to}, Path(f"calendars/splits_{fr}_{to}.json"))
        save(f"ipos_{fr}_{to}", "ipos-calendar", {"from": fr, "to": to}, Path(f"calendars/ipos_{fr}_{to}.json"))
        save(f"econcal_{fr}_{to}", "economic-calendar", {"from": fr, "to": to}, Path(f"calendars/economic_{fr}_{to}.json"))

    save("treasury_2015_2026", "treasury-rates", {"from": "2015-01-01", "to": ASOF.isoformat()}, Path("macro/treasury_rates.json"))
    for name in ECON:
        save(f"econ_{name}", "economic-indicators", {"name": name}, Path(f"macro/econ/{name}.json"), 20)

    save("shares_float_all", "shares-float-all", {}, Path("reference/shares_float_all.json"), 50)
    save("stock_list", "stock-list", {}, Path("reference/stock_list.json"), 1000)
    save("etf_list", "etf-list", {}, Path("reference/etf_list.json"), 100)
    save("index_list", "index-list", {}, Path("reference/index_list.json"), 50)
    save("commodities_list", "commodities-list", {}, Path("reference/commodities_list.json"), 20)
    save("forex_list", "forex-list", {}, Path("reference/forex_list.json"), 20)
    save("crypto_list", "cryptocurrency-list", {}, Path("reference/crypto_list.json"), 20)
    save("actively_trading", "actively-trading-list", {}, Path("reference/actively_trading.json"), 100)
    for page in range(0, 30):
        save(f"delisted_{page}", "delisted-companies", {"page": page}, Path(f"reference/delisted/p{page:02d}.json"), 20)

    for page in range(0, 50):
        save(f"insider_{page}", "insider-trading/latest", {"page": page, "limit": 100}, Path(f"flow/insider/p{page:02d}.json"), 30)
    for page in range(0, 30):
        save(f"senate_{page}", "senate-latest", {"page": page}, Path(f"flow/senate/p{page:02d}.json"), 20)
        save(f"house_{page}", "house-latest", {"page": page}, Path(f"flow/house/p{page:02d}.json"), 20)

    save("batch_nasdaq", "batch-exchange-quote", {"exchange": "NASDAQ"}, Path("quotes/batch_nasdaq.json"), 1000)
    save("batch_nyse", "batch-exchange-quote", {"exchange": "NYSE"}, Path("quotes/batch_nyse.json"), 1000)
    save("batch_amex", "batch-exchange-quote", {"exchange": "AMEX"}, Path("quotes/batch_amex.json"), 100)
    save("batch_etf", "batch-etf-quotes", {}, Path("quotes/batch_etf.json"), 100)
    save("batch_index", "batch-index-quotes", {}, Path("quotes/batch_index.json"), 50)
    save("batch_commodity", "batch-commodity-quotes", {}, Path("quotes/batch_commodity.json"), 20)
    save("batch_forex", "batch-forex-quotes", {}, Path("quotes/batch_forex.json"), 50)
    save("batch_crypto", "batch-crypto-quotes", {}, Path("quotes/batch_crypto.json"), 50)


def phase_commodities_indices() -> None:
    print("\n[3] COMMODITIES + INDICES EOD 2015→2026-07-10", flush=True)
    start = "2015-01-01"
    end = ASOF.isoformat()
    for sym in COMMODITIES:
        save(f"cmdty_{sym}", "historical-price-eod/full", {"symbol": sym, "from": start, "to": end}, Path(f"commodities/eod/{sym}.json"), 100)
        save(f"cmdty1h_{sym}", "historical-chart/1hour", {"symbol": sym, "from": "2023-01-01", "to": end}, Path(f"commodities/1hour/{sym}.json"), 50)
    for sym in INDICES:
        safe = sym.replace("^", "")
        save(f"idx_{safe}", "historical-price-eod/full", {"symbol": sym, "from": start, "to": end}, Path(f"indices/eod/{safe}.json"), 100)
        save(f"idx1h_{safe}", "historical-chart/1hour", {"symbol": sym, "from": "2023-01-01", "to": end}, Path(f"indices/1hour/{safe}.json"), 50)

    # full index-list symbols eod (archive value)
    st, body = get("index-list", {})
    if st == 200 and body:
        try:
            idx = json.loads(body)
            (OUT / "reference/index_list.json").write_bytes(body)
            symbols = []
            if isinstance(idx, list):
                for row in idx:
                    s = row.get("symbol") if isinstance(row, dict) else None
                    if s:
                        symbols.append(s)
            print(f"  index-list symbols={len(symbols)} — pulling EOD for each", flush=True)
            for i, sym in enumerate(symbols):
                safe = str(sym).replace("^", "").replace("/", "_")
                save(f"allidx_{safe}", "historical-price-eod/full", {"symbol": sym, "from": "2019-01-01", "to": end}, Path(f"indices/all_eod/{safe}.json"), 80)
                if (i + 1) % 25 == 0:
                    print(f"  ... indices {i+1}/{len(symbols)} ok={_ok}", flush=True)
        except Exception as e:
            print(f"  index-list parse fail: {e}", flush=True)


def phase_core_enrichment() -> None:
    print("\n[4] CORE ENRICHMENT (fundamentals/flow for trading universe)", flush=True)
    start = "2015-01-01"
    end = ASOF.isoformat()
    for sym in CORE:
        base = Path(f"enrichment/{sym}")
        save(f"{sym}_profile", "profile", {"symbol": sym}, base / "profile.json", 50)
        save(f"{sym}_mcap", "historical-market-capitalization", {"symbol": sym, "from": start, "to": end}, base / "market_cap.json", 30)
        save(f"{sym}_float", "shares-float", {"symbol": sym}, base / "float.json", 10)
        save(f"{sym}_key_metrics", "key-metrics", {"symbol": sym, "limit": 120}, base / "key_metrics.json", 50)
        save(f"{sym}_ratios", "ratios", {"symbol": sym, "limit": 120}, base / "ratios.json", 50)
        save(f"{sym}_growth", "financial-growth", {"symbol": sym, "limit": 80}, base / "financial_growth.json", 20)
        save(f"{sym}_income_g", "income-statement-growth", {"symbol": sym, "limit": 80}, base / "income_growth.json", 20)
        save(f"{sym}_estimates", "analyst-estimates", {"symbol": sym, "period": "annual"}, base / "analyst_estimates.json", 20)
        save(f"{sym}_estimates_q", "analyst-estimates", {"symbol": sym, "period": "quarter"}, base / "analyst_estimates_q.json", 20)
        save(f"{sym}_grades", "grades-historical", {"symbol": sym}, base / "grades_historical.json", 20)
        save(f"{sym}_pt", "price-target-consensus", {"symbol": sym}, base / "price_target_consensus.json", 10)
        save(f"{sym}_owner", "owner-earnings", {"symbol": sym}, base / "owner_earnings.json", 10)
        save(f"{sym}_ev", "enterprise-values", {"symbol": sym}, base / "enterprise_values.json", 10)
        save(f"{sym}_eod", "historical-price-eod/full", {"symbol": sym, "from": start, "to": end}, base / "eod.json", 200)
        for tech, extra in [
            ("rsi", {"periodLength": 14}),
            ("ema", {"periodLength": 20}),
            ("sma", {"periodLength": 50}),
            ("adx", {"periodLength": 14}),
            ("williams", {"periodLength": 14}),
        ]:
            save(
                f"{sym}_{tech}",
                f"technical-indicators/{tech}",
                {"symbol": sym, "timeframe": "1day", "from": "2019-01-01", "to": end, **extra},
                base / f"tech_{tech}.json",
                50,
            )
        # news pages
        for page in range(0, 5):
            save(f"{sym}_news_{page}", "news/stock", {"symbols": sym, "page": page, "limit": 100}, base / f"news_p{page}.json", 20)

    for sym in ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "SMH", "SQQQ", "TZA"]:
        base = Path(f"etf/{sym}")
        save(f"{sym}_etf_info", "etf/info", {"symbol": sym}, base / "info.json", 20)
        save(f"{sym}_etf_holdings", "etf/holdings", {"symbol": sym}, base / "holdings.json", 50)
        save(f"{sym}_etf_sector", "etf/sector-weightings", {"symbol": sym}, base / "sector_weightings.json", 10)
        save(f"{sym}_etf_country", "etf/country-weightings", {"symbol": sym}, base / "country_weightings.json", 10)


def phase_intraday_liquid() -> None:
    print("\n[5] INTRADAY 5min (2y) + 1min (90d) core liquid", flush=True)
    end = ASOF.isoformat()
    start_5m = (ASOF - timedelta(days=730)).isoformat()
    start_1m = (ASOF - timedelta(days=90)).isoformat()
    liquid = [
        "SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO",
        "SQQQ", "TZA", "SPXU", "SH", "UVXY", "SMH", "XLK", "XLF",
        "^GSPC", "^VIX", "^VIX1D", "^RUT", "^IXIC",
    ]
    for sym in liquid:
        safe = sym.replace("^", "")
        save(f"5m_{safe}", "historical-chart/5min", {"symbol": sym, "from": start_5m, "to": end}, Path(f"intraday/5min/{safe}.json"), 100)
        save(f"1m_{safe}", "historical-chart/1min", {"symbol": sym, "from": start_1m, "to": end}, Path(f"intraday/1min/{safe}.json"), 100)


def phase_eod_bulk_2015_2018() -> None:
    print("\n[6] EOD-BULK full market 2015-01-01 → 2018-12-31", flush=True)
    start = date(2015, 1, 1)
    end = date(2018, 12, 31)
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    days.sort(reverse=True)  # newest first within window
    present = sum(1 for x in days if (EOD_OUT / f"{x.isoformat()}.csv").exists() and (EOD_OUT / f"{x.isoformat()}.csv").stat().st_size > 1000)
    print(f"  weekdays={len(days)} present={present} todo={len(days)-present}", flush=True)
    ok = skip = fail = empty = 0
    for d in days:
        path = EOD_OUT / f"{d.isoformat()}.csv"
        if path.exists() and path.stat().st_size > 1000:
            skip += 1
            continue
        attempt = 0
        while attempt < 30:
            attempt += 1
            try:
                r = SESSION.get(
                    f"{BASE}/eod-bulk",
                    params={"date": d.isoformat(), "apikey": API_KEY},
                    timeout=300,
                )
                if r.status_code == 429:
                    wait = min(300, 5 * (2 ** min(attempt - 1, 6)))
                    print(f"  429 eod {d} wait {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                if r.status_code == 200 and len(r.content) > 1000:
                    tmp = path.with_suffix(".csv.partial")
                    tmp.write_bytes(r.content)
                    tmp.replace(path)
                    ok += 1
                    print(f"  OK eod {d} ({len(r.content)/1e6:.2f} MB) ok={ok} skip={skip}", flush=True)
                    time.sleep(EOD_SLEEP)
                    break
                if r.status_code == 200:
                    empty += 1
                    break
                fail += 1
                print(f"  FAIL eod {d} {r.status_code}", flush=True)
                break
            except Exception as e:
                time.sleep(2 + attempt)
                if attempt >= 30:
                    fail += 1
                    print(f"  FAIL eod {d} {e}", flush=True)
        else:
            fail += 1
    print(f"  eod 2015-2018 done ok={ok} skip={skip} empty={empty} fail={fail}", flush=True)


def phase_news_deep() -> None:
    print("\n[7] NEWS deep pages", flush=True)
    for page in range(0, 40):
        save(f"gen_{page}", "news/general-latest", {"page": page, "limit": 100}, Path(f"news/general/p{page:02d}.json"), 30)
        save(f"fmpn_{page}", "news/fmp-articles", {"page": page, "limit": 20}, Path(f"news/fmp/p{page:02d}.json"), 20)
        save(f"press_{page}", "news/press-releases-latest", {"page": page, "limit": 100}, Path(f"news/press/p{page:02d}.json"), 20)
        save(f"stockn_{page}", "news/stock", {"page": page, "limit": 100}, Path(f"news/stock/p{page:02d}.json"), 20)


def main() -> int:
    print("=" * 70, flush=True)
    print("FMP BANDWIDTH BURN — high-value pre-expiry", flush=True)
    print(f"OUT={OUT}", flush=True)
    print(f"EOD_OUT={EOD_OUT}", flush=True)
    print("=" * 70, flush=True)
    (OUT / "run_start.json").write_text(json.dumps({"started": now(), "as_of": ASOF.isoformat()}, indent=2))

    phase_bulk_statements()
    phase_calendars_macro()
    phase_commodities_indices()
    phase_core_enrichment()
    phase_intraday_liquid()
    phase_news_deep()
    phase_eod_bulk_2015_2018()

    summary = {
        "finished": now(),
        "ok": _ok,
        "skip": _skip,
        "fail": _fail,
        "bytes": _bytes,
        "mb": round(_bytes / 1e6, 1),
        "out": str(OUT),
    }
    (OUT / "run_done.json").write_text(json.dumps(summary, indent=2))
    print(f"\nDONE burn ok={_ok} skip={_skip} fail={_fail} mb={summary['mb']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
