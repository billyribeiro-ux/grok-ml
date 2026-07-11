#!/usr/bin/env python3
"""
Aether FMP Batch Engine — parallel batched downloads for Ultimate plan.

- Uses ThreadPoolExecutor for concurrent HTTP (historical is 1-symbol per call)
- Hard rate limit default 25 req/s (~1500/min) under 3000/min ceiling
- Batch endpoints where FMP supports multi-symbol (quotes, lists)
- Writes under /Volumes/LaCie/Aether/data/raw/fmp/batches/

NO Databento.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

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

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/batches")
if not Path("/Volumes/LaCie/Aether").exists():
    OUT = ROOT / "data" / "fmp" / "batches"
OUT.mkdir(parents=True, exist_ok=True)

# Rate limit: 25/s = 1500/min (Ultimate allows 3000/min)
RPS = float(os.getenv("FMP_RPS", "25"))
WORKERS = int(os.getenv("FMP_WORKERS", "32"))

STOCKS = ["AAPL", "NVDA", "TSLA", "AMZN", "NFLX", "CSCO"]
ETFS = [
    "SPY", "QQQ", "IWM", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA",
    "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS",
    "XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLK", "XLU",
    "SMH", "SOXX", "XBI", "IBB", "XOP", "OIH", "KRE", "KBE", "IGV", "VGT", "VFH",
]
INDICES = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^VIX1D", "^VVIX", "^TNX", "^MOVE", "^VXN", "^RVX"]
MACRO = [
    "ESUSD", "NQUSD", "YMUSD", "RTYUSD", "CLUSD", "BZUSD", "NGUSD",
    "GCUSD", "SIUSD", "HGUSD", "DXUSD", "ZBUSD", "ZNUSD", "EURUSD", "GBPUSD", "USDJPY",
]
ALL_PRICE = list(dict.fromkeys(STOCKS + ETFS + INDICES + MACRO))

_lock = threading.Lock()
_tokens = RPS
_last = time.monotonic()
_session_local = threading.local()
_stats = {"ok": 0, "fail": 0, "skip": 0}


def session() -> requests.Session:
    if not hasattr(_session_local, "s"):
        s = requests.Session()
        s.headers.update({"User-Agent": "AetherFMPBatch/1.0"})
        _session_local.s = s
    return _session_local.s


def rate_wait() -> None:
    global _tokens, _last
    with _lock:
        now = time.monotonic()
        elapsed = now - _last
        _last = now
        _tokens = min(RPS, _tokens + elapsed * RPS)
        if _tokens < 1:
            need = (1 - _tokens) / RPS
            time.sleep(need)
            _tokens = 0
        else:
            _tokens -= 1


def get_json(path: str, params: dict | None = None, retries: int = 4) -> Any:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        rate_wait()
        try:
            r = session().get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=120)
            if r.status_code == 429:
                time.sleep(1.5 + attempt)
                continue
            if r.status_code >= 500:
                time.sleep(0.8 + attempt * 0.5)
                continue
            if r.status_code in (400, 404) or not r.text.strip():
                return None
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            time.sleep(0.5 + attempt)
    return None


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def save_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def chunked(xs: list, n: int):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def run_pool(tasks: list[Callable[[], Any]], desc: str) -> None:
    print(f"\n=== {desc}  tasks={len(tasks)} workers={WORKERS} rps={RPS} ===", flush=True)
    if not tasks:
        return
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(t) for t in tasks]
        done = 0
        for f in as_completed(futs):
            done += 1
            try:
                f.result()
            except Exception as e:
                with _lock:
                    _stats["fail"] += 1
                print(f"  task error: {e}", flush=True)
            if done % 25 == 0 or done == len(futs):
                with _lock:
                    print(
                        f"  progress {done}/{len(futs)} ok={_stats['ok']} fail={_stats['fail']} skip={_stats['skip']}",
                        flush=True,
                    )


# ---------- batch endpoints (true multi-symbol) ----------

def job_batch_snapshots() -> None:
    d = OUT / "snapshots"
    for name, path, params in [
        ("batch_quote_core", "batch-quote", {"symbols": ",".join(STOCKS + ETFS[:20])}),
        ("batch_index_quotes", "batch-index-quotes", {}),
        ("batch_commodity_quotes", "batch-commodity-quotes", {}),
        ("batch_forex_quotes", "batch-forex-quotes", {}),
        ("batch_etf_quotes", "batch-etf-quotes", {}),
        ("batch_exchange_nasdaq", "batch-exchange-quote", {"exchange": "NASDAQ"}),
        ("batch_exchange_nyse", "batch-exchange-quote", {"exchange": "NYSE"}),
        ("gainers", "biggest-gainers", {}),
        ("losers", "biggest-losers", {}),
        ("actives", "most-actives", {}),
    ]:
        data = get_json(path, params)
        if data is None:
            with _lock:
                _stats["fail"] += 1
            continue
        save_json(data, d / f"{name}.json")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            try:
                save_df(pd.DataFrame(data), d / f"{name}.parquet")
            except Exception:
                pass
        with _lock:
            _stats["ok"] += 1
        print(f"  batch OK {name} n={len(data) if isinstance(data, list) else 'obj'}", flush=True)


# ---------- parallel EOD batches ----------

def make_eod_task(sym: str, out_dir: Path):
    def _t():
        safe = sym.replace("^", "").replace("/", "_")
        out = out_dir / f"{safe}.parquet"
        if out.exists() and out.stat().st_size > 500:
            with _lock:
                _stats["skip"] += 1
            return
        data = get_json(
            "historical-price-eod/full",
            {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
        )
        if not isinstance(data, list) or not data:
            with _lock:
                _stats["fail"] += 1
            return
        df = pd.DataFrame(data)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").drop_duplicates("date", keep="last")
        save_df(df, out)
        with _lock:
            _stats["ok"] += 1

    return _t


# ---------- parallel 5min in date-chunks per symbol ----------

def make_5min_task(sym: str, years: int = 3):
    def _t():
        safe = sym.replace("^", "").replace("/", "_")
        out = OUT / "ohlcv_5min" / f"{safe}.parquet"
        if out.exists() and out.stat().st_size > 50_000:
            with _lock:
                _stats["skip"] += 1
            return
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
            with _lock:
                _stats["fail"] += 1
            return
        df = pd.concat(frames, ignore_index=True)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date", keep="last")
        save_df(df, out)
        with _lock:
            _stats["ok"] += 1
        print(f"  5m {sym}: {len(df)} bars", flush=True)

    return _t


# ---------- parallel 1min last 1 year for tier-A only ----------

def make_1min_task(sym: str, years: int = 1):
    def _t():
        safe = sym.replace("^", "").replace("/", "_")
        out = OUT / "ohlcv_1min" / f"{safe}.parquet"
        if out.exists() and out.stat().st_size > 100_000:
            with _lock:
                _stats["skip"] += 1
            return
        start = ASOF - timedelta(days=365 * years + 2)
        frames = []
        cur = start
        while cur <= ASOF:
            end = min(cur + timedelta(days=1), ASOF)
            data = get_json(
                "historical-chart/1min",
                {"symbol": sym, "from": cur.isoformat(), "to": end.isoformat()},
            )
            if isinstance(data, list) and data:
                frames.append(pd.DataFrame(data))
            cur = end + timedelta(days=1)
        if not frames:
            with _lock:
                _stats["fail"] += 1
            return
        df = pd.concat(frames, ignore_index=True)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date", keep="last")
        save_df(df, out)
        with _lock:
            _stats["ok"] += 1
        print(f"  1m {sym}: {len(df)} bars", flush=True)

    return _t


# ---------- enrichment parallel per symbol ----------

ENRICH_EPS = [
    ("profile", "profile", lambda s: {"symbol": s}),
    ("quote", "quote", lambda s: {"symbol": s}),
    ("peers", "stock-peers", lambda s: {"symbol": s}),
    ("earnings", "earnings", lambda s: {"symbol": s, "limit": 80}),
    ("grades", "grades", lambda s: {"symbol": s}),
    ("grades_consensus", "grades-consensus", lambda s: {"symbol": s}),
    ("analyst_q", "analyst-estimates", lambda s: {"symbol": s, "period": "quarter", "limit": 40}),
    ("income_q", "income-statement", lambda s: {"symbol": s, "period": "quarter", "limit": 40}),
    ("balance_q", "balance-sheet-statement", lambda s: {"symbol": s, "period": "quarter", "limit": 40}),
    ("cash_q", "cash-flow-statement", lambda s: {"symbol": s, "period": "quarter", "limit": 40}),
    ("key_metrics", "key-metrics", lambda s: {"symbol": s, "limit": 40}),
    ("ratios", "ratios", lambda s: {"symbol": s, "limit": 40}),
    ("insider", "insider-trading/search", lambda s: {"symbol": s, "page": 0, "limit": 1000}),
    ("news", "news/stock", lambda s: {"symbols": s, "limit": 1000}),
    ("press", "news/press-releases", lambda s: {"symbols": s, "limit": 500}),
    ("mktcap", "historical-market-capitalization", lambda s: {"symbol": s, "from": START.isoformat(), "to": ASOF.isoformat()}),
    ("rsi_1d", "technical-indicators/rsi", lambda s: {
        "symbol": s, "periodLength": 14, "timeframe": "1day",
        "from": START.isoformat(), "to": ASOF.isoformat(),
    }),
    ("ema_1d", "technical-indicators/ema", lambda s: {
        "symbol": s, "periodLength": 20, "timeframe": "1day",
        "from": START.isoformat(), "to": ASOF.isoformat(),
    }),
]


def make_enrich_task(sym: str):
    def _t():
        base = OUT / "enrichment" / sym.replace("^", "")
        for name, path, pfn in ENRICH_EPS:
            out = base / f"{name}.json"
            if out.exists() and out.stat().st_size > 20:
                continue
            data = get_json(path, pfn(sym))
            if data is None:
                continue
            save_json(data, out)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                try:
                    save_df(pd.DataFrame(data), base / f"{name}.parquet")
                except Exception:
                    pass
        with _lock:
            _stats["ok"] += 1
        print(f"  enrich {sym} done", flush=True)

    return _t


# ---------- calendar months in parallel ----------

def make_calendar_task(kind: str, path: str, start: date, end: date):
    def _t():
        out = OUT / "calendars" / kind / f"{start.isoformat()}_{end.isoformat()}.json"
        if out.exists():
            with _lock:
                _stats["skip"] += 1
            return
        data = get_json(path, {"from": start.isoformat(), "to": end.isoformat()})
        if not isinstance(data, list):
            with _lock:
                _stats["fail"] += 1
            return
        save_json(data, out)
        if data:
            save_df(pd.DataFrame(data), out.with_suffix(".parquet"))
        with _lock:
            _stats["ok"] += 1

    return _t


def main() -> int:
    print("=" * 70, flush=True)
    print("FMP BATCH ENGINE (parallel)", flush=True)
    print(f"OUT={OUT}  workers={WORKERS}  rps={RPS}", flush=True)
    print("=" * 70, flush=True)
    save_json(
        {
            "started": datetime.now(timezone.utc).isoformat(),
            "workers": WORKERS,
            "rps": RPS,
            "symbols": ALL_PRICE,
        },
        OUT / "batch_run_start.json",
    )

    # 1) True batch snapshots
    job_batch_snapshots()

    # 2) EOD all symbols in parallel
    eod_dir = OUT / "ohlcv_eod"
    run_pool([make_eod_task(s, eod_dir) for s in ALL_PRICE], "EOD 5y batch")

    # 3) 5min 3y parallel for all
    run_pool([make_5min_task(s, years=3) for s in ALL_PRICE], "5min 3y batch")

    # 4) 1min 1y for tier-A stocks + major ETFs/indices
    tier1 = STOCKS + ["SPY", "QQQ", "IWM", "SQQQ", "XLK", "XLF", "SMH", "^VIX", "^GSPC", "ESUSD", "NQUSD", "NVDA", "TSLA"]
    tier1 = list(dict.fromkeys(tier1))
    run_pool([make_1min_task(s, years=1) for s in tier1], "1min 1y tier-A batch")

    # 5) enrichment parallel
    enrich_syms = list(dict.fromkeys(STOCKS + ETFS + INDICES))
    run_pool([make_enrich_task(s) for s in enrich_syms], "enrichment batch")

    # 6) calendars monthly parallel
    cal_tasks = []
    for kind, path in [
        ("earnings", "earnings-calendar"),
        ("dividends", "dividends-calendar"),
        ("economic", "economic-calendar"),
    ]:
        cur = START
        while cur <= ASOF:
            end = min(cur + timedelta(days=30), ASOF)
            cal_tasks.append(make_calendar_task(kind, path, cur, end))
            cur = end + timedelta(days=1)
    run_pool(cal_tasks, "calendars monthly batch")

    # merge calendars
    for kind in ("earnings", "dividends", "economic"):
        frames = []
        cdir = OUT / "calendars" / kind
        if not cdir.exists():
            continue
        for p in sorted(cdir.glob("*.parquet")):
            try:
                frames.append(pd.read_parquet(p))
            except Exception:
                pass
        if frames:
            df = pd.concat(frames, ignore_index=True)
            save_df(df, OUT / "calendars" / f"{kind}_full.parquet")
            print(f"  merged {kind}: {len(df)}", flush=True)

    save_json(
        {
            "finished": datetime.now(timezone.utc).isoformat(),
            "stats": _stats,
            "out": str(OUT),
        },
        OUT / "batch_run_done.json",
    )
    print(f"\nDONE stats={_stats}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
