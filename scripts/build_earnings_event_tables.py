#!/usr/bin/env python3
"""
Build earnings event-study tables (local only).

Uses:
  - earnings_archive panels (release dates + surprises + bmo/amc)
  - per-symbol EOD JSON packs (sp500_full/iwm/nasdaq ohlcv_eod)

OUT: /Volumes/LaCie/Aether/data/processed/research/earnings_events/
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from aether.features.earnings_events import build_earnings_event_table
from aether.loaders.earnings import earnings_panel
from aether.paths import FMP_RAW, PROCESSED, require_lacie

UNIV_EOD = {
    "sp500": FMP_RAW / "sp500_full" / "ohlcv_eod",
    "iwm": FMP_RAW / "iwm_russell2000" / "ohlcv_eod",
    "nasdaq": FMP_RAW / "nasdaq_full" / "ohlcv_eod",
}


def load_prices_from_eod_pack(universe: str, symbols: list[str]) -> pd.DataFrame:
    root = UNIV_EOD[universe]
    frames: list[pd.DataFrame] = []
    for i, s in enumerate(symbols, 1):
        # try json then parquet (iwm)
        jp = root / f"{s.replace('/', '_')}.json"
        pp = root / f"{s.replace('/', '_')}.parquet"
        df = None
        if jp.exists() and jp.stat().st_size > 80:
            try:
                raw = json.loads(jp.read_text())
                if isinstance(raw, list) and raw:
                    df = pd.DataFrame(raw)
            except Exception:
                df = None
        elif pp.exists():
            try:
                df = pd.read_parquet(pp)
            except Exception:
                df = None
        if df is None or df.empty:
            continue
        if "symbol" not in df.columns:
            df = df.copy()
            df["symbol"] = s
        # normalize date/close
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        if "close" not in df.columns and "adjClose" in df.columns:
            df["close"] = df["adjClose"]
        frames.append(df)
        if i % 200 == 0:
            print(f"  [{universe}] prices {i}/{len(symbols)} frames={len(frames)}", flush=True)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def summarize(table: pd.DataFrame, universe: str, path: Path) -> dict:
    summary: dict = {
        "universe": universe,
        "window": "2018-01-01→2026-07-10",
        "n_events": int(len(table)),
        "n_symbols": int(table["symbol"].nunique()) if len(table) else 0,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "path": str(path),
    }
    if table.empty:
        return summary
    for col in ("pre_ret_1d", "pre_ret_5d", "post_ret_1d", "post_ret_5d", "gap_ret"):
        if col in table.columns:
            s = table[col].dropna()
            summary[col] = {
                "n": int(len(s)),
                "mean": float(s.mean()) if len(s) else None,
                "median": float(s.median()) if len(s) else None,
            }
    if "eps_surprise_pct" in table.columns:
        for name, mask in (
            ("beat", table["eps_surprise_pct"] > 0),
            ("miss", table["eps_surprise_pct"] < 0),
        ):
            sub = table[mask]
            summary[f"{name}_n"] = int(len(sub))
            if "post_ret_1d" in sub.columns and len(sub):
                pr = sub["post_ret_1d"].dropna()
                summary[f"{name}_post_ret_1d_mean"] = float(pr.mean()) if len(pr) else None
    if "time" in table.columns:
        summary["time_counts"] = (
            table["time"].astype(str).value_counts(dropna=False).to_dict()
        )
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universes", default="sp500,iwm", help="sp500,iwm,nasdaq")
    args = ap.parse_args()
    require_lacie()
    out = PROCESSED / "research" / "earnings_events"
    out.mkdir(parents=True, exist_ok=True)

    for u in [x.strip() for x in args.universes.split(",") if x.strip()]:
        print(f"=== {u} ===", flush=True)
        ev = earnings_panel(u)
        syms = sorted(ev["symbol"].astype(str).unique().tolist())
        print(f"events={len(ev)} symbols={len(syms)}", flush=True)
        prices = load_prices_from_eod_pack(u, syms)
        print(
            f"price rows={len(prices)} symbols="
            f"{prices['symbol'].nunique() if not prices.empty else 0}",
            flush=True,
        )
        table = build_earnings_event_table(prices, ev, universe=u)
        path = out / f"{u}_2018_20260710.parquet"
        table.to_parquet(path, index=False)
        summary = summarize(table, u, path)
        (out / f"{u}_summary.json").write_text(json.dumps(summary, indent=2, default=str))
        print(json.dumps(summary, indent=2, default=str), flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
