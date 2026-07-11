#!/usr/bin/env python3
"""
Aether — FMP Ultimate MAX download (best-of-best + everything useful on plan).

NO Databento. Uses FMP Ultimate: ~150GB bandwidth, 3000 calls/min.
Throttle ~0.04s (~1500/min) — safe under 3000/min.

Writes to:
  /Volumes/LaCie/Aether/data/raw/fmp/ultimate/   (preferred)
  fallback: ./data/fmp/ultimate/
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
START = ASOF - timedelta(days=365 * 5 + 2)

LACIE = Path("/Volumes/LaCie/Aether/data/raw/fmp/ultimate")
LOCAL = ROOT / "data" / "fmp" / "ultimate"
DATA = LACIE if Path("/Volumes/LaCie/Aether").exists() else LOCAL
DATA.mkdir(parents=True, exist_ok=True)

# Core Aether equities (deep everything)
STOCKS = ["AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO"]
ETFS_CORE = ["SPY", "QQQ", "IWM", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA"]
INDICES = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^VIX1D", "^VVIX", "^TNX", "^MOVE"]
ALL_EQUITY = STOCKS + ETFS_CORE + [
    "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS",
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLC", "XLRE",
    "SMH", "SOXX", "XBI", "KRE", "XOP",
]

# Macro futures / FX (best for regime decode)
COMMODITIES = [
    "ESUSD", "NQUSD", "YMUSD", "RTYUSD", "CLUSD", "BZUSD", "NGUSD",
    "GCUSD", "SIUSD", "HGUSD", "DXUSD", "ZBUSD", "ZNUSD", "ZFUSD", "ZTUSD",
    "PLUSD", "PAUSD", "HOUSD", "RBUSD",
]
FOREX = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURJPY", "GBPJPY", "EURGBP",
]
COT_SYMBOLS = ["VX", "ES", "NQ", "YM", "CL", "GC", "SI", "ZN", "ZB"]

ECON = [
    "GDP", "realGDP", "federalFunds", "CPI", "inflationRate", "unemploymentRate",
    "totalNonfarmPayroll", "initialClaims", "retailSales", "consumerSentiment",
    "industrialProductionTotalIndex", "smoothedUSRecessionProbabilities",
    "15YearFixedRateMortgageAverage", "30YearFixedRateMortgageAverage",
]

TECH_DAILY = [
    ("rsi", {"periodLength": 14}),
    ("ema", {"periodLength": 20}),
    ("sma", {"periodLength": 20}),
    ("adx", {"periodLength": 14}),
    ("williams", {"periodLength": 14}),
    ("standarddeviation", {"periodLength": 20}),
]
TECH_5MIN = [
    ("rsi", {"periodLength": 14}),
    ("ema", {"periodLength": 20}),
    ("sma", {"periodLength": 20}),
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherFMPUltimate/1.0"})
MIN_INTERVAL = 0.04  # ~1500/min
_last = 0.0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def throttle() -> None:
    global _last
    dt = time.time() - _last
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last = time.time()


def get_json(path: str, params: dict | None = None, retries: int = 4) -> Any:
    params = {**(params or {}), "apikey": API_KEY}
    last = None
    for attempt in range(retries):
        throttle()
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=120)
            if r.status_code == 429:
                time.sleep(2 + attempt)
                continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            if r.status_code in (404, 400):
                return None
            if r.status_code != 200:
                return None
            if not r.text.strip():
                return None
            return r.json()
        except Exception as e:
            last = e
            time.sleep(1 + attempt)
    return None


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def pull_save(name: str, path: str, params: dict | None, out: Path) -> bool:
    data = get_json(path, params)
    if data is None:
        return False
    if isinstance(data, list) and len(data) == 0:
        return False
    save_json(data, out)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        try:
            save_parquet(pd.DataFrame(data), out.with_suffix(".parquet"))
        except Exception:
            pass
    print(f"  OK {name} -> {out.name} ({len(data) if isinstance(data, list) else 'obj'})", flush=True)
    return True


def download_eod(sym: str, out_dir: Path) -> int:
    out = out_dir / f"{sym.replace('^','')}.parquet"
    if out.exists() and out.stat().st_size > 1000:
        return -1  # skip existing
    data = get_json(
        "historical-price-eod/full",
        {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
    )
    if not isinstance(data, list) or not data:
        return 0
    df = pd.DataFrame(data)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    save_parquet(df, out)
    return len(df)


def download_intraday_5m(sym: str, out_dir: Path, years: int = 2) -> int:
    """2y of 5min is high value without burning entire 150GB on 1min for all."""
    out = out_dir / f"{sym.replace('^','')}_5min.parquet"
    start = ASOF - timedelta(days=365 * years + 2)
    frames = []
    cur = start
    while cur <= ASOF:
        end = min(cur + timedelta(days=4), ASOF)
        data = get_json(
            "historical-chart/5min",
            {"symbol": sym, "from": cur.isoformat(), "to": end.isoformat()},
        )
        if isinstance(data, list) and data:
            frames.append(pd.DataFrame(data))
        cur = end + timedelta(days=1)
    if not frames:
        return 0
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    save_parquet(df, out)
    return len(df)


def section_reference() -> None:
    print("\n[1] REFERENCE LISTS", flush=True)
    d = DATA / "reference"
    for name, path, params in [
        ("stock_list", "stock-list", {}),
        ("etf_list", "etf-list", {}),
        ("index_list", "index-list", {}),
        ("forex_list", "forex-list", {}),
        ("commodities_list", "commodities-list", {}),
        ("available_exchanges", "available-exchanges", {}),
        ("symbol_change", "symbol-change", {}),
        ("market_risk_premium", "market-risk-premium", {}),
        ("cik_list_p0", "cik-list", {"page": 0, "limit": 1000}),
    ]:
        pull_save(name, path, params, d / f"{name}.json")


def section_calendars() -> None:
    print("\n[2] CALENDARS (5y chunked)", flush=True)
    d = DATA / "calendars"
    # monthly chunks for earnings/div/econ
    kinds = [
        ("earnings", "earnings-calendar"),
        ("dividends", "dividends-calendar"),
        ("economic", "economic-calendar"),
    ]
    for label, path in kinds:
        frames = []
        cur = START
        while cur <= ASOF:
            end = min(cur + timedelta(days=30), ASOF)
            data = get_json(path, {"from": cur.isoformat(), "to": end.isoformat()})
            if isinstance(data, list) and data:
                frames.append(pd.DataFrame(data))
                print(f"  {label} {cur}→{end}: {len(data)}", flush=True)
            cur = end + timedelta(days=1)
        if frames:
            df = pd.concat(frames, ignore_index=True)
            save_parquet(df, d / f"{label}_calendar.parquet")
            save_json({"rows": len(df), "updated": now()}, d / f"{label}_meta.json")
    # IPO calendar longer windows
    pull_save("ipos", "ipos-calendar", {"from": START.isoformat(), "to": ASOF.isoformat()}, d / "ipos.json")


def section_macro_prices() -> None:
    print("\n[3] MACRO PRICES (commodities + FX + key indices EOD + 5m)", flush=True)
    eod_dir = DATA / "macro" / "eod"
    m5_dir = DATA / "macro" / "5min"
    for sym in COMMODITIES + FOREX + INDICES:
        n = download_eod(sym, eod_dir)
        print(f"  EOD {sym}: {n}", flush=True)
        # 5min for highest value only
        if sym in {"ESUSD", "NQUSD", "CLUSD", "GCUSD", "DXUSD", "EURUSD", "USDJPY", "^VIX", "^GSPC", "^TNX"}:
            n5 = download_intraday_5m(sym, m5_dir, years=2)
            print(f"  5m {sym}: {n5}", flush=True)


def section_cot() -> None:
    print("\n[4] COMMITMENT OF TRADERS", flush=True)
    d = DATA / "cot"
    for s in COT_SYMBOLS:
        pull_save(f"cot_report_{s}", "commitment-of-traders-report", {"symbol": s}, d / f"report_{s}.json")
        pull_save(f"cot_analysis_{s}", "commitment-of-traders-analysis", {"symbol": s}, d / f"analysis_{s}.json")


def section_news_bulk() -> None:
    print("\n[5] NEWS / ARTICLES (bulk pages)", flush=True)
    d = DATA / "news"
    # general + fmp articles many pages
    for page in range(0, 50):
        ok = pull_save(f"general_p{page}", "news/general-latest", {"page": page, "limit": 100}, d / f"general_p{page}.json")
        if not ok:
            break
    for page in range(0, 30):
        ok = pull_save(f"fmp_p{page}", "fmp-articles", {"page": page, "limit": 100}, d / f"fmp_articles_p{page}.json")
        if not ok:
            break
    for page in range(0, 20):
        pull_save(f"forex_news_p{page}", "news/forex", {"page": page, "limit": 100}, d / f"forex_p{page}.json")
    # per-symbol stock news + press
    for sym in STOCKS + ETFS_CORE:
        pull_save(f"news_{sym}", "news/stock", {"symbols": sym, "limit": 1000}, d / "by_symbol" / f"{sym}_news.json")
        pull_save(f"pr_{sym}", "news/press-releases", {"symbols": sym, "limit": 500}, d / "by_symbol" / f"{sym}_press.json")


def section_deep_equity() -> None:
    print("\n[6] DEEP EQUITY ENRICHMENT (stocks + core ETFs)", flush=True)
    for sym in STOCKS + ETFS_CORE:
        print(f"  --- {sym} ---", flush=True)
        base = DATA / "equity" / sym
        endpoints = [
            ("profile", "profile", {"symbol": sym}),
            ("quote", "quote", {"symbol": sym}),
            ("price_change", "stock-price-change", {"symbol": sym}),
            ("peers", "stock-peers", {"symbol": sym}),
            ("shares_float", "shares-float", {"symbol": sym}),
            ("key_metrics", "key-metrics", {"symbol": sym, "limit": 40}),
            ("key_metrics_ttm", "key-metrics-ttm", {"symbol": sym}),
            ("ratios", "ratios", {"symbol": sym, "limit": 40}),
            ("ratios_ttm", "ratios-ttm", {"symbol": sym}),
            ("financial_scores", "financial-scores", {"symbol": sym}),
            ("owner_earnings", "owner-earnings", {"symbol": sym}),
            ("enterprise_values", "enterprise-values", {"symbol": sym, "limit": 40}),
            ("income_annual", "income-statement", {"symbol": sym, "period": "annual", "limit": 40}),
            ("income_quarter", "income-statement", {"symbol": sym, "period": "quarter", "limit": 40}),
            ("balance_annual", "balance-sheet-statement", {"symbol": sym, "period": "annual", "limit": 40}),
            ("balance_quarter", "balance-sheet-statement", {"symbol": sym, "period": "quarter", "limit": 40}),
            ("cash_annual", "cash-flow-statement", {"symbol": sym, "period": "annual", "limit": 40}),
            ("cash_quarter", "cash-flow-statement", {"symbol": sym, "period": "quarter", "limit": 40}),
            ("income_growth", "income-statement-growth", {"symbol": sym, "limit": 40}),
            ("financial_growth", "financial-growth", {"symbol": sym, "limit": 40}),
            ("revenue_product", "revenue-product-segmentation", {"symbol": sym}),
            ("revenue_geo", "revenue-geographic-segmentation", {"symbol": sym}),
            ("earnings", "earnings", {"symbol": sym, "limit": 80}),
            ("analyst_annual", "analyst-estimates", {"symbol": sym, "period": "annual", "limit": 40}),
            ("analyst_quarter", "analyst-estimates", {"symbol": sym, "period": "quarter", "limit": 40}),
            ("grades", "grades", {"symbol": sym}),
            ("grades_consensus", "grades-consensus", {"symbol": sym}),
            ("grades_historical", "grades-historical", {"symbol": sym}),
            ("ratings_snapshot", "ratings-snapshot", {"symbol": sym}),
            ("ratings_historical", "ratings-historical", {"symbol": sym, "limit": 200}),
            ("price_target_consensus", "price-target-consensus", {"symbol": sym}),
            ("price_target_summary", "price-target-summary", {"symbol": sym}),
            ("price_target_news", "price-target-news", {"symbol": sym, "page": 0}),
            ("splits", "splits", {"symbol": sym}),
            ("dividends", "dividends", {"symbol": sym}),
            ("insider_search", "insider-trading/search", {"symbol": sym, "page": 0, "limit": 1000}),
            ("insider_stats", "insider-trading/statistics", {"symbol": sym}),
            ("beneficial", "acquisition-of-beneficial-ownership", {"symbol": sym}),
            ("inst_summary", "institutional-ownership/symbol-positions-summary", {"symbol": sym, "year": 2024, "quarter": 4}),
            ("esg_disclosures", "esg-disclosures", {"symbol": sym}),
            ("esg_ratings", "esg-ratings", {"symbol": sym}),
            ("employee_count", "employee-count", {"symbol": sym}),
            ("employee_hist", "historical-employee-count", {"symbol": sym}),
            ("company_notes", "company-notes", {"symbol": sym}),
            ("transcript_list", "earnings-transcript-list", {"symbol": sym}),
        ]
        for name, path, params in endpoints:
            pull_save(name, path, params, base / f"{name}.json")

        # market cap history 5y
        pull_save(
            "mktcap",
            "historical-market-capitalization",
            {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
            base / "market_cap_hist.json",
        )

        # recent earnings call transcripts (last 8 quarters)
        for year in range(ASOF.year, ASOF.year - 3, -1):
            for q in (1, 2, 3, 4):
                pull_save(
                    f"transcript_{year}_Q{q}",
                    "earning-call-transcript",
                    {"symbol": sym, "year": year, "quarter": q},
                    base / "transcripts" / f"{year}_Q{q}.json",
                )


def section_technicals() -> None:
    print("\n[7] TECHNICAL INDICATORS (universe)", flush=True)
    d = DATA / "technicals"
    for sym in ALL_EQUITY + INDICES:
        print(f"  tech {sym}", flush=True)
        for name, extra in TECH_DAILY:
            pull_save(
                f"{sym}_{name}_1d",
                f"technical-indicators/{name}",
                {
                    "symbol": sym,
                    "timeframe": "1day",
                    "from": START.isoformat(),
                    "to": ASOF.isoformat(),
                    **extra,
                },
                d / sym.replace("^", "") / f"{name}_1day.json",
            )
        # 5min tech last 90d high signal names
        if sym in STOCKS + ["SPY", "QQQ", "NVDA", "TSLA", "^VIX"]:
            start90 = (ASOF - timedelta(days=90)).isoformat()
            for name, extra in TECH_5MIN:
                pull_save(
                    f"{sym}_{name}_5m",
                    f"technical-indicators/{name}",
                    {
                        "symbol": sym,
                        "timeframe": "5min",
                        "from": start90,
                        "to": ASOF.isoformat(),
                        **extra,
                    },
                    d / sym.replace("^", "") / f"{name}_5min.json",
                )


def section_econ_treasury() -> None:
    print("\n[8] ECONOMICS + TREASURY", flush=True)
    d = DATA / "macro_econ"
    pull_save(
        "treasury",
        "treasury-rates",
        {"from": START.isoformat(), "to": ASOF.isoformat()},
        d / "treasury_rates.json",
    )
    for name in ECON:
        pull_save(name, "economic-indicators", {"name": name}, d / "indicators" / f"{name}.json")


def section_insider_latest() -> None:
    print("\n[9] MARKET-WIDE INSIDER LATEST (pages)", flush=True)
    d = DATA / "insider_market"
    for page in range(0, 100):
        ok = pull_save(
            f"insider_p{page}",
            "insider-trading/latest",
            {"page": page, "limit": 100},
            d / f"page_{page:03d}.json",
        )
        if not ok:
            break


def section_snapshots() -> None:
    print("\n[10] SNAPSHOTS", flush=True)
    d = DATA / "snapshots"
    pull_save("gainers", "biggest-gainers", {}, d / "gainers.json")
    pull_save("losers", "biggest-losers", {}, d / "losers.json")
    pull_save("actives", "most-actives", {}, d / "actives.json")
    pull_save("batch_index", "batch-index-quotes", {}, d / "batch_index_quotes.json")
    pull_save("batch_commodity", "batch-commodity-quotes", {}, d / "batch_commodity_quotes.json")
    # sector snapshots last 90 trading-ish days
    for i in range(0, 120):
        day = ASOF - timedelta(days=i)
        if day.weekday() >= 5:
            continue
        pull_save(
            f"sector_{day}",
            "sector-performance-snapshot",
            {"date": day.isoformat()},
            d / "sectors" / f"{day.isoformat()}.json",
        )


def main() -> int:
    print("=" * 70, flush=True)
    print("AETHER FMP ULTIMATE MAX", flush=True)
    print(f"OUT: {DATA}", flush=True)
    print(f"Range: {START} → {ASOF}", flush=True)
    print("NO DATABENTO. Best-of-best + all useful Ultimate endpoints.", flush=True)
    print("=" * 70, flush=True)

    save_json(
        {
            "started": now(),
            "out": str(DATA),
            "as_of": ASOF.isoformat(),
            "start": START.isoformat(),
            "plan": "Ultimate — max useful download",
            "stocks": STOCKS,
            "commodities": COMMODITIES,
            "forex": FOREX,
        },
        DATA / "manifest_start.json",
    )

    section_reference()
    section_calendars()
    section_econ_treasury()
    section_cot()
    section_macro_prices()
    section_news_bulk()
    section_deep_equity()
    section_technicals()
    section_insider_latest()
    section_snapshots()

    save_json({"finished": now(), "out": str(DATA)}, DATA / "manifest_done.json")
    print("\nDONE FMP ULTIMATE MAX", flush=True)
    print(f"Data: {DATA}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
