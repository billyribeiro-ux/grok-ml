#!/usr/bin/env python3
"""
Archive multi-timeframe history for SP500 + IWM holdings + NASDAQ batch.

Window (hard pin): 2018-01-01 → 2026-07-10
Intervals: eod (from local eod_bulk when possible), 1hour, 15min, 5min, 1min

FULL BOOK — no subsets. sp500 → iwm → nasdaq. Every symbol, every interval.

Honest notes:
- Single wide from/to returns only a short recent window; we chunk so full
  2018→2026 depth is reconstructed. We store whatever FMP returns; never invent.
- Skip-if-exists. Safe to re-run / crash-resume.
- Parallel workers (FMP_MTF_WORKERS) — Ultimate deadline is hard.

Usage:
  python scripts/fmp_archive_sp500_iwm_nasdaq_mtf.py
  FMP_MTF_WORKERS=12 FMP_MTF_SLEEP=0.08 python scripts/fmp_archive_sp500_iwm_nasdaq_mtf.py
  python scripts/fmp_archive_sp500_iwm_nasdaq_mtf.py --only sp500 --intervals 15min,5min,1min
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
LACIE = Path("/Volumes/LaCie/Aether/data/raw/fmp")
EOD_BULK = LACIE / "archive_expiry" / "eod_bulk"

START = date(2018, 1, 1)
END = date(2026, 7, 10)

# Chunk lengths (calendar days). Sized from live probes so each response stays
# under FMP's per-call bar cap (full depth only via many chunks).
CHUNK = {
    "1hour": 120,
    "15min": 30,
    "5min": 4,
    "1min": 1,
}

MIN_BYTES = {
    "eod": 80,
    "1hour": 200,
    "15min": 500,
    "5min": 1000,
    "1min": 1000,
}

SLEEP = float(os.getenv("FMP_MTF_SLEEP", "0.08"))
WORKERS = max(1, int(os.getenv("FMP_MTF_WORKERS", "12")))

_thread_local = threading.local()
_print_lock = threading.Lock()
_stats_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_sym(t: str) -> str:
    return t.replace("/", "_")


def _session() -> requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        _thread_local.session = s
    return s


def get_json(path: str, params: dict | None = None, retries: int = 6):
    p = dict(params or {})
    p["apikey"] = API_KEY
    sess = _session()
    for attempt in range(retries):
        try:
            r = sess.get(f"{BASE}/{path}", params=p, timeout=120)
        except Exception as e:
            time.sleep(1.5 + attempt)
            if attempt == retries - 1:
                with _print_lock:
                    print(f"  req err {path}: {e}", flush=True)
            continue
        if r.status_code == 429:
            time.sleep(6 + attempt * 3)
            continue
        if r.status_code != 200:
            time.sleep(0.5 + attempt * 0.5)
            continue
        try:
            return r.json()
        except Exception:
            return None
    return None

def load_sp500() -> list[str]:
    data = get_json("sp500-constituent")
    if not isinstance(data, list):
        raise SystemExit(f"sp500-constituent failed: {data}")
    syms = sorted({str(x.get("symbol", "")).strip() for x in data if x.get("symbol")})
    out = LACIE / "sp500_full"
    out.mkdir(parents=True, exist_ok=True)
    (out / "constituents.json").write_text(json.dumps(data, indent=2, default=str))
    (out / "universe_meta.json").write_text(
        json.dumps(
            {
                "universe": "sp500",
                "n": len(syms),
                "as_of_download": now(),
                "window": f"{START.isoformat()}→{END.isoformat()}",
                "source": "sp500-constituent",
            },
            indent=2,
        )
    )
    print(f"SP500 constituents n={len(syms)} AAPL={('AAPL' in syms)}", flush=True)
    return syms


def load_iwm() -> list[str]:
    hold_path = LACIE / "iwm_russell2000" / "holdings.json"
    if not hold_path.exists():
        print("IWM holdings missing — skipping iwm universe", flush=True)
        return []
    hold = json.loads(hold_path.read_text())
    syms = []
    for r in hold:
        if not isinstance(r, dict):
            continue
        t = (r.get("ticker") or r.get("symbol") or r.get("asset") or "").strip()
        if t:
            syms.append(t)
    if "IWM" not in {s.upper() for s in syms}:
        syms.append("IWM")
    syms = list(dict.fromkeys(syms))
    print(f"IWM universe n={len(syms)}", flush=True)
    return syms


def load_nasdaq() -> list[str]:
    batch = LACIE / "nasdaq_full" / "batch_exchange_nasdaq.json"
    if not batch.exists():
        print("NASDAQ batch missing — skipping nasdaq universe", flush=True)
        return []
    rows = json.loads(batch.read_text())
    syms = [str(r.get("symbol", "")).strip() for r in rows if r.get("symbol")]
    print(f"NASDAQ universe n={len(syms)}", flush=True)
    return syms


def out_dir(universe: str, interval: str) -> Path:
    root = {
        "sp500": LACIE / "sp500_full",
        "iwm": LACIE / "iwm_russell2000",
        "nasdaq": LACIE / "nasdaq_full",
    }[universe]
    # keep existing naming for iwm/nasdaq
    name = {
        "eod": "ohlcv_eod",
        "1hour": "ohlcv_1hour",
        "15min": "ohlcv_15min",
        "5min": "ohlcv_5min",
        "1min": "ohlcv_1min",
    }[interval]
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def eod_path(universe: str, sym: str) -> Path:
    d = out_dir(universe, "eod")
    # iwm uses parquet; nasdaq/sp500 use json for consistency with existing nasdaq
    if universe == "iwm":
        return d / f"{safe_sym(sym)}.parquet"
    return d / f"{safe_sym(sym)}.json"


def chart_path(universe: str, interval: str, sym: str) -> Path:
    return out_dir(universe, interval) / f"{safe_sym(sym)}.json"


def extract_eod_from_bulk(universe: str, symbols: list[str]) -> None:
    """Fill/refresh EOD from local eod_bulk, filtered to START..END. No API."""
    if not EOD_BULK.exists():
        print("eod_bulk missing — skip bulk EOD extract", flush=True)
        return
    want = set(symbols)
    need = []
    for s in symbols:
        p = eod_path(universe, s)
        if not p.exists() or p.stat().st_size < MIN_BYTES["eod"]:
            need.append(s)
    # Always re-slice if file exists but we want window pin? For speed only fill missing.
    # Optionally trim existing later.
    print(f"[{universe}] EOD bulk extract need={len(need)}/{len(symbols)}", flush=True)
    if not need:
        return
    buffers: dict[str, list[dict]] = {s: [] for s in need}
    want_need = set(need)
    csvs = sorted(
        p
        for p in EOD_BULK.glob("*.csv")
        if not p.name.startswith("._") and p.stat().st_size > 1000
    )
    # only days in window
    day_csvs = []
    for p in csvs:
        try:
            d = date.fromisoformat(p.stem)
        except ValueError:
            continue
        if START <= d <= END:
            day_csvs.append(p)
    print(f"[{universe}] scanning {len(day_csvs)} bulk days in window…", flush=True)
    for i, csv in enumerate(day_csvs, 1):
        try:
            df = pd.read_csv(csv, dtype={"symbol": str}, low_memory=False)
        except Exception:
            continue
        if "symbol" not in df.columns:
            continue
        df = df[df["symbol"].isin(want_need)]
        if df.empty:
            continue
        for sym, g in df.groupby("symbol"):
            for _, r in g.iterrows():
                buffers[str(sym)].append(
                    {
                        "symbol": str(sym),
                        "date": str(r.get("date", csv.stem))[:10],
                        "open": float(r["open"]) if pd.notna(r.get("open")) else None,
                        "high": float(r["high"]) if pd.notna(r.get("high")) else None,
                        "low": float(r["low"]) if pd.notna(r.get("low")) else None,
                        "close": float(r["close"]) if pd.notna(r.get("close")) else None,
                        "volume": int(r["volume"]) if pd.notna(r.get("volume")) else 0,
                        "change": None,
                        "changePercent": None,
                        "vwap": float(r["adjClose"])
                        if "adjClose" in r and pd.notna(r.get("adjClose"))
                        else (float(r["close"]) if pd.notna(r.get("close")) else None),
                    }
                )
        if i % 400 == 0 or i == len(day_csvs):
            print(f"  [{universe}] eod day {i}/{len(day_csvs)}", flush=True)

    wrote = 0
    for sym, rows in buffers.items():
        if not rows:
            continue
        rows = sorted(rows, key=lambda x: x["date"])
        path = eod_path(universe, sym)
        if universe == "iwm":
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df["ticker"] = sym
            df.to_parquet(path, index=False)
        else:
            path.write_text(json.dumps(rows, default=str))
        wrote += 1
    print(f"[{universe}] wrote {wrote} EOD files from bulk", flush=True)


def trim_eod_to_window(universe: str, symbols: list[str]) -> None:
    """Slice existing EOD packs to START..END (local only)."""
    n = 0
    for sym in symbols:
        path = eod_path(universe, sym)
        if not path.exists() or path.stat().st_size < MIN_BYTES["eod"]:
            continue
        try:
            if path.suffix == ".parquet":
                df = pd.read_parquet(path)
                if "date" not in df.columns:
                    continue
                df["date"] = pd.to_datetime(df["date"])
                trimmed = df[
                    (df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))
                ]
                if len(trimmed) < len(df):
                    trimmed.to_parquet(path, index=False)
                    n += 1
            else:
                rows = json.loads(path.read_text())
                if not isinstance(rows, list):
                    continue
                trimmed = [
                    r
                    for r in rows
                    if isinstance(r, dict)
                    and r.get("date")
                    and START.isoformat() <= str(r["date"])[:10] <= END.isoformat()
                ]
                if len(trimmed) != len(rows):
                    path.write_text(json.dumps(trimmed, default=str))
                    n += 1
        except Exception:
            continue
    print(f"[{universe}] trimmed {n} EOD files to window", flush=True)


def fetch_chart(sym: str, interval: str) -> list[dict]:
    """Pull chart bars for interval over START..END in chunks."""
    chunk_days = CHUNK[interval]
    frames: list[dict] = []
    cur = START
    while cur <= END:
        end = min(cur + timedelta(days=chunk_days - 1), END)
        data = get_json(
            f"historical-chart/{interval}",
            {"symbol": sym, "from": cur.isoformat(), "to": end.isoformat()},
        )
        if SLEEP > 0:
            time.sleep(SLEEP)
        if isinstance(data, list) and data:
            for row in data:
                if not isinstance(row, dict):
                    continue
                frames.append(
                    {
                        "symbol": sym,
                        "date": row.get("date"),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "volume": row.get("volume"),
                    }
                )
        cur = end + timedelta(days=1)
    if not frames:
        return []
    seen: set[str] = set()
    out: list[dict] = []
    for r in sorted(frames, key=lambda x: x.get("date") or ""):
        k = str(r.get("date") or "")
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _write_chart(path: Path, sym: str, interval: str, bars: list[dict]) -> str:
    """Write bars or honest empty marker. Returns 'ok' | 'empty'."""
    if not bars:
        path.write_text(
            json.dumps(
                {
                    "symbol": sym,
                    "interval": interval,
                    "window": f"{START}→{END}",
                    "bars": [],
                    "empty": True,
                    "note": "FMP returned no bars for this window/interval",
                    "pulled_at": now(),
                },
                indent=2,
            )
        )
        return "empty"
    path.write_text(json.dumps(bars, default=str))
    return "ok"


def archive_charts(universe: str, symbols: list[str], intervals: list[str]) -> None:
    for interval in intervals:
        if interval == "eod":
            continue
        need: list[str] = []
        skip = 0
        for sym in symbols:
            path = chart_path(universe, interval, sym)
            if path.exists() and path.stat().st_size >= MIN_BYTES.get(interval, 200):
                skip += 1
            else:
                need.append(sym)

        print(
            f"[{universe}] chart {interval} need={len(need)}/{len(symbols)} "
            f"skip={skip} workers={WORKERS} sleep={SLEEP}s chunk={CHUNK[interval]}d",
            flush=True,
        )
        if not need:
            print(f"[{universe}] {interval} done ok=0 skip={skip} empty=0", flush=True)
            continue

        ok = empty = fail = 0
        done = 0
        total = len(need)

        def one(sym: str) -> tuple[str, str]:
            path = chart_path(universe, interval, sym)
            try:
                bars = fetch_chart(sym, interval)
                status = _write_chart(path, sym, interval, bars)
                return sym, status
            except Exception as e:
                with _print_lock:
                    print(f"  fail {sym}/{interval}: {e}", flush=True)
                return sym, "fail"

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(one, s): s for s in need}
            for fut in as_completed(futs):
                _sym, status = fut.result()
                with _stats_lock:
                    if status == "ok":
                        ok += 1
                    elif status == "empty":
                        empty += 1
                    else:
                        fail += 1
                    done += 1
                    d, o, e, f = done, ok, empty, fail
                if d % 10 == 0 or d == total:
                    with _print_lock:
                        print(
                            f"  [{universe}/{interval}] {d}/{total} "
                            f"ok={o} empty={e} fail={f} (prior_skip={skip})",
                            flush=True,
                        )
        print(
            f"[{universe}] {interval} done ok={ok} skip={skip} empty={empty} fail={fail}",
            flush=True,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only",
        default="sp500,iwm,nasdaq",
        help="comma list: sp500,iwm,nasdaq",
    )
    ap.add_argument(
        "--intervals",
        default="eod,1hour,15min,5min,1min",
        help="comma list of intervals",
    )
    ap.add_argument("--workers", type=int, default=0, help="override FMP_MTF_WORKERS")
    args = ap.parse_args()
    global WORKERS
    if args.workers > 0:
        WORKERS = args.workers

    universes = [u.strip() for u in args.only.split(",") if u.strip()]
    intervals = [i.strip() for i in args.intervals.split(",") if i.strip()]

    print(
        f"MTF archive window {START}→{END} universes={universes} intervals={intervals} "
        f"workers={WORKERS} sleep={SLEEP}",
        flush=True,
    )
    print(f"started {now()}", flush=True)

    loaders = {
        "sp500": load_sp500,
        "iwm": load_iwm,
        "nasdaq": load_nasdaq,
    }
    for u in universes:
        if u not in loaders:
            print(f"unknown universe {u}", flush=True)
            continue
        syms = loaders[u]()
        if not syms:
            continue
        if "eod" in intervals:
            extract_eod_from_bulk(u, syms)
            trim_eod_to_window(u, syms)
        chart_iv = [i for i in intervals if i != "eod"]
        if chart_iv:
            archive_charts(u, syms, chart_iv)
        root = {
            "sp500": LACIE / "sp500_full",
            "iwm": LACIE / "iwm_russell2000",
            "nasdaq": LACIE / "nasdaq_full",
        }[u]
        (root / "mtf_run_stamp.json").write_text(
            json.dumps(
                {
                    "window": f"{START}→{END}",
                    "intervals": intervals,
                    "n_symbols": len(syms),
                    "workers": WORKERS,
                    "finished_at": now(),
                },
                indent=2,
            )
        )

    print(f"ALL DONE {now()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
