#!/usr/bin/env python3
"""
Aether — Download EVERYTHING useful from the FMP Ultimate catalog.

Uses user's full plan list. Prefers bulk CSV endpoints (efficient).
Per-symbol deep pulls for Aether core names for any remaining endpoints.

OUT: /Volumes/LaCie/Aether/data/raw/fmp/plan_catalog/
Skip-if-exists. 429 backoff. No Databento.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/plan_catalog")
if not Path("/Volumes/LaCie/Aether").exists():
    OUT = ROOT / "data" / "fmp" / "plan_catalog"
OUT.mkdir(parents=True, exist_ok=True)

CORE = ["AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO", "SPY", "QQQ", "IWM"]
INTERVAL = float(os.getenv("FMP_CATALOG_INTERVAL", "0.08"))

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherFMPCatalog/1.0"})
_last = 0.0
_ok = _fail = _skip = 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def throttle() -> None:
    global _last
    dt = time.time() - _last
    if dt < INTERVAL:
        time.sleep(INTERVAL - dt)
    _last = time.time()


def request_raw(path: str, params: dict | None = None, retries: int = 8) -> tuple[int, bytes, str]:
    """Return status, body bytes, content-type."""
    global _ok, _fail
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        throttle()
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=300)
            if r.status_code == 429:
                time.sleep(min(90, 2 ** attempt))
                continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            return r.status_code, r.content, r.headers.get("content-type", "")
        except Exception:
            time.sleep(1 + attempt)
    return 0, b"", ""


def save_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def pull(name: str, api_path: str, params: dict | None, rel: str, min_bytes: int = 20) -> bool:
    global _ok, _fail, _skip
    out = OUT / rel
    if out.exists() and out.stat().st_size >= min_bytes:
        _skip += 1
        return True
    st, body, ctype = request_raw(api_path, params)
    if st != 200 or not body or len(body) < min_bytes:
        _fail += 1
        print(f"  MISS {name} status={st} len={len(body)}", flush=True)
        return False
    # choose extension
    if "csv" in ctype or body[:1] in (b'"', b"s") and b"," in body[:200]:
        if out.suffix != ".csv":
            out = out.with_suffix(".csv")
    elif out.suffix not in (".json", ".csv", ".xlsx"):
        # try json
        try:
            json.loads(body)
            out = out.with_suffix(".json") if out.suffix != ".json" else out
        except Exception:
            out = out.with_suffix(".bin")
    save_bytes(out, body)
    _ok += 1
    print(f"  OK {name} → {out.relative_to(OUT)} ({len(body):,} bytes)", flush=True)
    return True


def section_directory() -> None:
    print("\n[DIRECTORY]", flush=True)
    for name, path, params in [
        ("stock_list", "stock-list", {}),
        ("financial_statement_symbol_list", "financial-statement-symbol-list", {}),
        ("cik_list", "cik-list", {"page": 0, "limit": 10000}),
        ("symbol_changes", "symbol-change", {}),
        ("etf_list", "etf-list", {}),
        ("actively_trading", "actively-trading-list", {}),
        ("available_exchanges", "available-exchanges", {}),
        ("available_sectors", "available-sectors", {}),
        ("available_industries", "available-industries", {}),
        ("available_countries", "available-countries", {}),
        ("delisted_p0", "delisted-companies", {"page": 0}),
        ("index_list", "index-list", {}),
        ("commodities_list", "commodities-list", {}),
        # forex + crypto intentionally skipped (user preference)
        ("sic_list", "standard-industrial-classification-list", {}),
        ("earnings_transcript_symbols", "earnings-transcript-list", {"symbol": "AAPL"}),  # sample; full per-symbol elsewhere
    ]:
        pull(name, path, params, f"directory/{name}")


def section_bulk() -> None:
    print("\n[BULK CSV — full market dumps]", flush=True)
    # These are the highest-leverage Ultimate endpoints
    bulks = [
        ("rating_bulk", "rating-bulk", {}),
        ("dcf_bulk", "dcf-bulk", {}),
        ("scores_bulk", "scores-bulk", {}),
        ("key_metrics_ttm_bulk", "key-metrics-ttm-bulk", {}),
        ("ratios_ttm_bulk", "ratios-ttm-bulk", {}),
        ("peers_bulk", "peers-bulk", {}),
        ("price_target_summary_bulk", "price-target-summary-bulk", {}),
        ("upgrades_downgrades_consensus_bulk", "upgrades-downgrades-consensus-bulk", {}),
        ("eod_bulk_today", "eod-bulk", {"date": ASOF.isoformat()}),
        ("eod_bulk_yday", "eod-bulk", {"date": (ASOF - timedelta(days=1)).isoformat()}),
        ("income_statement_bulk_2024", "income-statement-bulk", {"year": 2024, "period": "annual"}),
        ("income_statement_bulk_2025", "income-statement-bulk", {"year": 2025, "period": "annual"}),
        ("income_growth_bulk_2024", "income-statement-growth-bulk", {"year": 2024, "period": "annual"}),
        ("balance_bulk_2024", "balance-sheet-statement-bulk", {"year": 2024, "period": "annual"}),
        ("balance_growth_bulk_2024", "balance-sheet-statement-growth-bulk", {"year": 2024, "period": "annual"}),
        ("cashflow_bulk_2024", "cash-flow-statement-bulk", {"year": 2024, "period": "annual"}),
        ("cashflow_growth_bulk_2024", "cash-flow-statement-growth-bulk", {"year": 2024, "period": "annual"}),
        ("profile_bulk", "profile-bulk", {"part": 0}),
        ("etf_holder_bulk", "etf-holder-bulk", {}),
        ("earnings_surprises_bulk", "earnings-surprises-bulk", {}),
    ]
    for name, path, params in bulks:
        pull(name, path, params, f"bulk/{name}.csv", min_bytes=100)


def section_market_performance() -> None:
    print("\n[MARKET PERFORMANCE]", flush=True)
    for i in range(0, 400):
        day = ASOF - timedelta(days=i)
        if day.weekday() >= 5:
            continue
        ds = day.isoformat()
        pull(f"sector_perf_{ds}", "sector-performance-snapshot", {"date": ds}, f"performance/sector/{ds}.json")
        pull(f"industry_perf_{ds}", "industry-performance-snapshot", {"date": ds}, f"performance/industry/{ds}.json")
        pull(f"sector_pe_{ds}", "sector-pe-snapshot", {"date": ds}, f"performance/sector_pe/{ds}.json")
        pull(f"industry_pe_{ds}", "industry-pe-snapshot", {"date": ds}, f"performance/industry_pe/{ds}.json")
    for sec in [
        "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive",
        "Energy", "Financial Services", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities",
    ]:
        pull(
            f"hist_sector_{sec}",
            "historical-sector-performance",
            {"sector": sec, "from": START.isoformat(), "to": ASOF.isoformat()},
            f"performance/historical_sector/{sec.replace(' ', '_')}.json",
        )
        pull(
            f"hist_sector_pe_{sec}",
            "historical-sector-pe",
            {"sector": sec, "from": START.isoformat(), "to": ASOF.isoformat()},
            f"performance/historical_sector_pe/{sec.replace(' ', '_')}.json",
        )
    pull("gainers", "biggest-gainers", {}, "performance/gainers.json")
    pull("losers", "biggest-losers", {}, "performance/losers.json")
    pull("actives", "most-actives", {}, "performance/actives.json")


def section_quotes_batches() -> None:
    print("\n[QUOTES / BATCHES]", flush=True)
    for name, path, params in [
        ("batch_index", "batch-index-quotes", {}),
        ("batch_etf", "batch-etf-quotes", {}),
        ("batch_commodity", "batch-commodity-quotes", {}),
        # batch_forex / batch_crypto skipped
        ("batch_nasdaq", "batch-exchange-quote", {"exchange": "NASDAQ"}),
        ("batch_nyse", "batch-exchange-quote", {"exchange": "NYSE"}),
        ("batch_amex", "batch-exchange-quote", {"exchange": "AMEX"}),
        ("batch_core", "batch-quote", {"symbols": ",".join(CORE)}),
        ("batch_core_short", "batch-quote-short", {"symbols": ",".join(CORE)}),
    ]:
        pull(name, path, params, f"quotes/{name}.json")
    for sym in CORE:
        pull(f"aftermarket_trade_{sym}", "aftermarket-trade", {"symbol": sym}, f"quotes/aftermarket/{sym}_trade.json")
        pull(f"aftermarket_quote_{sym}", "aftermarket-quote", {"symbol": sym}, f"quotes/aftermarket/{sym}_quote.json")
        pull(f"price_change_{sym}", "stock-price-change", {"symbol": sym}, f"quotes/change/{sym}.json")


def section_calendars_events() -> None:
    print("\n[CALENDARS / EVENTS]", flush=True)
    pull("splits_cal", "splits-calendar", {"from": START.isoformat(), "to": ASOF.isoformat()}, "calendars/splits.json")
    pull("ipos_cal", "ipos-calendar", {"from": START.isoformat(), "to": ASOF.isoformat()}, "calendars/ipos.json")
    pull("ipos_disclosure", "ipos-disclosure", {"from": START.isoformat(), "to": ASOF.isoformat()}, "calendars/ipos_disclosure.json")
    pull("ipos_prospectus", "ipos-prospectus", {"from": START.isoformat(), "to": ASOF.isoformat()}, "calendars/ipos_prospectus.json")
    # earnings/div/econ already in other pipelines; still refresh full range chunks
    cur = START
    while cur <= ASOF:
        end = min(cur + timedelta(days=30), ASOF)
        for kind, path in [
            ("earnings", "earnings-calendar"),
            ("dividends", "dividends-calendar"),
            ("economic", "economic-calendar"),
        ]:
            pull(
                f"{kind}_{cur}",
                path,
                {"from": cur.isoformat(), "to": end.isoformat()},
                f"calendars/{kind}/{cur.isoformat()}_{end.isoformat()}.json",
            )
        cur = end + timedelta(days=1)


def section_senate_house_insider() -> None:
    print("\n[SENATE / HOUSE / INSIDER]", flush=True)
    pull("senate_latest", "senate-latest", {}, "politics/senate_latest.json")
    pull("house_latest", "house-latest", {}, "politics/house_latest.json")
    for sym in CORE:
        pull(f"senate_{sym}", "senate-trades", {"symbol": sym}, f"politics/senate_{sym}.json")
        pull(f"house_{sym}", "house-trades", {"symbol": sym}, f"politics/house_{sym}.json")
    for page in range(0, 100):
        if not pull(f"insider_p{page}", "insider-trading/latest", {"page": page, "limit": 100}, f"insider/latest/page_{page:03d}.json"):
            break
    pull("insider_types", "insider-trading-transaction-type", {}, "insider/transaction_types.json")


def section_institutional() -> None:
    print("\n[INSTITUTIONAL 13F]", flush=True)
    pull("inst_latest", "institutional-ownership/latest", {}, "institutional/latest.json")
    for page in range(0, 50):
        if not pull(f"inst_filings_p{page}", "institutional-ownership/latest", {"page": page}, f"institutional/filings_p{page:03d}.json"):
            break
    for sym in CORE:
        for y in (2023, 2024, 2025):
            for q in (1, 2, 3, 4):
                pull(
                    f"pos_{sym}_{y}Q{q}",
                    "institutional-ownership/symbol-positions-summary",
                    {"symbol": sym, "year": y, "quarter": q},
                    f"institutional/positions/{sym}_{y}_Q{q}.json",
                )


def section_sec() -> None:
    print("\n[SEC FILINGS]", flush=True)
    pull("sec_8k_recent", "sec-filings-8k", {"from": (ASOF - timedelta(days=30)).isoformat(), "to": ASOF.isoformat(), "page": 0}, "sec/8k_recent.json")
    for sym in CORE:
        pull(
            f"sec_{sym}",
            "sec-filings-search/symbol",
            {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat(), "page": 0},
            f"sec/by_symbol/{sym}.json",
        )


def section_analyst_dcf_esg() -> None:
    print("\n[ANALYST / DCF / ESG / EXEC]", flush=True)
    for sym in CORE:
        for name, path, params in [
            ("estimates_q", "analyst-estimates", {"symbol": sym, "period": "quarter", "limit": 40}),
            ("estimates_a", "analyst-estimates", {"symbol": sym, "period": "annual", "limit": 40}),
            ("ratings", "ratings-snapshot", {"symbol": sym}),
            ("ratings_hist", "ratings-historical", {"symbol": sym, "limit": 200}),
            ("pt_summary", "price-target-summary", {"symbol": sym}),
            ("pt_consensus", "price-target-consensus", {"symbol": sym}),
            ("grades", "grades", {"symbol": sym}),
            ("grades_hist", "grades-historical", {"symbol": sym}),
            ("grades_summary", "grades-consensus", {"symbol": sym}),
            ("esg_disc", "esg-disclosures", {"symbol": sym}),
            ("esg_ratings", "esg-ratings", {"symbol": sym}),
            ("exec_comp", "governance-executive-compensation", {"symbol": sym}),
            ("key_exec", "key-executives", {"symbol": sym}),
            ("beneficial", "acquisition-of-beneficial-ownership", {"symbol": sym}),
            ("transcript_dates", "earning-call-transcript-dates", {"symbol": sym}),
        ]:
            pull(f"{sym}_{name}", path, params, f"company/{sym}/{name}.json")
    pull("esg_benchmark", "esg-benchmark", {}, "esg/benchmark.json")


def section_statements_extra() -> None:
    print("\n[STATEMENTS EXTRA / AS-REPORTED / 10K]", flush=True)
    for sym in CORE:
        for name, path, params in [
            ("income_as_reported", "income-statement-as-reported", {"symbol": sym, "limit": 40}),
            ("balance_as_reported", "balance-sheet-statement-as-reported", {"symbol": sym, "limit": 40}),
            ("cash_as_reported", "cash-flow-statement-as-reported", {"symbol": sym, "limit": 40}),
            ("financials_as_reported", "financial-statement-full-as-reported", {"symbol": sym, "limit": 10}),
            ("reports_dates", "financial-reports-dates", {"symbol": sym}),
            ("owner_earnings", "owner-earnings", {"symbol": sym}),
            ("enterprise_values", "enterprise-values", {"symbol": sym, "limit": 40}),
            ("financial_scores", "financial-scores", {"symbol": sym}),
            ("key_metrics", "key-metrics", {"symbol": sym, "limit": 40}),
            ("ratios", "ratios", {"symbol": sym, "limit": 40}),
            ("income_growth", "income-statement-growth", {"symbol": sym, "limit": 40}),
            ("balance_growth", "balance-sheet-statement-growth", {"symbol": sym, "limit": 40}),
            ("cash_growth", "cash-flow-statement-growth", {"symbol": sym, "limit": 40}),
            ("fin_growth", "financial-growth", {"symbol": sym, "limit": 40}),
            ("rev_product", "revenue-product-segmentation", {"symbol": sym}),
            ("rev_geo", "revenue-geographic-segmentation", {"symbol": sym}),
            ("mktcap_hist", "historical-market-capitalization", {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()}),
            ("share_float", "shares-float", {"symbol": sym}),
            ("profile", "profile", {"symbol": sym}),
            ("peers", "stock-peers", {"symbol": sym}),
            ("notes", "company-notes", {"symbol": sym}),
            ("employees", "historical-employee-count", {"symbol": sym}),
        ]:
            pull(f"{sym}_{name}", path, params, f"statements/{sym}/{name}.json")


def section_tech_full() -> None:
    print("\n[TECHNICALS FULL SET]", flush=True)
    indicators = [
        ("sma", 20), ("ema", 20), ("wma", 20), ("dema", 20), ("tema", 20),
        ("rsi", 14), ("standarddeviation", 20), ("williams", 14), ("adx", 14),
    ]
    for sym in CORE + ["^VIX", "^GSPC", "^RUT"]:
        for name, period in indicators:
            for tf in ("1day", "1hour", "5min"):
                fr = START.isoformat() if tf == "1day" else (ASOF - timedelta(days=90)).isoformat()
                pull(
                    f"{sym}_{name}_{tf}",
                    f"technical-indicators/{name}",
                    {
                        "symbol": sym,
                        "periodLength": period,
                        "timeframe": tf,
                        "from": fr,
                        "to": ASOF.isoformat(),
                    },
                    f"technicals/{sym.replace('^','')}/{name}_{tf}.json",
                )


def section_macro_assets() -> None:
    print("\n[COMMODITY / INDEX PRICES — no forex/crypto]", flush=True)
    # Equities/index/commodity only (forex + crypto skipped per user)
    assets = [
        "GCUSD", "SIUSD", "CLUSD", "NGUSD", "ESUSD", "NQUSD", "DXUSD",
        "^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^TNX",
    ]
    for sym in assets:
        pull(
            f"eod_{sym}",
            "historical-price-eod/full",
            {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
            f"prices/eod/{sym.replace('^','')}.json",
        )
        # 1h last 2y
        pull(
            f"1h_{sym}",
            "historical-chart/1hour",
            {"symbol": sym, "from": (ASOF - timedelta(days=730)).isoformat(), "to": ASOF.isoformat()},
            f"prices/1hour/{sym.replace('^','')}.json",
        )


def section_hours_misc() -> None:
    print("\n[MARKET HOURS / MISC]", flush=True)
    pull("all_exchange_hours", "all-exchange-market-hours", {}, "hours/all_exchanges.json")
    for ex in ("NASDAQ", "NYSE", "AMEX", "CBOE"):
        pull(f"hours_{ex}", "exchange-market-hours", {"exchange": ex}, f"hours/{ex}.json")
        pull(f"holidays_{ex}", "holidays-by-exchange", {"exchange": ex}, f"hours/holidays_{ex}.json")
    pull("treasury", "treasury-rates", {"from": START.isoformat(), "to": ASOF.isoformat()}, "econ/treasury.json")
    pull("risk_premium", "market-risk-premium", {}, "econ/risk_premium.json")
    for name in [
        "GDP", "CPI", "federalFunds", "unemploymentRate", "totalNonfarmPayroll",
        "initialClaims", "retailSales", "consumerSentiment", "inflationRate",
        "smoothedUSRecessionProbabilities",
    ]:
        pull(name, "economic-indicators", {"name": name}, f"econ/indicators/{name}.json")
    pull("crowdfunding", "crowdfunding-offerings-latest", {"page": 0}, "fundraise/crowdfunding_p0.json")
    pull("company_screener_sample", "company-screener", {"marketCapMoreThan": 10_000_000_000, "limit": 1000, "isActivelyTrading": True}, "screener/large_cap_sample.json")


def section_news() -> None:
    print("\n[NEWS FULL]", flush=True)
    for page in range(0, 30):
        if not pull(f"general_{page}", "news/general-latest", {"page": page, "limit": 100}, f"news/general/p{page:02d}.json"):
            break
    for page in range(0, 20):
        if not pull(f"fmp_{page}", "fmp-articles", {"page": page, "limit": 100}, f"news/fmp/p{page:02d}.json"):
            break
    # crypto/forex news skipped
    for sym in CORE:
        pull(f"stock_news_{sym}", "news/stock", {"symbols": sym, "limit": 1000}, f"news/stock/{sym}.json")
        pull(f"press_{sym}", "news/press-releases", {"symbols": sym, "limit": 500}, f"news/press/{sym}.json")


def main() -> int:
    print("=" * 70, flush=True)
    print("FMP ULTIMATE — FULL PLAN CATALOG DOWNLOAD", flush=True)
    print(f"OUT={OUT}", flush=True)
    print("=" * 70, flush=True)
    (OUT / "run_start.json").write_text(json.dumps({"started": now(), "out": str(OUT)}, indent=2))

    section_directory()
    section_bulk()
    section_quotes_batches()
    section_market_performance()
    section_calendars_events()
    section_senate_house_insider()
    section_institutional()
    section_sec()
    section_analyst_dcf_esg()
    section_statements_extra()
    section_tech_full()
    section_macro_assets()
    section_hours_misc()
    section_news()

    summary = {"finished": now(), "ok": _ok, "fail": _fail, "skip": _skip, "out": str(OUT)}
    (OUT / "run_done.json").write_text(json.dumps(summary, indent=2))
    print(f"\nDONE catalog ok={_ok} fail={_fail} skip={_skip}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
