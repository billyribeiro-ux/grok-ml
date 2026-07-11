#!/usr/bin/env python3
"""
Aether — FMP VIX products + market internals download (~5 years).

Downloads everything FMP actually serves for:
- VIX term structure & vol-of-vol indices
- Tradable VIX ETFs/ETNs
- Cross-asset vol proxies (oil/gold/rates MOVE)
- Market internals proxies available on FMP (sectors, rates, econ, breadth movers)
- Core market context indices / yields

Honest gap: classic TICK/TRIN/ADD/CPC not available on this FMP plan.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
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
DATA = ROOT / "data" / "fmp" / "vix_internals"
ASOF = date(2026, 7, 10)
START = ASOF - timedelta(days=365 * 5 + 2)

# --- VIX / volatility complex (indices) ---
VIX_INDICES = [
    "^VIX",
    "^VIX1D",
    "^VIX9D",
    "^VIX3M",
    "^VIX6M",
    "^VIX1Y",
    "^VVIX",
    "^VXN",  # Nasdaq-100 vol
    "^RVX",  # Russell 2000 vol
    "^VXD",  # DJIA vol
    "^OVX",  # oil vol
    "^GVZ",  # gold vol
    "^VXSLV",  # silver ETF vol
    "^VXTLT",  # TLT vol
    "^MOVE",  # bond vol
    "^VIN",
    "^VIF",
    "^SPOTVOL",
    "^LOVOL",
    "^VIXEQ",
    "^VXTH",
    "^VIXMO",
    "^VINMO",
    "^VIFMO",
    "^LONGVOL",
    "^SHORTVOL",
    "^DLVIX",
    "^DSVIX",
    "^DSVIER",
    "^VWA",
    "^VWB",
    "^VW1VX",
    "^VW2VX",
    "^VW3VX",
    "^VINXE",
]

# High-priority: full multi-timeframe
VIX_PRIORITY = {
    "^VIX",
    "^VIX1D",
    "^VIX9D",
    "^VIX3M",
    "^VIX6M",
    "^VIX1Y",
    "^VVIX",
    "^VXN",
    "^RVX",
    "^MOVE",
    "^OVX",
    "^GVZ",
}

# Tradable VIX / vol products
VIX_ETFS = [
    "VXX",
    "UVXY",
    "SVXY",
    "VIXY",
    "VIXM",
    "VXZ",
    "SVIX",
    "UVIX",
    "TAIL",
    "SPLV",
    "USMV",
    "TVIX",  # may be delisted legacy
    "ZIV",
    "EVIX",
]

# Market context indices / yields / dollar
MARKET_CONTEXT = [
    "^GSPC",
    "^DJI",
    "^IXIC",
    "^RUT",
    "^NYA",
    "^TNX",
    "^IRX",
    "^FVX",
    "^TYX",
    "DX-Y.NYB",
]

SECTORS = [
    "Basic Materials",
    "Communication Services",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Energy",
    "Financial Services",
    "Healthcare",
    "Industrials",
    "Real Estate",
    "Technology",
    "Utilities",
]

ECON_NAMES = [
    "GDP",
    "realGDP",
    "realGDPPerCapita",
    "federalFunds",
    "CPI",
    "inflationRate",
    "unemploymentRate",
    "totalNonfarmPayroll",
    "initialClaims",
    "retailSales",
    "consumerSentiment",
    "industrialProductionTotalIndex",
    "smoothedUSRecessionProbabilities",
    "newPrivatelyOwnedHousingUnitsStartedTotalUnits",
    "15YearFixedRateMortgageAverage",
    "30YearFixedRateMortgageAverage",
]

INTRADAY = {
    "1min": 2,
    "5min": 5,
    "15min": 10,
    "30min": 14,
    "1hour": 30,
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherVixInternals/1.0"})
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


def safe_name(sym: str) -> str:
    return (
        sym.replace("^", "")
        .replace("=", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace(" ", "_")
    )


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
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                try:
                    body = r.json()
                except Exception:
                    body = r.text[:300]
                # soft fail for bad queries
                if r.status_code in (400, 422):
                    return None
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
    cols = [c for c in ["date", "open", "high", "low", "close", "volume", "vwap", "change", "changePercent", "symbol"] if c in df.columns]
    df = df[cols]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return df


def daterange_chunks(start: date, end: date, chunk_days: int):
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def download_eod(sym: str) -> int:
    out = DATA / "ohlcv" / "1day" / f"{safe_name(sym)}.parquet"
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
    out = DATA / "ohlcv" / interval / f"{safe_name(sym)}.parquet"
    ck = DATA / "ohlcv" / interval / f"{safe_name(sym)}.checkpoint.json"
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
                        {
                            "symbol": sym,
                            "interval": interval,
                            "rows": len(df),
                            "last_chunk_end": b.isoformat(),
                            "updated_at": now_iso(),
                        },
                        ck,
                    )
                print(f"    {sym} {interval}: {i}/{len(chunks)}")
        except Exception as e:
            print(f"    WARN {sym} {interval} {a}->{b}: {e}")
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


def download_symbol_bundle(sym: str, full_intraday: bool) -> dict[str, Any]:
    res: dict[str, Any] = {"symbol": sym}
    print(f"\n=== {sym} full_intraday={full_intraday} ===")
    try:
        n = download_eod(sym)
        res["eod"] = n
        print(f"  eod={n}")
    except Exception as e:
        res["eod_error"] = str(e)
        print("  eod fail", e)

    intervals = INTRADAY if full_intraday else {"5min": 5, "1hour": 30}
    for iv, chunk in intervals.items():
        try:
            n = download_intraday(sym, iv, chunk)
            res[iv] = n
            print(f"  {iv}={n}")
        except Exception as e:
            res[f"{iv}_error"] = str(e)
            print(f"  {iv} fail", e)

    # light enrichment
    enr = DATA / "enrichment" / safe_name(sym)
    for name, path, params in [
        ("quote", "quote", {"symbol": sym}),
        ("profile", "profile", {"symbol": sym}),
        ("price_change", "stock-price-change", {"symbol": sym}),
    ]:
        try:
            data = get_json(path, params)
            if data:
                save_json(data, enr / f"{name}.json")
                res[name] = True
        except Exception:
            res[name] = False
    return res


def download_market_internals() -> dict[str, Any]:
    out: dict[str, Any] = {}
    gdir = DATA / "market_internals"
    print("\n=== MARKET INTERNALS ===")

    # Snapshots
    for name, path, params in [
        ("biggest_gainers", "biggest-gainers", {}),
        ("biggest_losers", "biggest-losers", {}),
        ("most_actives", "most-actives", {}),
        ("market_risk_premium", "market-risk-premium", {}),
        ("index_list", "index-list", {}),
        ("batch_index_quotes", "batch-index-quotes", {}),
    ]:
        try:
            data = get_json(path, params)
            if data is not None:
                save_json(data, gdir / f"{name}.json")
                out[name] = True if not isinstance(data, list) else len(data)
                print(f"  {name}: ok ({out[name]})")
        except Exception as e:
            out[name] = str(e)
            print(f"  {name} fail {e}")

    # Sector snapshots recent days + full history per sector
    print("  sector performance history...")
    for sector in SECTORS:
        try:
            data = get_json(
                "historical-sector-performance",
                {"sector": sector, "from": START.isoformat(), "to": ASOF.isoformat()},
            )
            if isinstance(data, list) and data:
                df = pd.DataFrame(data)
                save_parquet(df, gdir / "sectors" / f"{safe_name(sector)}.parquet")
                save_json(data, gdir / "sectors" / f"{safe_name(sector)}.json")
                out[f"sector_{sector}"] = len(data)
                print(f"    {sector}: {len(data)}")
        except Exception as e:
            out[f"sector_{sector}"] = str(e)

    # Recent sector/industry snapshots (last ~30 calendar days)
    snap_dir = gdir / "snapshots"
    for i in range(0, 45):
        d = ASOF - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        ds = d.isoformat()
        for label, path in [
            ("sector", "sector-performance-snapshot"),
            ("industry", "industry-performance-snapshot"),
        ]:
            try:
                data = get_json(path, {"date": ds})
                if isinstance(data, list) and data:
                    save_json(data, snap_dir / f"{label}_{ds}.json")
            except Exception:
                pass
    out["snapshots_days"] = 45

    # Treasury rates
    try:
        data = get_json("treasury-rates", {"from": START.isoformat(), "to": ASOF.isoformat()})
        if isinstance(data, list) and data:
            save_parquet(pd.DataFrame(data), gdir / "treasury_rates.parquet")
            save_json(data, gdir / "treasury_rates.json")
            out["treasury_rates"] = len(data)
            print(f"  treasury_rates: {len(data)}")
    except Exception as e:
        out["treasury_rates"] = str(e)

    # Economic indicators
    econ_dir = gdir / "economic_indicators"
    for name in ECON_NAMES:
        try:
            data = get_json("economic-indicators", {"name": name})
            if isinstance(data, list) and data:
                save_json(data, econ_dir / f"{name}.json")
                try:
                    save_parquet(pd.DataFrame(data), econ_dir / f"{name}.parquet")
                except Exception:
                    pass
                out[f"econ_{name}"] = len(data)
                print(f"  econ {name}: {len(data)}")
        except Exception as e:
            out[f"econ_{name}"] = str(e)

    # Economic calendar in monthly chunks (~5y)
    print("  economic calendar chunks...")
    cal_frames = []
    cur = START
    while cur <= ASOF:
        end = min(cur + timedelta(days=31), ASOF)
        try:
            data = get_json(
                "economic-calendar",
                {"from": cur.isoformat(), "to": end.isoformat()},
            )
            if isinstance(data, list) and data:
                cal_frames.append(pd.DataFrame(data))
                print(f"    calendar {cur}→{end}: {len(data)}")
        except Exception as e:
            print(f"    calendar fail {cur}: {e}")
        cur = end + timedelta(days=1)
    if cal_frames:
        cdf = pd.concat(cal_frames, ignore_index=True)
        # dedupe soft
        subset = [c for c in ["date", "country", "event", "currency"] if c in cdf.columns]
        if subset:
            cdf = cdf.drop_duplicates(subset=subset, keep="last")
        save_parquet(cdf, gdir / "economic_calendar.parquet")
        out["economic_calendar"] = len(cdf)
        print(f"  economic_calendar total={len(cdf)}")

    # Honest gap note
    save_json(
        {
            "unavailable_on_fmp_plan": [
                "NYSE TICK",
                "TRIN / Arms Index",
                "Advance-Decline raw ADD/ADV/DECL ticks",
                "CBOE equity/index put-call ratio series (^CPC/^CPCE) as quote symbols",
                "^SKEW (no quote on this key)",
            ],
            "proxies_downloaded_instead": [
                "sector/industry performance breadth",
                "gainers/losers/most actives snapshots",
                "VIX term structure + VVIX + MOVE",
                "treasury curve + economic indicators + calendar",
            ],
        },
        gdir / "GAPS.md.json",
    )
    return out


def main() -> int:
    print("=" * 70)
    print("AETHER FMP — VIX PRODUCTS + MARKET INTERNALS")
    print(f"Range {START} → {ASOF}")
    print(f"Out {DATA}")
    print("=" * 70)
    DATA.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "started_at": now_iso(),
        "start": START.isoformat(),
        "as_of": ASOF.isoformat(),
        "results": {},
    }

    # 1) Internals first (lighter)
    try:
        manifest["results"]["market_internals"] = download_market_internals()
    except Exception as e:
        traceback.print_exc()
        manifest["results"]["market_internals_error"] = str(e)

    # 2) VIX indices
    for sym in VIX_INDICES:
        full = sym in VIX_PRIORITY
        try:
            manifest["results"][sym] = download_symbol_bundle(sym, full_intraday=full)
        except Exception as e:
            manifest["results"][sym] = {"error": str(e)}
            traceback.print_exc()
        save_json(manifest, DATA / "manifest.json")

    # 3) VIX ETFs — full intraday for liquid names
    etf_full = {"VXX", "UVXY", "SVXY", "VIXY", "VIXM", "SVIX", "UVIX", "VXZ"}
    for sym in VIX_ETFS:
        try:
            manifest["results"][sym] = download_symbol_bundle(sym, full_intraday=sym in etf_full)
        except Exception as e:
            manifest["results"][sym] = {"error": str(e)}
        save_json(manifest, DATA / "manifest.json")

    # 4) Market context
    ctx_full = {"^GSPC", "^DJI", "^IXIC", "^RUT", "^TNX"}
    for sym in MARKET_CONTEXT:
        try:
            manifest["results"][sym] = download_symbol_bundle(sym, full_intraday=sym in ctx_full)
        except Exception as e:
            manifest["results"][sym] = {"error": str(e)}
        save_json(manifest, DATA / "manifest.json")

    manifest["finished_at"] = now_iso()
    save_json(manifest, DATA / "manifest.json")

    print("\n" + "=" * 70)
    print("DONE VIX + INTERNALS")
    # summary counts
    ok_eod = 0
    for k, v in manifest["results"].items():
        if isinstance(v, dict) and v.get("eod"):
            ok_eod += 1
            print(f"  {k:12} eod={v.get('eod')} 5m={v.get('5min')} 1m={v.get('1min')}")
    print(f"symbols_with_eod={ok_eod}")
    print(f"manifest={DATA / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
