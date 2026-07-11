#!/usr/bin/env python3
"""
Extract NASDAQ per-symbol EOD from full-market eod_bulk CSVs.

This is a local-only rescue pass to finish NASDAQ ohlcv_eod much faster
than hitting FMP for 14k symbols one-by-one. It reads the already-downloaded
bulk daily files, filters rows for NASDAQ batch symbols, and writes
nasdaq_full/ohlcv_eod/{sym}.json in the same shape the FMP endpoint returns.

Skip-if-exists. Safe to re-run. Never deletes source data.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

EOD_BULK = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk")
NASDAQ_BATCH = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full/batch_exchange_nasdaq.json")
OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/nasdaq_full/ohlcv_eod")


def main() -> int:
    if not NASDAQ_BATCH.exists():
        print("NASDAQ batch file missing")
        return 1
    if not EOD_BULK.exists():
        print("eod_bulk directory missing")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)

    rows = json.loads(NASDAQ_BATCH.read_text())
    nasdaq_symbols = {str(r.get("symbol", "")).strip() for r in rows if r.get("symbol")}
    print(f"NASDAQ symbols: {len(nasdaq_symbols)}")

    csvs = sorted(EOD_BULK.glob("*.csv"))
    print(f"eod_bulk files: {len(csvs)}")

    # Pre-build output paths so we can check skip
    sym_to_path = {sym: OUT / f"{sym.replace('/', '_')}.json" for sym in nasdaq_symbols}
    missing = {sym for sym, p in sym_to_path.items() if not p.exists() or p.stat().st_size < 80}
    print(f"symbols still needing output: {len(missing)}")
    if not missing:
        print("All NASDAQ EOD files already exist. Nothing to do.")
        return 0

    # For each bulk day, read CSV and append rows for missing symbols
    buffers: dict[str, list[dict]] = {sym: [] for sym in missing}

    for i, csv in enumerate(csvs, 1):
        try:
            df = pd.read_csv(csv, dtype={"symbol": str})
        except Exception as e:
            print(f"  skip {csv.name}: {e}")
            continue

        if "symbol" not in df.columns or "date" not in df.columns:
            continue

        df = df[df["symbol"].isin(missing)]
        if df.empty:
            continue

        for sym, grp in df.groupby("symbol"):
            for _, r in grp.iterrows():
                buffers[sym].append({
                    "symbol": sym,
                    "date": str(r["date"]),
                    "open": float(r["open"]) if pd.notna(r.get("open")) else None,
                    "high": float(r["high"]) if pd.notna(r.get("high")) else None,
                    "low": float(r["low"]) if pd.notna(r.get("low")) else None,
                    "close": float(r["close"]) if pd.notna(r.get("close")) else None,
                    "volume": int(r["volume"]) if pd.notna(r.get("volume")) else None,
                })

        if i % 100 == 0:
            print(f"  processed {i}/{len(csvs)} bulk files")

    print("Writing per-symbol JSON files...")
    written = 0
    for sym in missing:
        buf = buffers[sym]
        if not buf:
            continue
        # sort by date ascending
        buf.sort(key=lambda x: x["date"])
        p = sym_to_path[sym]
        p.write_text(json.dumps(buf, indent=2, default=str))
        written += 1

    print(f"Wrote {written} NASDAQ EOD files to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
