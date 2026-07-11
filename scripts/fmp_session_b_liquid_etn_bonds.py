#!/usr/bin/env python3
"""
Session B: liquid US equities 10-700, ETNs, bond products.

Exclusive write roots:
  /Volumes/LaCie/Aether/data/raw/fmp/liquid_10_700/
  /Volumes/LaCie/Aether/data/raw/fmp/etn/
  /Volumes/LaCie/Aether/data/raw/fmp/bonds/
  /Volumes/LaCie/Aether/logs/session_b_*.log

Do not write anywhere else on LaCie.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing in .env")

LACIE = Path("/Volumes/LaCie/Aether")
DATA_ROOT = LACIE / "data" / "raw" / "fmp"
LIQUID_ROOT = DATA_ROOT / "liquid_10_700"
ETN_ROOT = DATA_ROOT / "etn"
BONDS_ROOT = DATA_ROOT / "bonds"
LOG_DIR = LACIE / "logs"

SLEEP = float(os.getenv("FMP_SESSION_B_SLEEP", "1.0"))
if SLEEP < 1.0:
    SLEEP = 1.0

BASE = "https://financialmodelingprep.com/stable"
ASOF = "2026-07-10"
EOD_FROM = "2015-01-01"
EOD_TO = "2026-07-10"
INTRADAY_FROM = "2024-07-10"
INTRADAY_TO = "2026-07-10"

# Minimum file sizes for skip-if-exists (bytes)
MIN_EOD_BYTES = 80
MIN_FUNDAMENTAL_BYTES = 20
MIN_INTRADAY_BYTES = 80

# Caps
LIQUID_FUNDAMENTAL_CAP = None  # all if time; set to 4000 if you want a cap
TOP_EQUITIES_5MIN = 300
TOP_BOND_ETFS_5MIN = 50
TOP_ETNS_5MIN = 30

HAND_SEED_BOND_ETFS = [
    "BND", "AGG", "LQD", "HYG", "JNK", "TLT", "IEF", "IEI", "SHY", "BIL",
    "SGOV", "TIP", "MUB", "VCIT", "VCSH", "BSV", "BIV", "BLV", "GOVT",
    "SPTS", "SPTI", "SPTL", "IGSB", "IGIB", "IGLB", "SJNK", "SHYG", "EMB",
    "VWOB", "BNDX", "LQDH", "HYGH", "TBT", "TLTW", "TMF", "TMV", "PFF",
    "PGX", "SPAB", "SPAX", "SPSB", "SPIB", "SPLB", "SPHY", "SPTL", "GOVT",
    "VGIT", "VGSH", "VGLT", "VTIP", "SCHO", "SCHR", "SCHZ", "SCHP",
]

BOND_NAME_TOKENS = [
    "BOND", "TREASURY", "TREASURIES", "TIPS", "MUNICIPAL", "MUNI",
    "CORPORATE BOND", "HIGH YIELD", "AGGREGATE", "CREDIT", "DURATION",
    "TIP", "BND", "AGG", "LQD", "HYG", "TLT", "IEF", "SHY", "BIL",
    "SGOV", "VCIT", "VCSH", "GOVT", "EMB", "BNDX", "JNK", "IEI",
    "BSV", "BIV", "BLV", "MUB", "PFF", "SPTI", "SPTL", "SPTS",
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherSessionB/1.0"})


def log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def safe_filename(sym: str) -> str:
    return sym.replace("/", "_").replace("\\", "_").replace("^", "_")


class Counters:
    def __init__(self) -> None:
        self.ok = 0
        self.skip = 0
        self.miss = 0
        self.fail = 0
        self.bytes_downloaded = 0
        self.status_429_count = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "skip": self.skip,
            "miss": self.miss,
            "fail": self.fail,
            "bytes_downloaded": self.bytes_downloaded,
            "status_429_count": self.status_429_count,
        }


COUNTERS = Counters()


def get_json(path: str, params: dict | None = None, retries: int = 8) -> tuple[int, Any]:
    """Return (status, parsed_json_or_none). Sleeps after every call."""
    params = {**(params or {}), "apikey": API_KEY}
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            time.sleep(SLEEP)
            r = SESSION.get(url, params=params, timeout=120)
            if r.status_code == 429:
                COUNTERS.status_429_count += 1
                wait = min(240, 10 * (attempt + 1))
                log(f"429 on {path} attempt={attempt+1} sleep={wait}s")
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                log(f"5xx on {path} status={r.status_code} attempt={attempt+1}")
                time.sleep(2 + attempt)
                continue
            if r.status_code != 200:
                return r.status_code, None
            try:
                data = r.json()
            except Exception:
                return r.status_code, None
            return r.status_code, data
        except Exception as e:
            log(f"ERR on {path}: {e} attempt={attempt+1}")
            time.sleep(2 + attempt)
    return 0, None


def save_json_atomic(path: Path, data: Any, min_bytes: int = 10) -> bool:
    """Atomic write via .partial rename. Returns True if written or already present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= min_bytes:
        COUNTERS.skip += 1
        return True
    body = json.dumps(data, indent=2, default=str).encode("utf-8")
    if len(body) < min_bytes:
        COUNTERS.miss += 1
        log(f"MISS atomic {path.name}: body too small ({len(body)} bytes)")
        return False
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_bytes(body)
    partial.rename(path)
    COUNTERS.ok += 1
    COUNTERS.bytes_downloaded += len(body)
    return True


def fetch_save_json(name: str, api_path: str, params: dict, out_path: Path, min_bytes: int = MIN_FUNDAMENTAL_BYTES) -> bool:
    """Fetch JSON and save atomically. Skip if exists and big enough."""
    if out_path.exists() and out_path.stat().st_size >= min_bytes:
        COUNTERS.skip += 1
        return True
    status, data = get_json(api_path, params)
    if status != 200 or data is None:
        COUNTERS.miss += 1
        log(f"MISS {name} status={status}")
        return False
    if isinstance(data, list) and len(data) == 0:
        COUNTERS.miss += 1
        log(f"MISS {name}: empty list")
        return False
    ok = save_json_atomic(out_path, data, min_bytes=min_bytes)
    if ok and not (out_path.exists() and out_path.stat().st_size >= min_bytes):
        # newly written
        log(f"OK {name} -> {out_path} ({out_path.stat().st_size} bytes)")
    return ok


def looks_us(symbol: str) -> bool:
    return ":" not in symbol and not any(
        symbol.endswith(suf) for suf in [".L", ".DE", ".PA", ".AS", ".BR", ".SW", ".MI", ".MC", ".ST", ".CO", ".OL", ".HE", ".HK", ".JP", ".AU", ".TO", ".CN", ".UK"]
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1: Universes
# ──────────────────────────────────────────────────────────────────────────────

def build_liquid_universe() -> list[dict[str, Any]]:
    log("[Phase 1A] Building liquid 10-700 universe")
    LIQUID_ROOT.mkdir(parents=True, exist_ok=True)
    screener_dir = LIQUID_ROOT / "screener"
    screener_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    page = 0
    empty_pages = 0
    max_pages = 50

    while page < max_pages and empty_pages < 3:
        params = {
            "priceMoreThan": 10,
            "priceLowerThan": 700,
            "isActivelyTrading": "true",
            "isEtf": "false",
            "isFund": "false",
            "country": "US",
            "limit": 1000,
            "page": page,
        }
        status, data = get_json("company-screener", params)
        page_path = screener_dir / f"page_{page:03d}.json"
        if status == 200 and data is not None:
            save_json_atomic(page_path, data, min_bytes=2)
            rows = data if isinstance(data, list) else data.get("data", [])
            log(f"Screener page {page}: status={status} rows={len(rows)}")
            if len(rows) == 0:
                empty_pages += 1
            else:
                empty_pages = 0
            for row in rows:
                sym = str(row.get("symbol", "")).strip()
                if not sym or sym in seen_symbols:
                    continue
                seen_symbols.add(sym)
                all_rows.append({
                    "symbol": sym,
                    "price": row.get("price"),
                    "marketCap": row.get("marketCap"),
                    "volume": row.get("volume"),
                    "exchange": row.get("exchangeShortName"),
                    "sector": row.get("sector"),
                    "industry": row.get("industry"),
                    "name": row.get("companyName"),
                    "beta": row.get("beta"),
                    "lastAnnualDividend": row.get("lastAnnualDividend"),
                    "isActivelyTrading": row.get("isActivelyTrading"),
                })
        else:
            log(f"Screener page {page}: status={status} data=None")
            empty_pages += 1
        if status == 200 and isinstance(data, list) and len(data) < 1000:
            break
        page += 1

    universe = {
        "as_of": ASOF,
        "price_min": 10,
        "price_max": 700,
        "filters": ["US", "activelyTrading", "notEtf", "notFund"],
        "optionable": "NOT_VERIFIED_FMP_HAS_NO_FLAG",
        "honesty_note": "FMP has no true optionable flag; this universe is price/mcap/volume filtered only.",
        "n": len(all_rows),
        "symbols": all_rows,
    }
    save_json_atomic(LIQUID_ROOT / "screener" / "universe.json", universe, min_bytes=20)
    log(f"Liquid universe: {len(all_rows)} symbols")
    return all_rows


def build_etn_universe() -> list[dict[str, Any]]:
    log("[Phase 1B] Building ETN universe")
    ETN_ROOT.mkdir(parents=True, exist_ok=True)

    status, data = get_json("etf-list", {"limit": 10000})
    etns: list[dict[str, Any]] = []
    seen: set[str] = set()
    if status == 200 and isinstance(data, list):
        save_json_atomic(ETN_ROOT / "etf_list_raw.json", data, min_bytes=20)
        for row in data:
            sym = str(row.get("symbol", "")).strip()
            name = str(row.get("name", "")).strip()
            if not sym or not looks_us(sym):
                continue
            if "ETN" in name.upper() or "EXCHANGE TRADED NOTE" in name.upper():
                if sym not in seen:
                    seen.add(sym)
                    etns.append({
                        "symbol": sym,
                        "name": name,
                        "exchange": row.get("exchange"),
                        "source": "etf-list name filter ETN",
                    })
    else:
        log(f"etf-list fetch status={status}")

    universe = {
        "as_of": ASOF,
        "method": "Filtered /stable/etf-list for US symbols with name containing ETN or Exchange Traded Note.",
        "honesty_note": "FMP has no dedicated ETN flag; list is name-based and may miss renamed or unlabeled ETNs.",
        "n": len(etns),
        "symbols": etns,
    }
    save_json_atomic(ETN_ROOT / "universe.json", universe, min_bytes=20)
    log(f"ETN universe: {len(etns)} symbols")
    return etns


def build_bond_universe() -> list[dict[str, Any]]:
    log("[Phase 1C] Building bond product universe")
    BONDS_ROOT.mkdir(parents=True, exist_ok=True)

    status, data = get_json("etf-list", {"limit": 10000})
    bond_etfs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_sym(sym: str, name: str = "", exchange: str = "", source: str = "") -> None:
        sym = sym.strip()
        if not sym or sym in seen or not looks_us(sym):
            return
        seen.add(sym)
        bond_etfs.append({
            "symbol": sym,
            "name": name,
            "exchange": exchange,
            "source": source,
        })

    # Hand seed
    for sym in HAND_SEED_BOND_ETFS:
        add_sym(sym, source="hand_seed_major_liquid_bond_etfs")

    if status == 200 and isinstance(data, list):
        save_json_atomic(BONDS_ROOT / "etf_list_raw.json", data, min_bytes=20)
        regex = re.compile(r"\b(" + "|".join(re.escape(t) for t in BOND_NAME_TOKENS) + r")\b", re.IGNORECASE)
        for row in data:
            sym = str(row.get("symbol", "")).strip()
            name = str(row.get("name", "")).strip()
            exchange = row.get("exchange")
            if not sym or not looks_us(sym):
                continue
            if regex.search(name):
                add_sym(sym, name, exchange, "etf-list bond-token regex")
    else:
        log(f"etf-list for bonds status={status}")

    # Treasury rates
    fetch_save_json(
        "treasury_rates",
        "treasury-rates",
        {"from": EOD_FROM, "to": EOD_TO},
        BONDS_ROOT / "treasury_rates.json",
        min_bytes=20,
    )

    universe = {
        "as_of": ASOF,
        "method": "Hand-seed major liquid bond ETFs + regex filter of /stable/etf-list for bond-ish tokens.",
        "honesty_note": "FMP does not serve full bond market/TRACE. This is bond ETFs and treasury rates only.",
        "n": len(bond_etfs),
        "symbols": bond_etfs,
    }
    save_json_atomic(BONDS_ROOT / "universe.json", universe, min_bytes=20)
    log(f"Bond universe: {len(bond_etfs)} symbols")
    return bond_etfs


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2-4: Symbol-level downloads
# ──────────────────────────────────────────────────────────────────────────────

def download_eod(symbols: list[str], out_dir: Path, label: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"[EOD] {label}: {len(symbols)} symbols -> {out_dir}")
    for i, sym in enumerate(symbols, 1):
        safe = safe_filename(sym)
        out = out_dir / f"{safe}.json"
        if out.exists() and out.stat().st_size >= MIN_EOD_BYTES:
            COUNTERS.skip += 1
            if i % 500 == 0:
                log(f"  {label} eod {i}/{len(symbols)} skip={COUNTERS.skip} ok={COUNTERS.ok}")
            continue
        status, data = get_json("historical-price-eod/full", {"symbol": sym, "from": EOD_FROM, "to": EOD_TO})
        if status == 200 and data is not None:
            body = json.dumps(data, indent=2, default=str).encode("utf-8")
            if len(body) >= MIN_EOD_BYTES:
                partial = out.with_suffix(out.suffix + ".partial")
                partial.write_bytes(body)
                partial.rename(out)
                COUNTERS.ok += 1
                COUNTERS.bytes_downloaded += len(body)
            else:
                COUNTERS.miss += 1
                log(f"  MISS {label} EOD {sym}: body too small ({len(body)})")
        else:
            COUNTERS.miss += 1
            if i % 200 == 0 or status in (429, 401, 403):
                log(f"  MISS {label} EOD {sym} status={status} ({i}/{len(symbols)})")
        if i % 100 == 0:
            log(f"  {label} eod progress {i}/{len(symbols)} ok={COUNTERS.ok} skip={COUNTERS.skip} miss={COUNTERS.miss}")


def download_fundamentals_liquid(symbols: list[dict[str, Any]]) -> None:
    log("[Phase 3] Fundamentals for liquid universe")
    # Sort by volume desc
    sorted_syms = sorted(symbols, key=lambda x: x.get("volume") or 0, reverse=True)
    if LIQUID_FUNDAMENTAL_CAP:
        sorted_syms = sorted_syms[:LIQUID_FUNDAMENTAL_CAP]
        log(f"  capped to top {LIQUID_FUNDAMENTAL_CAP} by volume")

    for i, row in enumerate(sorted_syms, 1):
        sym = row["symbol"]
        safe = safe_filename(sym)
        base = LIQUID_ROOT / "screener_fundamentals" / safe
        base.mkdir(parents=True, exist_ok=True)

        # quote_freeze: copy screener row
        qf = base / "quote_freeze.json"
        if not (qf.exists() and qf.stat().st_size >= MIN_FUNDAMENTAL_BYTES):
            save_json_atomic(qf, row, min_bytes=MIN_FUNDAMENTAL_BYTES)

        fetch_save_json(f"profile_{sym}", "profile", {"symbol": sym}, base / "profile.json")
        fetch_save_json(f"float_{sym}", "shares-float", {"symbol": sym}, base / "float.json")
        fetch_save_json(f"key_metrics_ttm_{sym}", "key-metrics-ttm", {"symbol": sym}, base / "key_metrics_ttm.json")
        fetch_save_json(f"ratios_ttm_{sym}", "ratios-ttm", {"symbol": sym}, base / "ratios_ttm.json")

        if i % 100 == 0:
            log(f"  fundamentals progress {i}/{len(sorted_syms)} ok={COUNTERS.ok} skip={COUNTERS.skip} miss={COUNTERS.miss}")


def download_etn_bond_enrichment(symbols: list[dict[str, Any]], root: Path, label: str) -> None:
    log(f"[Enrichment] {label}: {len(symbols)} symbols")
    for i, row in enumerate(symbols, 1):
        sym = row["symbol"]
        safe = safe_filename(sym)
        base = root / "enrichment" / safe
        base.mkdir(parents=True, exist_ok=True)
        fetch_save_json(f"profile_{sym}", "profile", {"symbol": sym}, base / "profile.json")
        fetch_save_json(f"etf_info_{sym}", "etf/info", {"symbol": sym}, base / "etf_info.json")
        fetch_save_json(f"etf_holdings_{sym}", "etf/holdings", {"symbol": sym}, base / "etf_holdings.json")
        if i % 50 == 0:
            log(f"  {label} enrichment {i}/{len(symbols)}")


def download_intraday(symbols: list[str], out_dir: Path, label: str, timeframe: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"[{timeframe}] {label}: {len(symbols)} symbols -> {out_dir}")
    for i, sym in enumerate(symbols, 1):
        safe = safe_filename(sym)
        out = out_dir / f"{safe}.json"
        if out.exists() and out.stat().st_size >= MIN_INTRADAY_BYTES:
            COUNTERS.skip += 1
            continue
        status, data = get_json(f"historical-chart/{timeframe}", {"symbol": sym, "from": INTRADAY_FROM, "to": INTRADAY_TO})
        if status == 200 and data is not None:
            body = json.dumps(data, indent=2, default=str).encode("utf-8")
            if len(body) >= MIN_INTRADAY_BYTES:
                partial = out.with_suffix(out.suffix + ".partial")
                partial.write_bytes(body)
                partial.rename(out)
                COUNTERS.ok += 1
                COUNTERS.bytes_downloaded += len(body)
            else:
                COUNTERS.miss += 1
        else:
            COUNTERS.miss += 1
        if i % 50 == 0:
            log(f"  {label} {timeframe} progress {i}/{len(symbols)} ok={COUNTERS.ok} skip={COUNTERS.skip} miss={COUNTERS.miss}")


def download_5min(symbols: list[str], out_dir: Path, label: str) -> None:
    download_intraday(symbols, out_dir, label, "5min")


def download_1min(symbols: list[str], out_dir: Path, label: str) -> None:
    download_intraday(symbols, out_dir, label, "1min")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    log("=" * 70)
    log("Session B: liquid_10_700 / etn / bonds")
    log(f"LaCie={LACIE} sleep={SLEEP}s")
    log("=" * 70)

    if not LACIE.exists():
        log("FATAL: LaCie not mounted")
        return 1

    # Ensure exclusive roots exist
    for p in (LIQUID_ROOT, ETN_ROOT, BONDS_ROOT, LOG_DIR):
        p.mkdir(parents=True, exist_ok=True)

    run_start = {
        "started": datetime.utcnow().isoformat() + "Z",
        "sleep": SLEEP,
        "pid": os.getpid(),
        "roots": [str(LIQUID_ROOT), str(ETN_ROOT), str(BONDS_ROOT)],
    }
    save_json_atomic(LIQUID_ROOT / "run_start.json", run_start, min_bytes=2)

    # ── Phase 1: Universes ──
    liquid = build_liquid_universe()
    etns = build_etn_universe()
    bonds = build_bond_universe()

    liquid_symbols = [r["symbol"] for r in liquid]
    etn_symbols = [r["symbol"] for r in etns]
    bond_symbols = [r["symbol"] for r in bonds]

    log(f"[Phase 1 DONE] liquid={len(liquid_symbols)} etn={len(etn_symbols)} bond={len(bond_symbols)}")

    # ── Phase 2: EOD ──
    download_eod(liquid_symbols, LIQUID_ROOT / "ohlcv_eod", "liquid")
    download_eod(etn_symbols, ETN_ROOT / "ohlcv_eod", "etn")
    download_eod(bond_symbols, BONDS_ROOT / "ohlcv_eod", "bond")

    # ── Phase 3: Fundamentals ──
    download_fundamentals_liquid(liquid)
    download_etn_bond_enrichment(etns, ETN_ROOT, "etn")
    download_etn_bond_enrichment(bonds, BONDS_ROOT, "bond")

    # ── Phase 4: 5min caps ──
    # Top 300 liquid by volume
    top_equities = [r["symbol"] for r in sorted(liquid, key=lambda x: x.get("volume") or 0, reverse=True)[:TOP_EQUITIES_5MIN]]
    # Top 50 bond ETFs / 30 ETNs by volume if known, else just first N
    bond_with_vol = sorted([r for r in bonds if r.get("volume")], key=lambda x: x.get("volume", 0), reverse=True)
    bond_5min = [r["symbol"] for r in bond_with_vol[:TOP_BOND_ETFS_5MIN]] if bond_with_vol else [r["symbol"] for r in bonds[:TOP_BOND_ETFS_5MIN]]
    etn_with_vol = sorted([r for r in etns if r.get("volume")], key=lambda x: x.get("volume", 0), reverse=True)
    etn_5min = [r["symbol"] for r in etn_with_vol[:TOP_ETNS_5MIN]] if etn_with_vol else [r["symbol"] for r in etns[:TOP_ETNS_5MIN]]

    download_5min(top_equities, LIQUID_ROOT / "ohlcv_5min", "liquid_top300")
    download_5min(bond_5min, BONDS_ROOT / "ohlcv_5min", "bond_top50")
    download_5min(etn_5min, ETN_ROOT / "ohlcv_5min", "etn_top30")

    # 1min for same capped tops (user request; kept capped to avoid explosion)
    download_1min(top_equities, LIQUID_ROOT / "ohlcv_1min", "liquid_top300")
    download_1min(bond_5min, BONDS_ROOT / "ohlcv_1min", "bond_top50")
    download_1min(etn_5min, ETN_ROOT / "ohlcv_1min", "etn_top30")

    # ── Finalize ──
    run_done = {
        "finished": datetime.utcnow().isoformat() + "Z",
        "sleep": SLEEP,
        "pid": os.getpid(),
        "liquid_n": len(liquid_symbols),
        "etn_n": len(etn_symbols),
        "bond_n": len(bond_symbols),
        "daily_ohlcv_source": "ohlcv_eod (historical-price-eod/full)",
        "intraday_timeframes": ["5min", "1min"],
        "intraday_scope": "capped tops only (liquid top 300, bond top 50, etn top 30)",
        "counters": COUNTERS.to_dict(),
    }
    save_json_atomic(LIQUID_ROOT / "run_done.json", run_done, min_bytes=2)
    log("=" * 70)
    log("Session B DONE")
    log(json.dumps(run_done, indent=2))
    log("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL EXCEPTION: {e}")
        traceback.print_exc()
        sys.exit(2)
