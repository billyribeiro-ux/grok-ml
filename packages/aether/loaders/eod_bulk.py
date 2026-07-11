"""Load full-market daily bars from FMP eod-bulk CSVs on LaCie."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from aether.paths import EOD_BULK, require_lacie

# Columns written by FMP eod-bulk
_COL_MAP = {
    "symbol": "symbol",
    "date": "date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "adjClose": "adj_close",
    "adj_close": "adj_close",
    "volume": "volume",
}


def eod_bulk_path(d: date | str) -> Path:
    require_lacie()
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return EOD_BULK / f"{d.isoformat()}.csv"


def list_eod_bulk_dates() -> list[date]:
    require_lacie()
    out: list[date] = []
    for p in EOD_BULK.glob("*.csv"):
        if p.name.startswith("._") or p.stat().st_size < 1000:
            continue
        try:
            out.append(date.fromisoformat(p.stem))
        except ValueError:
            continue
    return sorted(out)


def load_eod_bulk_day(d: date | str, symbols: list[str] | None = None) -> pd.DataFrame:
    """Load one trading day of full-market EOD. Optional symbol filter."""
    path = eod_bulk_path(d)
    if not path.exists():
        raise FileNotFoundError(f"eod-bulk day missing: {path}")

    df = pd.read_csv(path)
    # normalize columns
    rename = {c: _COL_MAP[c] for c in df.columns if c in _COL_MAP}
    df = df.rename(columns=rename)
    need = ["symbol", "date", "open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"eod-bulk {path.name} missing columns {missing}")

    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for c in ("open", "high", "low", "close", "adj_close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")

    if symbols is not None:
        want = set(symbols)
        df = df[df["symbol"].isin(want)]

    return df.reset_index(drop=True)


def load_symbol_history_from_eod_bulk(
    symbol: str,
    start: date | str | None = None,
    end: date | str | None = None,
) -> pd.DataFrame:
    """
    Build a single-symbol daily OHLCV series by scanning eod-bulk day files.

    As-of safe: only includes dates present on disk. Does not invent bars.
    For large universes prefer writing a once-off extract; F1 core is small.
    """
    require_lacie()
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)

    dates = list_eod_bulk_dates()
    if start:
        dates = [d for d in dates if d >= start]
    if end:
        dates = [d for d in dates if d <= end]
    if not dates:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]
        )

    frames: list[pd.DataFrame] = []
    for d in dates:
        try:
            day = load_eod_bulk_day(d, symbols=[symbol])
        except FileNotFoundError:
            continue
        if len(day):
            frames.append(day)

    if not frames:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]
        )

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    out["symbol"] = symbol
    return out.reset_index(drop=True)


def _panel_cache_dir() -> Path:
    from aether.paths import FEATURE_STORE

    d = FEATURE_STORE / "eod_panel_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _panel_cache_key(
    symbols: list[str],
    dates: list[date],
    max_days: int | None,
) -> str:
    import hashlib

    syms = ",".join(sorted({s.upper() for s in symbols}))
    d0 = dates[0].isoformat() if dates else "none"
    d1 = dates[-1].isoformat() if dates else "none"
    payload = f"{syms}|n={len(dates)}|{d0}|{d1}|max={max_days}"
    return hashlib.sha1(payload.encode()).hexdigest()[:20]


def load_core_panel_from_eod_bulk(
    symbols: list[str],
    start: date | str | None = None,
    end: date | str | None = None,
    max_days: int | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Load a multi-symbol daily panel for a date range (one pass over day files).

    More efficient than per-symbol scans for F1 core. Optional parquet cache under
    LaCie feature_store — invalidated when eod_bulk date span/count changes.
    """
    require_lacie()
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)

    dates = list_eod_bulk_dates()
    if start:
        dates = [d for d in dates if d >= start]
    if end:
        dates = [d for d in dates if d <= end]
    if max_days is not None and len(dates) > max_days:
        dates = dates[-max_days:]

    cache_path: Path | None = None
    if use_cache and dates:
        try:
            key = _panel_cache_key(list(symbols), dates, max_days)
            cache_path = _panel_cache_dir() / f"panel_{key}.parquet"
            if cache_path.exists() and cache_path.stat().st_size > 1000:
                cached = pd.read_parquet(cache_path)
                if not cached.empty and "symbol" in cached.columns:
                    return cached.sort_values(["symbol", "date"]).reset_index(drop=True)
        except Exception:
            # cache is acceleration only — never fail the load path
            cache_path = None

    want = set(symbols)
    frames: list[pd.DataFrame] = []
    for d in dates:
        path = eod_bulk_path(d)
        if not path.exists() or path.stat().st_size < 1000:
            continue
        # read only needed columns when possible
        df = pd.read_csv(path)
        rename = {c: _COL_MAP[c] for c in df.columns if c in _COL_MAP}
        df = df.rename(columns=rename)
        if "symbol" not in df.columns:
            continue
        df = df[df["symbol"].isin(want)]
        if df.empty:
            continue
        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        for c in ("open", "high", "low", "close", "adj_close"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
        frames.append(
            df[["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]]
        )

    if not frames:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]
        )
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
    if use_cache and cache_path is not None:
        try:
            out.to_parquet(cache_path, index=False)
        except Exception:
            pass
    return out
