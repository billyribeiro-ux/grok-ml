"""
Wide cross-sectional panel from the frozen eod-bulk archive.

Motivation (measured, not assumed): the 13-symbol universe the engine trades has
an effective breadth of 1.89 independent bets — 13 names with mean pairwise
correlation 0.233 and 72% of variance in a single market factor. Sharpe
precision scales with independent bets, so no amount of trading that universe
produces a measurable edge.

A single eod-bulk day holds ~4,086 liquid US names. Ranking that cross-section
is the only lever that raises breadth by orders of magnitude, and the data is
already on disk.

Liquidity screen is applied POINT-IN-TIME (per date, from that date's own bar),
never from a current-membership list — the archive's own presence/absence is the
survivorship-free universe definition.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from aether.loaders.eod_bulk import eod_bulk_path, list_eod_bulk_dates
from aether.paths import FEATURE_STORE, require_lacie

# Columns FMP writes, normalized to the engine's contract.
_COLS = {
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

OUT_COLS = ["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]


@dataclass(frozen=True, slots=True)
class LiquidityScreen:
    """Point-in-time tradability filter. Applied per date, never forward-filled."""

    min_dollar_volume: float = 5_000_000.0
    min_close: float = 5.0
    max_close: float = 100_000.0
    exclude_suffixed: bool = True  # '.' marks foreign listings in this archive
    exclude_crypto: bool = True  # eod-bulk mixes FX/crypto pairs in with equities
    max_open_close_ratio: float = 2.0  # bar-level sanity; see note below

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df
        sym = out["symbol"].astype(str)
        if self.exclude_suffixed:
            out = out[~sym.str.contains(r"\.", regex=True)]
        if self.exclude_crypto:
            # Measured: ARCXUSD / AUSCMUSD / AUTOUSD etc. carry no exchange dot
            # and pass a naive equity screen. They produced open-to-open returns
            # up to +941,400% and below -100%.
            s = out["symbol"].astype(str)
            out = out[~(s.str.endswith("USD") | s.str.endswith("USDT"))]

        dollar_vol = out["close"] * out["volume"]
        out = out[
            (dollar_vol >= self.min_dollar_volume)
            & (out["close"] >= self.min_close)
            & (out["close"] <= self.max_close)
        ]

        # Bar-level coherence. qlib's check_data_health flags >50% single-bar
        # price steps; the archive contains bars like ATXG 2022-08-31
        # (open 4050 -> close 98481) that are unadjusted-split or vendor errors.
        # A bar failing OHLC ordering is not a price, it is a defect.
        o, h, l, c = out["open"], out["high"], out["low"], out["close"]
        coherent = (
            (o > 0) & (h > 0) & (l > 0) & (c > 0)
            & (l <= o) & (l <= c) & (o <= h) & (c <= h)
            & (o / c <= self.max_open_close_ratio)
            & (c / o <= self.max_open_close_ratio)
        )
        return out[coherent]


def _cache_key(start: date, end: date, screen: LiquidityScreen, n_days: int) -> str:
    payload = (
        f"{start}|{end}|{n_days}|{screen.min_dollar_volume}|{screen.min_close}"
        f"|{screen.max_close}|{screen.exclude_suffixed}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _read_day(path: Path) -> pd.DataFrame | None:
    """One eod-bulk day, normalized. None if unreadable or implausibly small."""
    if not path.exists() or path.stat().st_size < 1000:
        return None
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception:
        return None
    df = df.rename(columns={c: _COLS[c] for c in df.columns if c in _COLS})
    if "symbol" not in df.columns or "close" not in df.columns:
        return None
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    for c in ("open", "high", "low", "close", "adj_close", "volume"):
        if c not in df.columns:
            return None
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close", "volume"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df[OUT_COLS]


def build_cross_section(
    start: date | str = date(2015, 1, 1),
    end: date | str = date(2026, 7, 10),
    screen: LiquidityScreen | None = None,
    use_cache: bool = True,
    progress_every: int = 250,
) -> pd.DataFrame:
    """
    Long panel of every liquid US name on every archived trading day.

    Survivorship-free by construction: a symbol appears on date d if and only if
    the archive's file for d contains it. Delisted names simply stop appearing —
    they are not retroactively removed from earlier dates.
    """
    require_lacie()
    screen = screen or LiquidityScreen()
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)

    dates = [d for d in list_eod_bulk_dates() if start <= d <= end]
    if not dates:
        raise RuntimeError(f"no eod-bulk days in {start}..{end}")

    cache_dir = FEATURE_STORE / "cross_section"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"panel_{_cache_key(start, end, screen, len(dates))}.parquet"
    if use_cache and cache.exists() and cache.stat().st_size > 10_000:
        return pd.read_parquet(cache)

    frames: list[pd.DataFrame] = []
    skipped = 0
    for i, d in enumerate(dates, 1):
        day = _read_day(eod_bulk_path(d))
        if day is None:
            skipped += 1
            continue
        frames.append(screen.apply(day))
        if progress_every and i % progress_every == 0:
            print(f"  {i}/{len(dates)} days, {sum(len(f) for f in frames):,} rows", flush=True)

    if skipped:
        # Never silent: a missing day is a hole in the calendar, not an empty day.
        print(f"  WARNING: {skipped} day files unreadable/too small and skipped", flush=True)
    if not frames:
        raise RuntimeError("no readable eod-bulk days")

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    if use_cache:
        tmp = cache.with_suffix(".parquet.partial")
        panel.to_parquet(tmp, index=False)
        tmp.replace(cache)  # atomic: a crash mid-write cannot leave a valid-looking file
    return panel


def universe_on(panel: pd.DataFrame, d: date | str) -> list[str]:
    """Point-in-time tradable universe for one date."""
    ts = pd.Timestamp(d)
    return sorted(panel.loc[panel["date"] == ts, "symbol"].unique().tolist())


def breadth_stats(panel: pd.DataFrame) -> dict:
    """Effective independent bets — the quantity that actually bounds Sharpe precision."""
    px = panel.pivot_table(index="date", columns="symbol", values="adj_close")
    rets = px.pct_change()
    # Restrict to names with a mostly-complete history so the correlation matrix
    # is not dominated by pairwise-incomplete overlaps.
    dense = rets.loc[:, rets.notna().mean() > 0.9]
    corr = dense.corr().to_numpy()
    import numpy as np

    corr = corr[~np.isnan(corr).all(axis=1)][:, ~np.isnan(corr).all(axis=0)]
    corr = np.nan_to_num(corr, nan=0.0)
    ev = np.linalg.eigvalsh(corr)
    ev = ev[ev > 0]
    k = corr.shape[0]
    return {
        "n_symbols_total": int(panel["symbol"].nunique()),
        "n_symbols_dense": int(k),
        "n_dates": int(panel["date"].nunique()),
        "rows": int(len(panel)),
        "mean_pairwise_corr": float((corr.sum() - k) / (k * (k - 1))) if k > 1 else float("nan"),
        "effective_bets": float((ev.sum() ** 2) / (ev**2).sum()),
        "top_factor_share": float(ev[-1] / ev.sum()),
    }
