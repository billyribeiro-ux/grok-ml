#!/usr/bin/env python3
"""
Aether — Expand FMP archive: full sector ETFs + inverse ETFs + IWM top-500 5m.

LaCie only. Skip-if-exists. Patient 429 backoff.
Complements bandwidth_burn + sector_etfs + iwm_russell2000 packs.

OUT: /Volumes/LaCie/Aether/data/raw/fmp/expand_sectors_inverses_iwm/
     + iwm_russell2000/ohlcv_5min/ (top-500 gap fill)
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
    raise SystemExit("LaCie not mounted")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
START_EOD = "2015-01-01"
START_5M = (ASOF - timedelta(days=730)).isoformat()
START_1M = (ASOF - timedelta(days=90)).isoformat()
END = ASOF.isoformat()

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/expand_sectors_inverses_iwm")
IWM_ROOT = Path("/Volumes/LaCie/Aether/data/raw/fmp/iwm_russell2000")
IWM_5M = IWM_ROOT / "ohlcv_5min"
OUT.mkdir(parents=True, exist_ok=True)
IWM_5M.mkdir(parents=True, exist_ok=True)

SLEEP = float(os.getenv("FMP_EXPAND_SLEEP", "0.55"))
TOP_IWM_5M = int(os.getenv("IWM_EXPAND_TOP_5M", "500"))

# Full sector / industry ETF book (matches sector_etfs script)
SECTORS = [
    "XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLK", "XLU",
    "IYW", "IYF", "IYH", "IYE", "IYJ", "IYK", "IDU", "IYR", "IYC",
    "VGT", "VFH", "VHT", "VDE", "VIS", "VAW", "VCR", "VDC", "VPU", "VOX", "VNQ",
    "SMH", "SOXX", "PSI", "XBI", "IBB", "IHE", "IHI", "IHF", "XOP", "OIH",
    "KRE", "KBE", "XHB", "ITB", "XRT", "XME", "GDX", "GDXJ", "IGV",
    "XNTK", "QTEC", "FDN", "ITA", "XAR", "JETS", "PPA", "TAN", "ICLN", "URA",
    "HACK", "SKYY", "BOTZ",
]

# Inverse / short / vol products (broad liquid set for day/swing)
INVERSES = [
    # index -1x
    "SH", "PSQ", "DOG", "RWM", "HDGE",
    # index -2x
    "SDS", "QID", "DXD", "TWM",
    # index -3x
    "SPXU", "SPXS", "SQQQ", "SDOW", "SRTY", "TZA",
    # single-stock -1x (Aether core)
    "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS",
    # single-stock -2x common
    "NVDQ", "TSLQ", "AMDS", "AAPU",  # may 404 some; skip-if-empty
    # sector -1x / -3x liquid
    "SEF", "SKF", "FAZ", "LABD", "TECS", "SOXS", "WEBS", "ERY", "DRIP", "GASX",
    "REK", "SRS", "BIS", "HIBL",  # mixed; fail soft
    # vol long/short products
    "UVXY", "SVXY", "VIXY", "VIXM", "UVIX", "SVIX", "VXX", "VXZ", "TAIL",
]

# High-signal names get 1-min 90d
INTRADAY_1M = set(
    [
        "SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XLV", "SMH", "SOXX", "XBI", "KRE", "XOP", "IGV",
        "SQQQ", "SPXU", "TZA", "SH", "PSQ", "SDS", "QID", "SDOW", "SRTY", "UVXY", "SVXY",
        "AAPD", "NVDD", "TSLS",
    ]
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherFMPExpand/1.0"})
_ok = _skip = _fail = 0
_bytes = 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get(path: str, params: dict | None = None, retries: int = 12) -> tuple[int, bytes]:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        if attempt == 0:
            time.sleep(SLEEP)
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=300)
            if r.status_code == 429:
                wait = min(240, 5 * (2 ** min(attempt, 6)))
                print(f"  429 {path} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            return r.status_code, r.content
        except Exception as e:
            print(f"  err {path}: {e}", flush=True)
            time.sleep(1 + attempt)
    return 0, b""


def save(name: str, api: str, params: dict | None, out: Path, min_bytes: int = 40) -> bool:
    global _ok, _skip, _fail, _bytes
    if out.exists() and out.stat().st_size >= min_bytes:
        _skip += 1
        return True
    st, body = get(api, params)
    if st != 200 or len(body) < min_bytes:
        _fail += 1
        # empty [] is common for dead inverse tickers
        if st == 200 and len(body) < min_bytes:
            print(f"  empty {name} len={len(body)}", flush=True)
        else:
            print(f"  MISS {name} status={st} len={len(body)}", flush=True)
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix not in (".json", ".csv", ".parquet"):
        try:
            json.loads(body)
            out = out.with_suffix(".json")
        except Exception:
            if b"," in body[:80]:
                out = out.with_suffix(".csv")
    out.write_bytes(body)
    _ok += 1
    _bytes += len(body)
    print(f"  OK {name} ({len(body)/1e6:.2f} MB)", flush=True)
    return True


def enrich_symbol(sym: str, kind: str) -> None:
    base = OUT / kind / sym
    save(f"{sym}_eod", "historical-price-eod/full", {"symbol": sym, "from": START_EOD, "to": END}, base / "eod.json", 100)
    save(f"{sym}_profile", "profile", {"symbol": sym}, base / "profile.json", 40)
    save(f"{sym}_float", "shares-float", {"symbol": sym}, base / "float.json", 8)
    save(f"{sym}_mcap", "historical-market-capitalization", {"symbol": sym, "from": START_EOD, "to": END}, base / "market_cap.json", 20)
    save(f"{sym}_key", "key-metrics", {"symbol": sym, "limit": 100}, base / "key_metrics.json", 30)
    save(f"{sym}_ratios", "ratios", {"symbol": sym, "limit": 100}, base / "ratios.json", 30)
    save(f"{sym}_growth", "financial-growth", {"symbol": sym, "limit": 60}, base / "financial_growth.json", 15)
    save(f"{sym}_est", "analyst-estimates", {"symbol": sym, "period": "annual"}, base / "analyst_estimates.json", 15)
    save(f"{sym}_grades", "grades-historical", {"symbol": sym}, base / "grades_historical.json", 15)
    save(f"{sym}_pt", "price-target-consensus", {"symbol": sym}, base / "price_target_consensus.json", 8)
    save(f"{sym}_5m", "historical-chart/5min", {"symbol": sym, "from": START_5M, "to": END}, base / "ohlcv_5min.json", 80)
    if sym in INTRADAY_1M:
        save(f"{sym}_1m", "historical-chart/1min", {"symbol": sym, "from": START_1M, "to": END}, base / "ohlcv_1min.json", 80)
    # ETF structure when applicable
    save(f"{sym}_etf_info", "etf/info", {"symbol": sym}, base / "etf_info.json", 15)
    save(f"{sym}_holdings", "etf/holdings", {"symbol": sym}, base / "etf_holdings.json", 30)
    save(f"{sym}_sec_w", "etf/sector-weightings", {"symbol": sym}, base / "etf_sector_weightings.json", 8)


def phase_sectors() -> None:
    print(f"\n[1] SECTOR/INDUSTRY ETFs enrichment n={len(SECTORS)}", flush=True)
    for i, sym in enumerate(SECTORS, 1):
        print(f"--- sector {i}/{len(SECTORS)} {sym} ---", flush=True)
        enrich_symbol(sym, "sectors")


def phase_inverses() -> None:
    # de-dupe
    seen: set[str] = set()
    inv = [s for s in INVERSES if not (s in seen or seen.add(s))]
    print(f"\n[2] INVERSE/SHORT/VOL ETFs enrichment n={len(inv)}", flush=True)
    for i, sym in enumerate(inv, 1):
        print(f"--- inverse {i}/{len(inv)} {sym} ---", flush=True)
        enrich_symbol(sym, "inverses")


def phase_iwm_top500_5m() -> None:
    print(f"\n[3] IWM top-{TOP_IWM_5M} by weight → 5min ({START_5M}→{END})", flush=True)
    holdings_path = IWM_ROOT / "holdings.json"
    if not holdings_path.exists():
        print("  MISS holdings.json", flush=True)
        return
    rows = json.loads(holdings_path.read_text())
    if not isinstance(rows, list):
        print("  bad holdings format", flush=True)
        return

    def weight(r: dict) -> float:
        try:
            return float(r.get("weightPercentage") or r.get("weight") or 0)
        except Exception:
            return 0.0

    def ticker(r: dict) -> str:
        return str(r.get("ticker") or r.get("symbol") or r.get("asset") or "").strip()

    ranked = sorted(rows, key=weight, reverse=True)
    tickers: list[str] = []
    for r in ranked:
        t = ticker(r)
        if not t or t in tickers:
            continue
        # skip weird non-US suffixes for FMP when needed; still try
        tickers.append(t)
        if len(tickers) >= TOP_IWM_5M:
            break

    print(f"  selected {len(tickers)} tickers (top weight)", flush=True)
    (OUT / "iwm_top500_tickers.json").write_text(
        json.dumps({"as_of": END, "n": len(tickers), "tickers": tickers}, indent=2)
    )

    for i, sym in enumerate(tickers, 1):
        # prefer writing into existing iwm 5min tree (json or parquet name)
        out_json = IWM_5M / f"{sym}.json"
        out_parq = IWM_5M / f"{sym}.parquet"
        if (out_parq.exists() and out_parq.stat().st_size > 1000) or (
            out_json.exists() and out_json.stat().st_size > 5000
        ):
            _skip_inc()
            if i % 50 == 0:
                print(f"  progress iwm5m {i}/{len(tickers)} skip-heavy ok={_ok}", flush=True)
            continue
        # also check expand pack
        alt = OUT / "iwm_5min" / f"{sym}.json"
        ok = save(
            f"iwm5m_{sym}",
            "historical-chart/5min",
            {"symbol": sym, "from": START_5M, "to": END},
            alt,
            min_bytes=80,
        )
        # mirror into iwm tree as json for consistency
        if ok and alt.exists() and not out_json.exists():
            try:
                out_json.write_bytes(alt.read_bytes())
            except Exception:
                pass
        if i % 25 == 0:
            print(f"  progress iwm5m {i}/{len(tickers)} ok={_ok} fail={_fail} skip={_skip}", flush=True)


def _skip_inc() -> None:
    global _skip
    _skip += 1


def main() -> int:
    print("=" * 70, flush=True)
    print("EXPAND: sectors + inverses + IWM top-500 5m", flush=True)
    print(f"OUT={OUT}", flush=True)
    print(f"sectors={len(SECTORS)} inverses={len(INVERSES)} iwm_top={TOP_IWM_5M}", flush=True)
    print("=" * 70, flush=True)
    (OUT / "run_start.json").write_text(
        json.dumps(
            {
                "started": now(),
                "as_of": END,
                "n_sectors": len(SECTORS),
                "n_inverses": len(INVERSES),
                "iwm_top_5m": TOP_IWM_5M,
            },
            indent=2,
        )
    )

    phase_sectors()
    phase_inverses()
    phase_iwm_top500_5m()

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
    print(f"\nDONE expand ok={_ok} skip={_skip} fail={_fail} mb={summary['mb']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
