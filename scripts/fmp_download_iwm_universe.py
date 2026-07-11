#!/usr/bin/env python3
"""
Aether — IWM / Russell 2000 full holdings download for small-cap scanner ML.

Pulls ~2000 IWM constituents via FMP Ultimate in parallel batches:
  1) Holdings snapshot (weights, shares, mkt value)
  2) EOD OHLCV ~5y for ALL holdings
  3) Screener metrics (profile, quote, float, ratios, key-metrics, pe, etc.)
  4) 5-min last 1y for TOP N by weight (liquid small-cap focus)
  5) 1-min last 90d for TOP M by weight

Output:
  /Volumes/LaCie/Aether/data/raw/fmp/iwm_russell2000/

NO Databento. Rate-limited under Ultimate 3000/min.
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

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/iwm_russell2000")
if not Path("/Volumes/LaCie/Aether").exists():
    OUT = ROOT / "data" / "fmp" / "iwm_russell2000"
OUT.mkdir(parents=True, exist_ok=True)

RPS = float(os.getenv("FMP_RPS", "28"))  # ~1680/min
WORKERS = int(os.getenv("FMP_WORKERS", "40"))
TOP_5MIN = int(os.getenv("IWM_TOP_5MIN", "400"))   # top 400 by weight → 5m 1y
TOP_1MIN = int(os.getenv("IWM_TOP_1MIN", "100"))   # top 100 by weight → 1m 90d

_lock = threading.Lock()
_tokens = RPS
_last = time.monotonic()
_tls = threading.local()
_stats = {"ok": 0, "fail": 0, "skip": 0}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sess() -> requests.Session:
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.headers.update({"User-Agent": "AetherIWMScanner/1.0"})
        _tls.s = s
    return _tls.s


def rate_wait() -> None:
    global _tokens, _last
    with _lock:
        t = time.monotonic()
        elapsed = t - _last
        _last = t
        _tokens = min(RPS, _tokens + elapsed * RPS)
        if _tokens < 1:
            time.sleep((1 - _tokens) / RPS)
            _tokens = 0
        else:
            _tokens -= 1


def get_json(path: str, params: dict | None = None, retries: int = 4) -> Any:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        rate_wait()
        try:
            r = sess().get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=120)
            if r.status_code == 429:
                time.sleep(1.5 + attempt)
                continue
            if r.status_code >= 500:
                time.sleep(0.8 + attempt)
                continue
            if r.status_code in (400, 404) or not r.text.strip():
                return None
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            time.sleep(0.4 + attempt * 0.4)
    return None


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def save_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def safe_sym(s: str) -> str:
    return s.replace("/", "_").replace("^", "")


def run_pool(fns: list, desc: str) -> None:
    print(f"\n=== {desc} n={len(fns)} workers={WORKERS} rps={RPS} ===", flush=True)
    if not fns:
        return
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(fn) for fn in fns]
        done = 0
        for f in as_completed(futs):
            done += 1
            try:
                f.result()
            except Exception as e:
                with _lock:
                    _stats["fail"] += 1
                if done % 100 == 0:
                    print(f"  err: {e}", flush=True)
            if done % 50 == 0 or done == len(futs):
                with _lock:
                    print(
                        f"  {done}/{len(futs)} ok={_stats['ok']} fail={_stats['fail']} skip={_stats['skip']}",
                        flush=True,
                    )


def fetch_holdings() -> pd.DataFrame:
    print("[1] Fetch IWM holdings...", flush=True)
    data = get_json("etf/holdings", {"symbol": "IWM"})
    if not isinstance(data, list) or not data:
        raise SystemExit("Failed to fetch IWM holdings")
    df = pd.DataFrame(data)
    # asset is the constituent ticker
    if "asset" in df.columns:
        df["ticker"] = df["asset"]
    else:
        df["ticker"] = df.get("symbol")
    df = df.dropna(subset=["ticker"])
    df["ticker"] = df["ticker"].astype(str)
    # drop cash-like
    df = df[~df["ticker"].str.upper().isin(["USD", "CASH", "—", "-", "N/A"])]
    df["weightPercentage"] = pd.to_numeric(df.get("weightPercentage"), errors="coerce").fillna(0)
    df = df.sort_values("weightPercentage", ascending=False)
    # unique keep max weight row
    df = df.drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)
    save_df(df, OUT / "holdings.parquet")
    save_json(df.to_dict(orient="records"), OUT / "holdings.json")
    save_json(
        {
            "etf": "IWM",
            "name": "iShares Russell 2000 ETF",
            "n_holdings": len(df),
            "as_of": ASOF.isoformat(),
            "updated": now(),
            "top20": df.head(20)[["ticker", "name", "weightPercentage"]].to_dict(orient="records"),
        },
        OUT / "universe_meta.json",
    )
    # also etf info / sector weightings
    for name, path in [
        ("etf_info", "etf/info"),
        ("etf_sector_weightings", "etf/sector-weightings"),
        ("etf_country_weightings", "etf/country-weightings"),
    ]:
        d = get_json(path, {"symbol": "IWM"})
        if d:
            save_json(d, OUT / f"{name}.json")
    print(f"  holdings={len(df)}", flush=True)
    return df


def make_eod_task(ticker: str):
    def _t():
        out = OUT / "ohlcv_eod" / f"{safe_sym(ticker)}.parquet"
        if out.exists() and out.stat().st_size > 400:
            with _lock:
                _stats["skip"] += 1
            return
        data = get_json(
            "historical-price-eod/full",
            {"symbol": ticker, "from": START.isoformat(), "to": ASOF.isoformat()},
        )
        if not isinstance(data, list) or not data:
            data = get_json(
                "historical-price-eod/light",
                {"symbol": ticker, "from": START.isoformat(), "to": ASOF.isoformat()},
            )
        if not isinstance(data, list) or not data:
            with _lock:
                _stats["fail"] += 1
            return
        df = pd.DataFrame(data)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").drop_duplicates("date", keep="last")
        df["ticker"] = ticker
        save_df(df, out)
        with _lock:
            _stats["ok"] += 1

    return _t


def make_screener_task(ticker: str):
    """Lightweight fields for ML scanner features."""

    def _t():
        base = OUT / "screener" / safe_sym(ticker)
        marker = base / "_done.json"
        if marker.exists():
            with _lock:
                _stats["skip"] += 1
            return
        payload = {"ticker": ticker, "pulled": now()}
        for name, path, params in [
            ("quote", "quote", {"symbol": ticker}),
            ("profile", "profile", {"symbol": ticker}),
            ("shares_float", "shares-float", {"symbol": ticker}),
            ("key_metrics_ttm", "key-metrics-ttm", {"symbol": ticker}),
            ("ratios_ttm", "ratios-ttm", {"symbol": ticker}),
            ("financial_scores", "financial-scores", {"symbol": ticker}),
            ("price_change", "stock-price-change", {"symbol": ticker}),
            ("grades_consensus", "grades-consensus", {"symbol": ticker}),
            ("analyst_estimates", "analyst-estimates", {"symbol": ticker, "period": "annual", "limit": 5}),
        ]:
            data = get_json(path, params)
            if data is not None:
                save_json(data, base / f"{name}.json")
                payload[name] = True
            else:
                payload[name] = False
        save_json(payload, marker)
        with _lock:
            _stats["ok"] += 1

    return _t


def make_5min_task(ticker: str, years: int = 1):
    def _t():
        out = OUT / "ohlcv_5min" / f"{safe_sym(ticker)}.parquet"
        if out.exists() and out.stat().st_size > 20_000:
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
                {"symbol": ticker, "from": cur.isoformat(), "to": end.isoformat()},
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
        df["ticker"] = ticker
        save_df(df, out)
        with _lock:
            _stats["ok"] += 1

    return _t


def make_1min_task(ticker: str, days: int = 90):
    def _t():
        out = OUT / "ohlcv_1min" / f"{safe_sym(ticker)}.parquet"
        if out.exists() and out.stat().st_size > 20_000:
            with _lock:
                _stats["skip"] += 1
            return
        start = ASOF - timedelta(days=days)
        frames = []
        cur = start
        while cur <= ASOF:
            end = min(cur + timedelta(days=1), ASOF)
            data = get_json(
                "historical-chart/1min",
                {"symbol": ticker, "from": cur.isoformat(), "to": end.isoformat()},
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
        df["ticker"] = ticker
        save_df(df, out)
        with _lock:
            _stats["ok"] += 1

    return _t


def batch_quotes(tickers: list[str]) -> None:
    """True multi-symbol batch quotes in chunks of 50."""
    print("\n[batch-quote all IWM in chunks of 50]", flush=True)
    rows = []
    for i, chunk in enumerate(chunked(tickers, 50)):
        data = get_json("batch-quote", {"symbols": ",".join(chunk)})
        if isinstance(data, list):
            rows.extend(data)
            print(f"  quote chunk {i+1}: {len(data)}", flush=True)
    if rows:
        df = pd.DataFrame(rows)
        save_df(df, OUT / "batch_quotes_all.parquet")
        save_json(rows, OUT / "batch_quotes_all.json")
        print(f"  total quotes {len(rows)}", flush=True)


def chunked(xs: list, n: int):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def build_screener_table() -> None:
    """Flatten screener JSONs into one ML-ready parquet."""
    print("\n[build screener flat table]", flush=True)
    rows = []
    sdir = OUT / "screener"
    if not sdir.exists():
        return
    for d in sdir.iterdir():
        if not d.is_dir():
            continue
        ticker = d.name
        row: dict[str, Any] = {"ticker": ticker}
        # quote
        qf = d / "quote.json"
        if qf.exists():
            try:
                q = json.loads(qf.read_text())
                if isinstance(q, list) and q:
                    q = q[0]
                if isinstance(q, dict):
                    for k in (
                        "price", "change", "changePercentage", "volume", "averageVolume",
                        "marketCap", "pe", "eps", "yearHigh", "yearLow", "priceAvg50", "priceAvg200",
                        "open", "previousClose", "dayLow", "dayHigh",
                    ):
                        if k in q:
                            row[k] = q[k]
            except Exception:
                pass
        # profile
        pf = d / "profile.json"
        if pf.exists():
            try:
                p = json.loads(pf.read_text())
                if isinstance(p, list) and p:
                    p = p[0]
                if isinstance(p, dict):
                    for k in ("sector", "industry", "country", "exchange", "ipoDate", "isEtf", "isActivelyTrading", "beta"):
                        if k in p:
                            row[k] = p[k]
            except Exception:
                pass
        # ratios ttm
        rf = d / "ratios_ttm.json"
        if rf.exists():
            try:
                r = json.loads(rf.read_text())
                if isinstance(r, list) and r:
                    r = r[0]
                if isinstance(r, dict):
                    for k, v in r.items():
                        if k in ("symbol", "date", "period"):
                            continue
                        if isinstance(v, (int, float)) or v is None:
                            row[f"ratio_{k}"] = v
            except Exception:
                pass
        # key metrics ttm
        kf = d / "key_metrics_ttm.json"
        if kf.exists():
            try:
                k = json.loads(kf.read_text())
                if isinstance(k, list) and k:
                    k = k[0]
                if isinstance(k, dict):
                    for key, v in k.items():
                        if key in ("symbol", "date", "period"):
                            continue
                        if isinstance(v, (int, float)) or v is None:
                            row[f"metric_{key}"] = v
            except Exception:
                pass
        rows.append(row)
    if rows:
        df = pd.DataFrame(rows)
        # merge weights
        h = pd.read_parquet(OUT / "holdings.parquet")
        h = h.rename(columns={"ticker": "ticker"})
        if "ticker" in h.columns:
            df = df.merge(
                h[["ticker", "weightPercentage", "marketValue", "sharesNumber", "name"]].drop_duplicates("ticker"),
                on="ticker",
                how="left",
            )
        save_df(df, OUT / "screener_ml_table.parquet")
        save_json({"rows": len(df), "cols": list(df.columns), "updated": now()}, OUT / "screener_ml_meta.json")
        print(f"  screener table {len(df)} x {len(df.columns)}", flush=True)


def main() -> int:
    print("=" * 70, flush=True)
    print("IWM / RUSSELL 2000 — SMALL-CAP SCANNER DATA", flush=True)
    print(f"OUT={OUT}", flush=True)
    print(f"workers={WORKERS} rps={RPS} top5m={TOP_5MIN} top1m={TOP_1MIN}", flush=True)
    print("=" * 70, flush=True)

    holdings = fetch_holdings()
    tickers = holdings["ticker"].tolist()
    top5 = holdings.head(TOP_5MIN)["ticker"].tolist()
    top1 = holdings.head(TOP_1MIN)["ticker"].tolist()

    save_json(
        {
            "started": now(),
            "n": len(tickers),
            "top5min": top5[:20],
            "top1min": top1[:20],
        },
        OUT / "run_start.json",
    )

    # Batch quotes (true multi-symbol)
    batch_quotes(tickers)

    # EOD all ~2000 in parallel
    global _stats
    _stats = {"ok": 0, "fail": 0, "skip": 0}
    run_pool([make_eod_task(t) for t in tickers], "EOD 5y ALL IWM holdings")

    # Screener features all
    _stats = {"ok": 0, "fail": 0, "skip": 0}
    run_pool([make_screener_task(t) for t in tickers], "Screener metrics ALL IWM")
    build_screener_table()

    # 5min top N
    _stats = {"ok": 0, "fail": 0, "skip": 0}
    run_pool([make_5min_task(t, years=1) for t in top5], f"5min 1y TOP {TOP_5MIN}")

    # 1min top M
    _stats = {"ok": 0, "fail": 0, "skip": 0}
    run_pool([make_1min_task(t, days=90) for t in top1], f"1min 90d TOP {TOP_1MIN}")

    save_json({"finished": now(), "stats": _stats, "n_tickers": len(tickers)}, OUT / "run_done.json")
    print("\nDONE IWM universe", flush=True)
    print(f"Data: {OUT}", flush=True)
    print("ML table: screener_ml_table.parquet", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
