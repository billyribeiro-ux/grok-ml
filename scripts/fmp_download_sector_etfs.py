#!/usr/bin/env python3
"""
Aether — FMP sector / industry ETF universe download (~5 years).

Includes:
- SPDR Select Sector 11 (XL*)
- Vanguard + iShares sector ETFs
- High-signal industry ETFs (semis, biotech, banks, energy services, etc.)

Per symbol: OHLCV multi-TF + ETF info/holdings/weightings when available.
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
DATA = ROOT / "data" / "fmp" / "sector_etfs"
ASOF = date(2026, 7, 10)
START = ASOF - timedelta(days=365 * 5 + 2)

# SPDR Select Sector — full multi-timeframe (primary sector rotation map)
SPDR_SECTORS = [
    "XLC",  # Communication
    "XLY",  # Consumer Discretionary
    "XLP",  # Consumer Staples
    "XLE",  # Energy
    "XLF",  # Financials
    "XLV",  # Health Care
    "XLI",  # Industrials
    "XLB",  # Materials
    "XLRE",  # Real Estate
    "XLK",  # Technology
    "XLU",  # Utilities
]

# Companion sector families
ISHARES_SECTOR = ["IYW", "IYF", "IYH", "IYE", "IYJ", "IYK", "IDU", "IYR", "IYC"]
VANGUARD_SECTOR = ["VGT", "VFH", "VHT", "VDE", "VIS", "VAW", "VCR", "VDC", "VPU", "VOX", "VNQ"]

# Industry / thematic (rotation + risk regime)
INDUSTRY = [
    "SMH",
    "SOXX",
    "PSI",
    "XBI",
    "IBB",
    "IHE",
    "IHI",
    "IHF",
    "XOP",
    "OIH",
    "KRE",
    "KBE",
    "XHB",
    "ITB",
    "XRT",
    "XME",
    "GDX",
    "GDXJ",
    "IGV",
    "XNTK",
    "QTEC",
    "FDN",
    "ITA",
    "XAR",
    "JETS",
    "PPA",
    "TAN",
    "ICLN",
    "URA",
    "HACK",
    "SKYY",
    "BOTZ",
]

ALL = SPDR_SECTORS + ISHARES_SECTOR + VANGUARD_SECTOR + INDUSTRY
# de-dupe preserve order
_seen: set[str] = set()
ALL_SYMBOLS = [s for s in ALL if not (s in _seen or _seen.add(s))]

FULL_INTRADAY = set(SPDR_SECTORS) | {"SMH", "SOXX", "XBI", "KRE", "XOP", "XLF", "XLK", "XLE", "IGV"}

INTRADAY = {
    "1min": 2,
    "5min": 5,
    "15min": 10,
    "30min": 14,
    "1hour": 30,
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherSectorETFs/1.0"})
MIN_INTERVAL_S = 0.12
_last = 0.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def throttle() -> None:
    global _last
    dt = time.time() - _last
    if dt < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - dt)
    _last = time.time()


def get_json(path: str, params: dict[str, Any] | None = None, retries: int = 4) -> Any:
    params = dict(params or {})
    params["apikey"] = API_KEY
    url = f"{BASE}/{path.lstrip('/')}"
    last = None
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
            if r.status_code in (404, 400):
                return None
            if r.status_code != 200:
                try:
                    body = r.json()
                except Exception:
                    body = r.text[:200]
                raise RuntimeError(f"HTTP {r.status_code} {path} {body}")
            if not r.text.strip():
                return None
            return r.json()
        except Exception as e:
            last = e
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"Failed {path}: {last}")


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def bars_to_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows)
    cols = [c for c in ["date", "open", "high", "low", "close", "volume", "vwap", "change", "changePercent"] if c in df.columns]
    df = df[cols]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def daterange_chunks(start: date, end: date, chunk_days: int):
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def download_eod(sym: str) -> int:
    out = DATA / "ohlcv" / "1day" / f"{sym}.parquet"
    data = get_json(
        "historical-price-eod/full",
        {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
    )
    if not isinstance(data, list) or not data:
        data = get_json(
            "historical-price-eod/light",
            {"symbol": sym, "from": START.isoformat(), "to": ASOF.isoformat()},
        )
    df = bars_to_df(data if isinstance(data, list) else [])
    if len(df):
        save_parquet(df, out)
    return len(df)


def download_intraday(sym: str, interval: str, chunk_days: int) -> int:
    out = DATA / "ohlcv" / interval / f"{sym}.parquet"
    ck = DATA / "ohlcv" / interval / f"{sym}.checkpoint.json"
    existing = pd.DataFrame()
    resume = START
    if out.exists():
        existing = pd.read_parquet(out)
        if len(existing):
            resume = max(START, pd.to_datetime(existing["date"]).max().date() - timedelta(days=1))
    frames: list[pd.DataFrame] = [existing] if len(existing) else []
    chunks = list(daterange_chunks(resume, ASOF, chunk_days))
    for i, (a, b) in enumerate(chunks, 1):
        try:
            data = get_json(
                f"historical-chart/{interval}",
                {"symbol": sym, "from": a.isoformat(), "to": b.isoformat()},
            )
            if isinstance(data, list) and data:
                frames.append(bars_to_df(data))
            if i % 40 == 0 or i == len(chunks):
                if frames:
                    df = pd.concat(frames, ignore_index=True)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
                    save_parquet(df, out)
                    frames = [df]
                    save_json(
                        {"symbol": sym, "interval": interval, "rows": len(df), "last_chunk_end": b.isoformat(), "updated_at": now_iso()},
                        ck,
                    )
                print(f"    {sym} {interval}: {i}/{len(chunks)}", flush=True)
        except Exception as e:
            print(f"    WARN {sym} {interval} {a}->{b}: {e}", flush=True)
            time.sleep(1.5)
    if not frames:
        return 0
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    save_parquet(df, out)
    save_json(
        {
            "symbol": sym,
            "interval": interval,
            "rows": len(df),
            "start": str(df["date"].min()) if len(df) else None,
            "end": str(df["date"].max()) if len(df) else None,
            "updated_at": now_iso(),
        },
        ck,
    )
    return len(df)


def download_etf_meta(sym: str) -> dict[str, bool]:
    enr = DATA / "enrichment" / sym
    res: dict[str, bool] = {}
    for name, path in [
        ("quote", "quote"),
        ("profile", "profile"),
        ("etf_info", "etf/info"),
        ("etf_holdings", "etf/holdings"),
        ("etf_sector_weightings", "etf/sector-weightings"),
        ("etf_country_weightings", "etf/country-weightings"),
        ("price_change", "stock-price-change"),
    ]:
        try:
            data = get_json(path, {"symbol": sym})
            if data:
                save_json(data, enr / f"{name}.json")
                res[name] = True
            else:
                res[name] = False
        except Exception:
            res[name] = False
    return res


def download_symbol(sym: str) -> dict[str, Any]:
    full = sym in FULL_INTRADAY
    print(f"\n=== {sym} full_intraday={full} ===", flush=True)
    res: dict[str, Any] = {"symbol": sym, "full_intraday": full}
    try:
        res["eod"] = download_eod(sym)
        print(f"  eod={res['eod']}", flush=True)
    except Exception as e:
        res["eod_error"] = str(e)
        print(f"  eod fail {e}", flush=True)

    intervals = INTRADAY if full else {"5min": 5, "15min": 10, "1hour": 30}
    for iv, chunk in intervals.items():
        try:
            n = download_intraday(sym, iv, chunk)
            res[iv] = n
            print(f"  {iv}={n}", flush=True)
        except Exception as e:
            res[f"{iv}_error"] = str(e)
            print(f"  {iv} fail {e}", flush=True)

    res["meta"] = download_etf_meta(sym)
    return res


def main() -> int:
    print("=" * 70, flush=True)
    print("AETHER FMP — SECTOR / INDUSTRY ETFs", flush=True)
    print(f"Symbols: {len(ALL_SYMBOLS)}  Range: {START} → {ASOF}", flush=True)
    print(f"Out: {DATA}", flush=True)
    print("=" * 70, flush=True)
    DATA.mkdir(parents=True, exist_ok=True)
    save_json(
        {
            "spdr_select_sector": SPDR_SECTORS,
            "ishares_sector": ISHARES_SECTOR,
            "vanguard_sector": VANGUARD_SECTOR,
            "industry_thematic": INDUSTRY,
            "all": ALL_SYMBOLS,
            "full_intraday": sorted(FULL_INTRADAY),
        },
        DATA / "universe.json",
    )

    manifest: dict[str, Any] = {
        "started_at": now_iso(),
        "start": START.isoformat(),
        "as_of": ASOF.isoformat(),
        "symbols": ALL_SYMBOLS,
        "results": {},
    }

    for sym in ALL_SYMBOLS:
        try:
            manifest["results"][sym] = download_symbol(sym)
        except Exception as e:
            manifest["results"][sym] = {"error": str(e)}
            print(f"FAIL {sym}: {e}", flush=True)
        save_json(manifest, DATA / "manifest.json")

    manifest["finished_at"] = now_iso()
    save_json(manifest, DATA / "manifest.json")
    print("\nDONE sector ETFs", flush=True)
    for s, r in manifest["results"].items():
        if isinstance(r, dict):
            print(f"  {s:6} eod={r.get('eod')} 5m={r.get('5min')} 1m={r.get('1min')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
