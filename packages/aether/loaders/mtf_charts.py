"""
Multi-timeframe chart bars from LaCie MTF archive (local only, no network).

Reads skip-if-exists JSON packs written by scripts/fmp_archive_sp500_iwm_nasdaq_mtf.py:

  {universe_root}/ohlcv_{1hour|15min|5min|1min}/{SYM}.json

Honest: returns whatever is on disk; empty markers yield empty frames.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from aether.paths import FMP_RAW, require_lacie

UNIVERSE_ROOTS = {
    "sp500": FMP_RAW / "sp500_full",
    "iwm": FMP_RAW / "iwm_russell2000",
    "nasdaq": FMP_RAW / "nasdaq_full",
}

INTERVALS = ("1hour", "15min", "5min", "1min")


def universe_root(universe: str) -> Path:
    require_lacie()
    key = universe.strip().lower()
    if key not in UNIVERSE_ROOTS:
        raise ValueError(f"unknown universe={universe!r}; expected {list(UNIVERSE_ROOTS)}")
    return UNIVERSE_ROOTS[key]


def chart_dir(universe: str, interval: str) -> Path:
    iv = interval.strip().lower()
    if iv not in INTERVALS:
        raise ValueError(f"unknown interval={interval!r}; expected {INTERVALS}")
    return universe_root(universe) / f"ohlcv_{iv}"


def chart_path(universe: str, interval: str, symbol: str) -> Path:
    safe = symbol.replace("/", "_").replace("^", "")
    return chart_dir(universe, interval) / f"{safe}.json"


def inventory(universe: str = "sp500") -> pd.DataFrame:
    """Count non-empty chart files per interval for a universe."""
    require_lacie()
    rows = []
    root = universe_root(universe)
    for iv in INTERVALS:
        d = root / f"ohlcv_{iv}"
        if not d.exists():
            rows.append(
                {
                    "universe": universe,
                    "interval": iv,
                    "files": 0,
                    "nonempty": 0,
                    "empty_markers": 0,
                    "dir_exists": False,
                }
            )
            continue
        files = [p for p in d.glob("*.json") if not p.name.startswith("._")]
        nonempty = empty = 0
        for p in files:
            try:
                if p.stat().st_size < 80:
                    empty += 1
                    continue
                raw = json.loads(p.read_text())
                if isinstance(raw, dict) and raw.get("empty"):
                    empty += 1
                elif isinstance(raw, list) and len(raw) == 0:
                    empty += 1
                else:
                    nonempty += 1
            except Exception:
                empty += 1
        rows.append(
            {
                "universe": universe,
                "interval": iv,
                "files": len(files),
                "nonempty": nonempty,
                "empty_markers": empty,
                "dir_exists": True,
            }
        )
    return pd.DataFrame(rows)


def load_symbol_chart(
    symbol: str,
    interval: str = "15min",
    *,
    universe: str = "sp500",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """
    Load one symbol's bars. Columns: symbol, date (datetime), open, high, low, close, volume.
    """
    path = chart_path(universe, interval, symbol)
    if not path.exists():
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "volume"]
        )
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "volume"]
        )

    if isinstance(raw, dict):
        if raw.get("empty"):
            return pd.DataFrame(
                columns=["symbol", "date", "open", "high", "low", "close", "volume"]
            )
        rows = raw.get("bars") or raw.get("historical") or []
    elif isinstance(raw, list):
        rows = raw
    else:
        rows = []

    if not rows:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "volume"]
        )

    df = pd.DataFrame(rows)
    if "date" not in df.columns:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "volume"]
        )
    df["date"] = pd.to_datetime(df["date"])
    if "symbol" not in df.columns:
        df["symbol"] = symbol
    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        # inclusive end-of-day
        df = df[df["date"] <= pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    cols = [c for c in ["symbol", "date", "open", "high", "low", "close", "volume"] if c in df.columns]
    return df[cols].sort_values("date").reset_index(drop=True)


def load_chart_panel(
    symbols: Iterable[str],
    interval: str = "15min",
    *,
    universe: str = "sp500",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Concatenate multi-symbol chart bars (honest skip when file missing)."""
    frames = [
        load_symbol_chart(s, interval, universe=universe, start=start, end=end)
        for s in symbols
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "volume"]
        )
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(
        drop=True
    )
