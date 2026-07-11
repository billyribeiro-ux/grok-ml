#!/usr/bin/env python3
"""
Aether — EVERY market-internal signal FMP Ultimate can serve.

What "internals" means here (and what FMP actually has):
  YES: VIX term structure, VVIX, MOVE, sector/industry breadth, indices,
       COT, treasury, economic calendar/indicators, insider flow,
       put-write / vol indices, gainers-losers-actives, exchange batches,
       ETF sector weightings, institutional snapshots for core names.
  NO (not on FMP): classic NYSE TICK, TRIN, raw ADD/ADV/DECL, equity PCR ^CPC.

Writes to: /Volumes/LaCie/Aether/data/raw/fmp/market_internals/
Respects rate limits with backoff (Ultimate 3000/min — we stay ~12 rps to
coexist with other jobs, or wait on 429).
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
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
START = ASOF - timedelta(days=365 * 5 + 2)

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/market_internals")
if not Path("/Volumes/LaCie/Aether").exists():
    OUT = ROOT / "data" / "fmp" / "market_internals"
OUT.mkdir(parents=True, exist_ok=True)

# --- exhaustive internal / regime index set (FMP index-list validated family) ---
VOL_REGIME_INDICES = [
    "^VIX", "^VIX1D", "^VIX9D", "^VIX3M", "^VIX6M", "^VIX1Y", "^VVIX",
    "^VXN", "^RVX", "^VXD", "^OVX", "^GVZ", "^VXSLV", "^VXTLT", "^MOVE",
    "^SPOTVOL", "^LOVOL", "^VIXEQ", "^VXTH", "^VIXMO", "^VINMO", "^VIFMO",
    "^VIN", "^VIF", "^VWA", "^VWB", "^VW1VX", "^VW2VX", "^VW3VX",
    "^LONGVOL", "^SHORTVOL", "^DLVIX", "^DSVIX", "^DSVIER", "^VINXE",
    "^PUT", "^PUTR", "^PWT", "^PUTY", "^PUTVM", "^BXMVM", "^CALD", "^SPDVDCC",
]

MARKET_BREADTH_PROXIES = [
    "^GSPC", "^DJI", "^IXIC", "^RUT", "^NYA", "^XAX", "^RUTTR",
    "^XNDX", "^XCMP", "^NBI", "^ICEBIO", "^TRAN", "^PSE",
    "^TNX", "^IRX", "^FVX", "^TYX",
]

SECTORS = [
    "Basic Materials", "Communication Services", "Consumer Cyclical",
    "Consumer Defensive", "Energy", "Financial Services", "Healthcare",
    "Industrials", "Real Estate", "Technology", "Utilities",
]

ECON = [
    "GDP", "realGDP", "realGDPPerCapita", "federalFunds", "CPI", "inflationRate",
    "unemploymentRate", "totalNonfarmPayroll", "initialClaims", "retailSales",
    "consumerSentiment", "industrialProductionTotalIndex",
    "smoothedUSRecessionProbabilities", "15YearFixedRateMortgageAverage",
    "30YearFixedRateMortgageAverage", "newPrivatelyOwnedHousingUnitsStartedTotalUnits",
]

COT = ["VX", "ES", "NQ", "YM", "CL", "GC", "SI", "ZN", "ZB", "NG", "HG", "DX"]

CORE_FOR_FLOW = ["SPY", "QQQ", "IWM", "AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO"]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherMarketInternals/1.0"})
MIN_INTERVAL = float(os.getenv("FMP_INTERNALS_INTERVAL", "0.12"))  # ~500/min — coexist
_last = 0.0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def throttle() -> None:
    global _last
    dt = time.time() - _last
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last = time.time()


def get_json(path: str, params: dict | None = None, retries: int = 8) -> Any:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        throttle()
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=120)
            if r.status_code == 429:
                wait = min(60, 2 ** attempt)
                print(f"  429 backoff {wait}s on {path}", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            if r.status_code in (400, 404) or not r.text.strip():
                return None
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            time.sleep(1 + attempt)
    return None


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def save_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def pull(name: str, path: str, params: dict | None, out: Path) -> bool:
    if out.exists() and out.stat().st_size > 50:
        print(f"  skip exists {name}", flush=True)
        return True
    data = get_json(path, params)
    if data is None:
        print(f"  miss {name}", flush=True)
        return False
    if isinstance(data, list) and len(data) == 0:
        print(f"  empty {name}", flush=True)
        return False
    save_json(data, out)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        try:
            save_df(pd.DataFrame(data), out.with_suffix(".parquet"))
        except Exception:
            pass
    n = len(data) if isinstance(data, list) else "obj"
    print(f"  OK {name} ({n})", flush=True)
    return True


def download_eod(sym: str, out_dir: Path) -> int:
    safe = sym.replace("^", "").replace("/", "_")
    out = out_dir / f"{safe}.parquet"
    if out.exists() and out.stat().st_size > 400:
        return -1
    data = get_json(
        "historical-price-eod/full",
        {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
    )
    if not isinstance(data, list) or not data:
        data = get_json(
            "historical-price-eod/light",
            {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
        )
    if not isinstance(data, list) or not data:
        return 0
    df = pd.DataFrame(data)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date", keep="last")
    df["symbol"] = sym
    save_df(df, out)
    return len(df)


def download_5m(sym: str, out_dir: Path, years: int = 2) -> int:
    safe = sym.replace("^", "").replace("/", "_")
    out = out_dir / f"{safe}_5min.parquet"
    if out.exists() and out.stat().st_size > 20_000:
        return -1
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
    df = df.sort_values("date").drop_duplicates("date", keep="last")
    df["symbol"] = sym
    save_df(df, out)
    return len(df)


def section_honest_gaps() -> None:
    gaps = {
        "unavailable_on_fmp": [
            "NYSE TICK (^TICK)",
            "TRIN / Arms Index",
            "Advance-Decline line raw (ADD/ADV/DECL ticks)",
            "CBOE equity put/call ratio series as quote symbols (^CPC/^CPCE)",
            "True order-book internals (use Databento for that)",
        ],
        "proxies_pulled_instead": [
            "Full VIX term structure + VVIX + MOVE + cross-asset vol indices",
            "CBOE PutWrite indices (^PUT family) as options-pressure proxies",
            "Sector + industry performance breadth",
            "Gainers/losers/most-actives + exchange-wide quote batches",
            "Insider latest flow market-wide",
            "COT positioning",
            "Treasury + economic calendar/indicators",
            "ETF sector/country weightings for SPY/QQQ/IWM",
        ],
        "updated": now(),
    }
    save_json(gaps, OUT / "GAPS_AND_PROXIES.json")


def section_vol_indices() -> None:
    print("\n[1] VOL / REGIME INDICES EOD + 5m", flush=True)
    eod = OUT / "indices" / "eod"
    m5 = OUT / "indices" / "5min"
    priority_5m = {
        "^VIX", "^VIX1D", "^VVIX", "^VIX9D", "^VIX3M", "^MOVE",
        "^VXN", "^RVX", "^GSPC", "^RUT", "^IXIC", "^TNX",
    }
    for sym in VOL_REGIME_INDICES + MARKET_BREADTH_PROXIES:
        n = download_eod(sym, eod)
        print(f"  EOD {sym}: {n}", flush=True)
        if sym in priority_5m:
            n5 = download_5m(sym, m5, years=2)
            print(f"  5m {sym}: {n5}", flush=True)


def section_sector_industry_breadth() -> None:
    print("\n[2] SECTOR + INDUSTRY BREADTH", flush=True)
    # historical sector series
    for sec in SECTORS:
        pull(
            f"sector_{sec}",
            "historical-sector-performance",
            {"sector": sec, "from": START.isoformat(), "to": ASOF.isoformat()},
            OUT / "breadth" / "sectors" / f"{sec.replace(' ', '_')}.json",
        )
    # daily snapshots last ~180 sessions
    for i in range(0, 260):
        day = ASOF - timedelta(days=i)
        if day.weekday() >= 5:
            continue
        ds = day.isoformat()
        pull(
            f"sector_snap_{ds}",
            "sector-performance-snapshot",
            {"date": ds},
            OUT / "breadth" / "sector_snapshots" / f"{ds}.json",
        )
        pull(
            f"industry_snap_{ds}",
            "industry-performance-snapshot",
            {"date": ds},
            OUT / "breadth" / "industry_snapshots" / f"{ds}.json",
        )
    # build industry name list from latest snapshot and pull historical where API allows
    latest = OUT / "breadth" / "industry_snapshots"
    industries = set()
    if latest.exists():
        for p in sorted(latest.glob("*.json"))[-5:]:
            try:
                rows = json.loads(p.read_text())
                if isinstance(rows, list):
                    for r in rows:
                        if r.get("industry"):
                            industries.add(r["industry"])
            except Exception:
                pass
    print(f"  industries discovered: {len(industries)}", flush=True)
    save_json(sorted(industries), OUT / "breadth" / "industry_names.json")
    for ind in sorted(industries):
        pull(
            f"hist_ind_{ind[:40]}",
            "historical-industry-performance",
            {"industry": ind, "from": START.isoformat(), "to": ASOF.isoformat()},
            OUT / "breadth" / "industries_hist" / f"{ind.replace('/', '_').replace(' ', '_')[:80]}.json",
        )


def section_market_wide_flow() -> None:
    print("\n[3] MARKET-WIDE FLOW SNAPSHOTS + BATCHES", flush=True)
    d = OUT / "flow"
    for name, path, params in [
        ("gainers", "biggest-gainers", {}),
        ("losers", "biggest-losers", {}),
        ("actives", "most-actives", {}),
        ("batch_index_quotes", "batch-index-quotes", {}),
        ("batch_etf_quotes", "batch-etf-quotes", {}),
        ("batch_commodity_quotes", "batch-commodity-quotes", {}),
        ("batch_forex_quotes", "batch-forex-quotes", {}),
        ("batch_exchange_nasdaq", "batch-exchange-quote", {"exchange": "NASDAQ"}),
        ("batch_exchange_nyse", "batch-exchange-quote", {"exchange": "NYSE"}),
        ("batch_exchange_amex", "batch-exchange-quote", {"exchange": "AMEX"}),
        ("market_risk_premium", "market-risk-premium", {}),
        ("index_list", "index-list", {}),
    ]:
        pull(name, path, params, d / f"{name}.json")


def section_insider_institutional() -> None:
    print("\n[4] INSIDER + INSTITUTIONAL FLOW", flush=True)
    d = OUT / "positioning"
    for page in range(0, 200):
        ok = pull(
            f"insider_latest_{page}",
            "insider-trading/latest",
            {"page": page, "limit": 100},
            d / "insider_latest" / f"page_{page:03d}.json",
        )
        if not ok:
            break
    for sym in CORE_FOR_FLOW:
        pull(f"insider_{sym}", "insider-trading/search", {"symbol": sym, "page": 0, "limit": 1000}, d / "by_symbol" / f"{sym}_insider.json")
        pull(f"insider_stats_{sym}", "insider-trading/statistics", {"symbol": sym}, d / "by_symbol" / f"{sym}_insider_stats.json")
        pull(f"float_{sym}", "shares-float", {"symbol": sym}, d / "by_symbol" / f"{sym}_float.json")
        for y in (2023, 2024, 2025):
            for q in (1, 2, 3, 4):
                pull(
                    f"inst_{sym}_{y}Q{q}",
                    "institutional-ownership/symbol-positions-summary",
                    {"symbol": sym, "year": y, "quarter": q},
                    d / "institutional" / f"{sym}_{y}_Q{q}.json",
                )


def section_cot_econ() -> None:
    print("\n[5] COT + TREASURY + ECONOMIC", flush=True)
    d = OUT / "macro"
    for s in COT:
        pull(f"cot_report_{s}", "commitment-of-traders-report", {"symbol": s}, d / "cot" / f"report_{s}.json")
        pull(f"cot_analysis_{s}", "commitment-of-traders-analysis", {"symbol": s}, d / "cot" / f"analysis_{s}.json")
    pull(
        "treasury",
        "treasury-rates",
        {"from": START.isoformat(), "to": ASOF.isoformat()},
        d / "treasury_rates.json",
    )
    for name in ECON:
        pull(name, "economic-indicators", {"name": name}, d / "econ" / f"{name}.json")
    # economic calendar monthly
    cur = START
    frames = []
    while cur <= ASOF:
        end = min(cur + timedelta(days=30), ASOF)
        data = get_json("economic-calendar", {"from": cur.isoformat(), "to": end.isoformat()})
        if isinstance(data, list) and data:
            frames.append(pd.DataFrame(data))
            print(f"  econ cal {cur}→{end}: {len(data)}", flush=True)
        cur = end + timedelta(days=1)
    if frames:
        df = pd.concat(frames, ignore_index=True)
        save_df(df, d / "economic_calendar_full.parquet")


def section_etf_internals() -> None:
    print("\n[6] ETF INTERNAL STRUCTURE (major)", flush=True)
    d = OUT / "etf_structure"
    for sym in ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "SMH", "TZA", "SQQQ"]:
        for name, path in [
            ("info", "etf/info"),
            ("holdings", "etf/holdings"),
            ("sector_weightings", "etf/sector-weightings"),
            ("country_weightings", "etf/country-weightings"),
        ]:
            pull(f"{sym}_{name}", path, {"symbol": sym}, d / sym / f"{name}.json")


def section_news_internals() -> None:
    print("\n[7] NEWS / REGIME NARRATIVE", flush=True)
    d = OUT / "news"
    for page in range(0, 40):
        if not pull(f"general_{page}", "news/general-latest", {"page": page, "limit": 100}, d / f"general_p{page:02d}.json"):
            break
    for page in range(0, 20):
        if not pull(f"fmp_{page}", "fmp-articles", {"page": page, "limit": 100}, d / f"fmp_p{page:02d}.json"):
            break


def main() -> int:
    print("=" * 70, flush=True)
    print("MARKET INTERNALS — ALL AVAILABLE ON FMP", flush=True)
    print(f"OUT={OUT}", flush=True)
    print("=" * 70, flush=True)
    save_json({"started": now(), "out": str(OUT)}, OUT / "run_start.json")
    section_honest_gaps()
    section_vol_indices()
    section_sector_industry_breadth()
    section_market_wide_flow()
    section_insider_institutional()
    section_cot_econ()
    section_etf_internals()
    section_news_internals()
    save_json({"finished": now(), "out": str(OUT)}, OUT / "run_done.json")
    print("\nDONE market internals", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
