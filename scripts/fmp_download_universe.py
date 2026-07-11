#!/usr/bin/env python3
"""
Aether — FMP full-universe historical download (as of 2026-07-10).

Downloads last 5 years of price history + all stable FMP endpoints available
for the Aether long + inverse universe.

API key: FMP_API_KEY in project .env only (never hardcode).
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing from .env")

BASE = "https://financialmodelingprep.com/stable"
DATA = ROOT / "data" / "fmp"
ASOF = date(2026, 7, 10)
START = ASOF - timedelta(days=365 * 5 + 2)  # ~5 years

# Aether v1 universe (longs + -1x inverses + -3x amplifiers)
LONGS = [
    "AAPL",
    "NVDA",
    "TSLA",
    "AMZN",
    "NFLX",
    "CSCO",
    "SPY",
    "QQQ",
    "IWM",
    "SPX",  # mapped to ^GSPC for FMP
]
INVERSE_1X = ["AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS", "SH", "PSQ", "RWM"]
INVERSE_3X = ["SQQQ", "SPXU", "TZA"]
ALL_SYMBOLS = LONGS + INVERSE_1X + INVERSE_3X

# FMP symbol overrides
FMP_SYMBOL = {
    "SPX": "^GSPC",
}

# Stock-like vs ETF-like for fundamentals routing
STOCKS = {"AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO"}
ETFS = set(ALL_SYMBOLS) - STOCKS - {"SPX"}
INDEXES = {"SPX"}

# Intraday intervals and safe calendar-day chunk sizes (FMP truncates responses)
INTRADAY = {
    "1min": 2,
    "5min": 5,
    "15min": 10,
    "30min": 14,
    "1hour": 30,
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherDataPipeline/1.0"})

# Gentle rate limiting
MIN_INTERVAL_S = 0.12
_last_call = 0.0


def fmp_symbol(sym: str) -> str:
    return FMP_SYMBOL.get(sym, sym)


def safe_name(sym: str) -> str:
    return sym.replace("^", "")


def throttle() -> None:
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - elapsed)
    _last_call = time.time()


def get_json(path: str, params: dict[str, Any] | None = None, retries: int = 4) -> Any:
    params = dict(params or {})
    params["apikey"] = API_KEY
    url = path if path.startswith("http") else f"{BASE}/{path.lstrip('/')}"
    last_err: Exception | None = None
    for attempt in range(retries):
        throttle()
        try:
            r = SESSION.get(url, params=params, timeout=90)
            if r.status_code == 429:
                time.sleep(2 ** attempt + 1)
                continue
            if r.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                # try parse error
                try:
                    body = r.json()
                except Exception:
                    body = r.text[:300]
                raise RuntimeError(f"HTTP {r.status_code} {url} -> {body}")
            if not r.text or not r.text.strip():
                return None
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"Failed {url}: {last_err}")


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def daterange_chunks(start: date, end: date, chunk_days: int):
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def bars_to_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows)
    # normalize column order
    cols = [c for c in ["date", "open", "high", "low", "close", "volume", "vwap", "change", "changePercent"] if c in df.columns]
    df = df[cols]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return df.reset_index(drop=True)


def download_intraday(sym: str, interval: str, chunk_days: int) -> pd.DataFrame:
    fsym = fmp_symbol(sym)
    out_dir = DATA / "ohlcv" / interval
    out_path = out_dir / f"{safe_name(sym)}.parquet"
    checkpoint = out_dir / f"{safe_name(sym)}.checkpoint.json"

    existing = pd.DataFrame()
    resume_from = START
    if out_path.exists():
        existing = pd.read_parquet(out_path)
        if len(existing):
            last = pd.to_datetime(existing["date"]).max().date()
            resume_from = max(START, last - timedelta(days=1))
            print(f"  resume {sym} {interval} from {resume_from} (have {len(existing)} bars)")

    frames: list[pd.DataFrame] = []
    if len(existing):
        frames.append(existing)

    chunks = list(daterange_chunks(resume_from, ASOF, chunk_days))
    for i, (a, b) in enumerate(chunks, 1):
        try:
            data = get_json(
                f"historical-chart/{interval}",
                {"symbol": fsym, "from": a.isoformat(), "to": b.isoformat()},
            )
            if isinstance(data, list) and data:
                frames.append(bars_to_df(data))
            if i % 25 == 0 or i == len(chunks):
                print(f"  {sym} {interval}: chunk {i}/{len(chunks)} ({a}→{b})")
                # intermediate save
                if frames:
                    df = pd.concat(frames, ignore_index=True)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
                    save_parquet(df, out_path)
                    frames = [df]
                    save_json(
                        {
                            "symbol": sym,
                            "fmp_symbol": fsym,
                            "interval": interval,
                            "last_chunk_end": b.isoformat(),
                            "rows": len(df),
                            "updated_at": datetime.utcnow().isoformat() + "Z",
                        },
                        checkpoint,
                    )
        except Exception as e:
            print(f"  WARN {sym} {interval} {a}→{b}: {e}")
            time.sleep(2)

    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    save_parquet(df, out_path)
    save_json(
        {
            "symbol": sym,
            "fmp_symbol": fsym,
            "interval": interval,
            "rows": len(df),
            "start": str(df["date"].min()) if len(df) else None,
            "end": str(df["date"].max()) if len(df) else None,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        },
        checkpoint,
    )
    return df


def download_eod(sym: str) -> pd.DataFrame:
    fsym = fmp_symbol(sym)
    out_dir = DATA / "ohlcv" / "1day"
    out_path = out_dir / f"{safe_name(sym)}.parquet"
    data = get_json(
        "historical-price-eod/full",
        {"symbol": fsym, "from": START.isoformat(), "to": ASOF.isoformat()},
    )
    if not isinstance(data, list) or not data:
        # light fallback
        data = get_json(
            "historical-price-eod/light",
            {"symbol": fsym, "from": START.isoformat(), "to": ASOF.isoformat()},
        )
    df = bars_to_df(data if isinstance(data, list) else [])
    if len(df):
        save_parquet(df, out_path)
    return df


def pull_endpoint(path: str, params: dict[str, Any], out: Path) -> bool:
    try:
        data = get_json(path, params)
        if data is None:
            return False
        if isinstance(data, list) and len(data) == 0:
            return False
        if isinstance(data, dict) and (
            data.get("Error Message") or data.get("error") or data.get("message") == "Legacy Endpoint"
        ):
            return False
        save_json(data, out)
        return True
    except Exception as e:
        print(f"  endpoint fail {path}: {e}")
        return False


def download_symbol_enrichment(sym: str) -> dict[str, bool]:
    fsym = fmp_symbol(sym)
    base = DATA / "enrichment" / safe_name(sym)
    results: dict[str, bool] = {}

    common = [
        ("quote", "quote", {"symbol": fsym}),
        ("quote_short", "quote-short", {"symbol": fsym}),
        ("profile", "profile", {"symbol": fsym}),
        ("price_change", "stock-price-change", {"symbol": fsym}),
        ("peers", "stock-peers", {"symbol": fsym}),
        ("news", "news/stock", {"symbols": fsym, "limit": 1000}),
        ("earnings", "earnings", {"symbol": fsym, "limit": 80}),
        ("splits", "splits", {"symbol": fsym}),
        ("dividends", "dividends", {"symbol": fsym}),
        ("grades", "grades", {"symbol": fsym}),
        ("grades_historical", "grades-historical", {"symbol": fsym}),
        ("price_target_summary", "price-target-summary", {"symbol": fsym}),
        ("price_target_consensus", "price-target-consensus", {"symbol": fsym}),
        ("analyst_estimates", "analyst-estimates", {"symbol": fsym, "period": "annual", "limit": 40}),
        ("analyst_estimates_q", "analyst-estimates", {"symbol": fsym, "period": "quarter", "limit": 40}),
        ("key_metrics", "key-metrics", {"symbol": fsym, "limit": 40}),
        ("key_metrics_ttm", "key-metrics-ttm", {"symbol": fsym}),
        ("ratios", "ratios", {"symbol": fsym, "limit": 40}),
        ("ratios_ttm", "ratios-ttm", {"symbol": fsym}),
        ("financial_scores", "financial-scores", {"symbol": fsym}),
        ("enterprise_values", "enterprise-values", {"symbol": fsym, "limit": 40}),
        ("owner_earnings", "owner-earnings", {"symbol": fsym}),
        ("shares_float", "shares-float", {"symbol": fsym}),
        ("market_cap_hist", "historical-market-capitalization", {
            "symbol": fsym,
            "from": START.isoformat(),
            "to": ASOF.isoformat(),
        }),
        ("insider", "insider-trading/search", {"symbol": fsym, "page": 0, "limit": 1000}),
        ("rsi_1day", "technical-indicators/rsi", {
            "symbol": fsym,
            "periodLength": 14,
            "timeframe": "1day",
            "from": START.isoformat(),
            "to": ASOF.isoformat(),
        }),
        ("sma_1day", "technical-indicators/sma", {
            "symbol": fsym,
            "periodLength": 20,
            "timeframe": "1day",
            "from": START.isoformat(),
            "to": ASOF.isoformat(),
        }),
        ("ema_1day", "technical-indicators/ema", {
            "symbol": fsym,
            "periodLength": 20,
            "timeframe": "1day",
            "from": START.isoformat(),
            "to": ASOF.isoformat(),
        }),
        ("bb_1day", "technical-indicators/bollinger", {
            "symbol": fsym,
            "periodLength": 20,
            "timeframe": "1day",
            "from": START.isoformat(),
            "to": ASOF.isoformat(),
        }),
        ("aftermarket_trade", "aftermarket-trade", {"symbol": fsym}),
        ("aftermarket_quote", "aftermarket-quote", {"symbol": fsym}),
        ("employee_count", "historical-employee-count", {"symbol": fsym}),
        ("company_notes", "company-notes", {"symbol": fsym}),
        ("key_executives", "key-executives", {"symbol": fsym}),
        ("financial_reports_dates", "financial-reports-dates", {"symbol": fsym}),
    ]

    for name, path, params in common:
        results[name] = pull_endpoint(path, params, base / f"{name}.json")

    # Financial statements — stocks mainly; try for all
    for stmt in ("income-statement", "balance-sheet-statement", "cash-flow-statement"):
        for period, label in (("annual", "annual"), ("quarter", "quarter")):
            results[f"{stmt}_{label}"] = pull_endpoint(
                stmt,
                {"symbol": fsym, "period": period, "limit": 40},
                base / f"{stmt}_{label}.json",
            )

    # ETF-specific
    if sym in ETFS:
        for name, path in (
            ("etf_info", "etf/info"),
            ("etf_holdings", "etf/holdings"),
            ("etf_sector_weightings", "etf/sector-weightings"),
            ("etf_country_weightings", "etf/country-weightings"),
        ):
            results[name] = pull_endpoint(path, {"symbol": fsym}, base / f"{name}.json")

    # More news pages if first page full
    news_path = base / "news.json"
    if news_path.exists():
        try:
            first = json.loads(news_path.read_text())
            if isinstance(first, list) and len(first) >= 100:
                all_news = list(first)
                for page in range(1, 11):
                    more = get_json("news/stock", {"symbols": fsym, "limit": 1000, "page": page})
                    if not isinstance(more, list) or not more:
                        break
                    all_news.extend(more)
                    if len(more) < 1000:
                        break
                # dedupe by url+date
                seen = set()
                deduped = []
                for item in all_news:
                    k = (item.get("url"), item.get("publishedDate"), item.get("title"))
                    if k in seen:
                        continue
                    seen.add(k)
                    deduped.append(item)
                save_json(deduped, news_path)
                results["news_pages"] = True
        except Exception as e:
            print(f"  news pagination fail {sym}: {e}")

    return results


def download_global() -> None:
    gdir = DATA / "global"
    pull_endpoint("fmp-articles", {"page": 0, "limit": 100}, gdir / "fmp_articles_p0.json")
    # a few article pages
    for p in range(1, 6):
        pull_endpoint("fmp-articles", {"page": p, "limit": 100}, gdir / f"fmp_articles_p{p}.json")
    pull_endpoint("index-list", {}, gdir / "index_list.json")
    # batch quotes
    symbols = [fmp_symbol(s) for s in ALL_SYMBOLS]
    # batch in groups of 10
    batch_all = []
    for i in range(0, len(symbols), 10):
        chunk = ",".join(symbols[i : i + 10])
        data = get_json("batch-quote", {"symbols": chunk})
        if isinstance(data, list):
            batch_all.extend(data)
    if batch_all:
        save_json(batch_all, gdir / "batch_quotes.json")


def main() -> int:
    print("=" * 70)
    print("AETHER FMP DOWNLOAD")
    print(f"Range: {START} → {ASOF} (~5 years)")
    print(f"Symbols ({len(ALL_SYMBOLS)}): {', '.join(ALL_SYMBOLS)}")
    print(f"Output: {DATA}")
    print("=" * 70)

    DATA.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "as_of": ASOF.isoformat(),
        "start": START.isoformat(),
        "symbols": ALL_SYMBOLS,
        "fmp_symbol_map": FMP_SYMBOL,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "results": {},
    }

    # Global first
    print("\n[0] Global endpoints")
    try:
        download_global()
        manifest["results"]["global"] = "ok"
    except Exception as e:
        print("global fail", e)
        manifest["results"]["global"] = str(e)

    for sym in ALL_SYMBOLS:
        print(f"\n{'='*70}\nSYMBOL {sym} (FMP={fmp_symbol(sym)})\n{'='*70}")
        sym_res: dict[str, Any] = {}

        # EOD
        print("[1] EOD daily")
        try:
            df = download_eod(sym)
            sym_res["eod_rows"] = len(df)
            print(f"  EOD rows={len(df)}")
        except Exception as e:
            sym_res["eod_error"] = str(e)
            print("  EOD fail", e)

        # Intraday
        for interval, chunk_days in INTRADAY.items():
            print(f"[2] Intraday {interval} (chunk={chunk_days}d)")
            try:
                df = download_intraday(sym, interval, chunk_days)
                sym_res[f"{interval}_rows"] = len(df)
                if len(df):
                    print(f"  {interval} rows={len(df)} range={df['date'].min()} → {df['date'].max()}")
                else:
                    print(f"  {interval} empty")
            except Exception as e:
                sym_res[f"{interval}_error"] = str(e)
                print(f"  {interval} fail", e)
                traceback.print_exc()

        # Enrichment
        print("[3] Enrichment / fundamentals / news / tech")
        try:
            er = download_symbol_enrichment(sym)
            sym_res["enrichment"] = er
            ok = sum(1 for v in er.values() if v)
            print(f"  enrichment ok={ok}/{len(er)}")
        except Exception as e:
            sym_res["enrichment_error"] = str(e)
            print("  enrichment fail", e)

        manifest["results"][sym] = sym_res
        save_json(manifest, DATA / "manifest.json")

    manifest["finished_at"] = datetime.utcnow().isoformat() + "Z"
    save_json(manifest, DATA / "manifest.json")

    # Summary report
    print("\n" + "=" * 70)
    print("DONE — summary")
    for sym, res in manifest["results"].items():
        if sym == "global":
            continue
        if not isinstance(res, dict):
            continue
        eod = res.get("eod_rows", 0)
        m5 = res.get("5min_rows", 0)
        m1 = res.get("1min_rows", 0)
        print(f"  {sym:6} eod={eod:<6} 5m={m5:<8} 1m={m1:<8}")
    print(f"Manifest: {DATA / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
