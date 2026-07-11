"""Load per-symbol OHLCV JSON dumps (liquid/bonds/etn archives) into panels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pandas as pd


def load_symbol_json_dir(
    directory: Path,
    symbols: Sequence[str] | None = None,
    *,
    max_symbols: int | None = None,
) -> pd.DataFrame:
    """
    Read `{SYMBOL}.json` files written by session-b style archives.
    Expected rows: date/open/high/low/close/adjClose|adj_close/volume.
    Skips multi-listed suffixes (e.g. AAPL.NE) unless explicitly requested.
    """
    if not directory.is_dir():
        return pd.DataFrame()

    files = sorted(
        p
        for p in directory.glob("*.json")
        if not p.name.startswith("._") and p.stat().st_size > 50
    )
    wanted = {s.upper() for s in symbols} if symbols else None
    frames: list[pd.DataFrame] = []
    for p in files:
        stem = p.stem.upper()
        # default: only plain US-like tickers without dots
        if wanted is None and "." in stem:
            continue
        if wanted is not None and stem not in wanted:
            continue
        try:
            raw = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(raw, list) or not raw:
            continue
        df = pd.DataFrame(raw)
        # normalize columns
        colmap = {c: c for c in df.columns}
        for a, b in (
            ("adjClose", "adj_close"),
            ("Adj Close", "adj_close"),
            ("date", "date"),
        ):
            if a in df.columns:
                colmap[a] = b
        df = df.rename(columns=colmap)
        need = {"date", "open", "high", "low", "close"}
        if not need.issubset(df.columns):
            continue
        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]
        if "volume" not in df.columns:
            df["volume"] = 0
        df["symbol"] = stem
        df["date"] = pd.to_datetime(df["date"], utc=False, errors="coerce")
        df = df.dropna(subset=["date", "close"])
        frames.append(
            df[["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]]
        )
        if max_symbols is not None and len(frames) >= max_symbols:
            break
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
    return out
