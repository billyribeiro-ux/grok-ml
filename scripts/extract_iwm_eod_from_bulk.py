#!/usr/bin/env python3
"""
Ensure every IWM (Russell 2000) holding + the IWM ETF itself has
per-symbol EOD parquet under iwm_russell2000/ohlcv_eod/.

Local-only extract from archive_expiry/eod_bulk — no FMP API calls.
Skip-if-exists for non-empty files. Safe to re-run.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

EOD_BULK = Path("/Volumes/LaCie/Aether/data/raw/fmp/archive_expiry/eod_bulk")
ROOT = Path("/Volumes/LaCie/Aether/data/raw/fmp/iwm_russell2000")
OUT = ROOT / "ohlcv_eod"
HOLD = ROOT / "holdings.json"
META = ROOT / "universe_meta.json"


def safe_sym(t: str) -> str:
    return t.replace("/", "_")


def main() -> int:
    if not HOLD.exists():
        print("holdings.json missing")
        return 1
    if not EOD_BULK.exists():
        print("eod_bulk missing")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    hold = json.loads(HOLD.read_text())
    tickers: list[str] = []
    for r in hold:
        if not isinstance(r, dict):
            continue
        t = (r.get("ticker") or r.get("symbol") or r.get("asset") or "").strip()
        if t:
            tickers.append(t)
    if "IWM" not in {t.upper() for t in tickers}:
        tickers.append("IWM")
    tickers = list(dict.fromkeys(tickers))

    need = [
        t
        for t in tickers
        if not (OUT / f"{safe_sym(t)}.parquet").exists()
        or (OUT / f"{safe_sym(t)}.parquet").stat().st_size < 200
    ]
    print(f"IWM universe tickers: {len(tickers)}  need extract: {len(need)}")
    if need:
        want = set(need)
        buffers: dict[str, list[dict]] = {t: [] for t in need}
        csvs = sorted(
            p
            for p in EOD_BULK.glob("*.csv")
            if not p.name.startswith("._") and p.stat().st_size > 1000
        )
        print(f"scanning {len(csvs)} eod_bulk days…", flush=True)
        for i, csv in enumerate(csvs, 1):
            try:
                df = pd.read_csv(csv, dtype={"symbol": str}, low_memory=False)
            except Exception as e:
                print(f"  skip {csv.name}: {e}", flush=True)
                continue
            if "symbol" not in df.columns:
                continue
            df = df[df["symbol"].isin(want)]
            if df.empty:
                continue
            for sym, g in df.groupby("symbol"):
                for _, r in g.iterrows():
                    o = float(r["open"]) if pd.notna(r.get("open")) else None
                    h = float(r["high"]) if pd.notna(r.get("high")) else None
                    low = float(r["low"]) if pd.notna(r.get("low")) else None
                    c = float(r["close"]) if pd.notna(r.get("close")) else None
                    v = int(r["volume"]) if pd.notna(r.get("volume")) else 0
                    ch = (c - o) if o is not None and c is not None else 0.0
                    chp = ((c / o - 1.0) * 100.0) if o and c is not None else 0.0
                    adj = r.get("adjClose", c)
                    vwap = float(adj) if pd.notna(adj) else c
                    buffers[str(sym)].append(
                        {
                            "symbol": str(sym),
                            "date": pd.Timestamp(str(r["date"])[:10]),
                            "open": o,
                            "high": h,
                            "low": low,
                            "close": c,
                            "volume": v,
                            "change": ch,
                            "changePercent": chp,
                            "vwap": vwap,
                            "ticker": str(sym),
                        }
                    )
            if i % 500 == 0 or i == len(csvs):
                print(f"  day {i}/{len(csvs)}", flush=True)

        for sym, rows in buffers.items():
            if not rows:
                print(f"  EMPTY {sym}")
                continue
            df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
            path = OUT / f"{safe_sym(sym)}.parquet"
            df.to_parquet(path, index=False)
            print(f"  wrote {sym} bars={len(df)}", flush=True)

    files = {
        p.stem
        for p in OUT.iterdir()
        if p.suffix == ".parquet" and not p.name.startswith("._")
    }
    missing = [t for t in tickers if safe_sym(t) not in files]
    meta = json.loads(META.read_text()) if META.exists() else {}
    meta.update(
        {
            "etf": "IWM",
            "n_holdings": sum(1 for t in tickers if t.upper() != "IWM"),
            "n_tickers_with_etf": len(tickers),
            "ohlcv_eod_files": len(files),
            "ohlcv_eod_complete": len(missing) == 0,
            "includes_etf_iwm": "IWM" in files,
            "missing_ohlcv_eod": missing,
            "eod_fill_updated": datetime.now(timezone.utc).isoformat(),
        }
    )
    META.write_text(json.dumps(meta, indent=2, default=str))
    print(
        f"FINAL files={len(files)} target={len(tickers)} missing={missing} "
        f"IWM={('IWM' in files)}"
    )
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
