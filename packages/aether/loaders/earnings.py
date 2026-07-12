"""
Earnings release events from LaCie FMP archive (honest, no network).

Primary source: earnings_archive panels built from daily
`earnings-calendar` with includeReportTimes (bmo/amc).

Window pin: 2018-01-01 → 2026-07-10 (filter enforced on load if dates present).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from aether.paths import FMP_RAW

EARN_ROOT = FMP_RAW / "earnings_archive"
PANEL_DIR = EARN_ROOT / "panels"

WINDOW_START = "2018-01-01"
WINDOW_END = "2026-07-10"

PANEL_FILES = {
    "all": PANEL_DIR / "all_2018_20260710.parquet",
    "sp500": PANEL_DIR / "sp500_2018_20260710.parquet",
    "iwm": PANEL_DIR / "iwm_2018_20260710.parquet",
    "nasdaq": PANEL_DIR / "nasdaq_2018_20260710.parquet",
}


def earnings_panel(
    universe: str = "sp500",
    *,
    start: str | None = WINDOW_START,
    end: str | None = WINDOW_END,
) -> pd.DataFrame:
    """
    Load earnings events panel for a universe.

    Columns (when present):
      symbol, date, epsActual, epsEstimated, revenueActual, revenueEstimated,
      time (bmo/amc/…), periodEnding, confirmed, lastUpdated,
      eps_surprise, eps_surprise_pct, revenue_surprise, revenue_surprise_pct
    """
    key = universe.strip().lower()
    path = PANEL_FILES.get(key)
    if path is None:
        raise ValueError(f"unknown universe={universe!r}; expected one of {list(PANEL_FILES)}")
    if not path.exists():
        raise FileNotFoundError(
            f"earnings panel missing: {path} — run scripts/fmp_archive_earnings_releases.py"
        )
    df = pd.read_parquet(path)
    if "date" not in df.columns:
        raise ValueError(f"earnings panel missing date column: {path}")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def earnings_for_symbol(
    symbol: str,
    universe: str = "sp500",
    *,
    start: str | None = WINDOW_START,
    end: str | None = WINDOW_END,
) -> pd.DataFrame:
    """Single-symbol slice of the earnings panel."""
    df = earnings_panel(universe, start=start, end=end)
    sym = symbol.strip().upper()
    return df[df["symbol"].astype(str).str.upper() == sym].reset_index(drop=True)


def days_to_next_earnings(
    panel: pd.DataFrame,
    as_of: pd.Timestamp | str,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """
    For each symbol, distance in calendar days to the next earnings date on/after as_of.

    Returns columns: symbol, next_earnings_date, days_to_earnings, time
    Honest: symbols with no future event are omitted (not invented).
    """
    as_of_ts = pd.Timestamp(as_of).normalize()
    df = panel.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if symbols is not None:
        want = {s.upper() for s in symbols}
        df = df[df["symbol"].astype(str).str.upper().isin(want)]
    future = df[df["date"] >= as_of_ts]
    if future.empty:
        return pd.DataFrame(
            columns=["symbol", "next_earnings_date", "days_to_earnings", "time"]
        )
    idx = future.groupby(future["symbol"].astype(str).str.upper())["date"].idxmin()
    nxt = future.loc[idx, ["symbol", "date", "time"]].copy()
    nxt = nxt.rename(columns={"date": "next_earnings_date"})
    nxt["days_to_earnings"] = (nxt["next_earnings_date"] - as_of_ts).dt.days
    return nxt.reset_index(drop=True)


# Feature columns attached to daily bars for pre/post-earnings ML
EARN_FEATURE_COLS = (
    "earn_days_to_next",
    "earn_days_since_last",
    "earn_in_pre_window",
    "earn_in_post_window",
    "earn_is_day",
    "earn_next_is_bmo",
    "earn_next_is_amc",
    "earn_last_eps_surprise_pct",
    "earn_last_rev_surprise_pct",
)


def attach_earnings_features(
    daily: pd.DataFrame,
    events: pd.DataFrame | None = None,
    *,
    universe: str = "sp500",
    pre_window: int = 5,
    post_window: int = 5,
) -> pd.DataFrame:
    """
    Join earnings proximity + last surprise features onto a daily OHLCV/feature panel.

    Requires columns: symbol, date.
    Uses only past events for surprise (no future-label leak on surprise).
    days_to_next uses the archived calendar (standard for event-driven research;
    schedule revisions are an honest residual risk).

    Missing calendar → zeros / neutral flags (same pattern as fund_* ETF fill).
    """
    if daily.empty:
        return daily
    if "symbol" not in daily.columns or "date" not in daily.columns:
        raise ValueError("daily panel needs symbol + date")

    out = daily.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["symbol"] = out["symbol"].astype(str)

    if events is None:
        try:
            events = earnings_panel(universe)
        except (FileNotFoundError, ValueError):
            for c in EARN_FEATURE_COLS:
                if c not in out.columns:
                    out[c] = 0.0
            return out

    if events.empty:
        for c in EARN_FEATURE_COLS:
            out[c] = 0.0
        return out

    ev = events.copy()
    ev["date"] = pd.to_datetime(ev["date"]).dt.normalize()
    ev["symbol"] = ev["symbol"].astype(str)
    ev = ev.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Per-symbol event arrays for vectorized searchsorted
    pieces: list[pd.DataFrame] = []
    for sym, g in out.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        e = ev[ev["symbol"] == sym].sort_values("date")
        if e.empty:
            g["earn_days_to_next"] = np.nan
            g["earn_days_since_last"] = np.nan
            g["earn_next_is_bmo"] = 0.0
            g["earn_next_is_amc"] = 0.0
            g["earn_last_eps_surprise_pct"] = np.nan
            g["earn_last_rev_surprise_pct"] = np.nan
            pieces.append(g)
            continue

        edates = e["date"].to_numpy(dtype="datetime64[ns]")
        times = e["time"].astype(str).str.lower().fillna("").to_numpy()
        eps_s = (
            e["eps_surprise_pct"].to_numpy(dtype=float)
            if "eps_surprise_pct" in e.columns
            else np.full(len(e), np.nan)
        )
        rev_s = (
            e["revenue_surprise_pct"].to_numpy(dtype=float)
            if "revenue_surprise_pct" in e.columns
            else np.full(len(e), np.nan)
        )

        dvals = g["date"].to_numpy(dtype="datetime64[ns]")
        # next: first event index with date >= bar date
        nxt_i = np.searchsorted(edates, dvals, side="left")
        # last: last event index with date < bar date (strict past for surprise)
        last_i = np.searchsorted(edates, dvals, side="left") - 1

        days_to = np.full(len(g), np.nan)
        days_since = np.full(len(g), np.nan)
        next_bmo = np.zeros(len(g))
        next_amc = np.zeros(len(g))
        last_eps = np.full(len(g), np.nan)
        last_rev = np.full(len(g), np.nan)

        for i in range(len(g)):
            ni = int(nxt_i[i])
            li = int(last_i[i])
            if 0 <= ni < len(edates):
                days_to[i] = (edates[ni] - dvals[i]) / np.timedelta64(1, "D")
                t = times[ni]
                next_bmo[i] = 1.0 if t == "bmo" else 0.0
                next_amc[i] = 1.0 if t == "amc" else 0.0
            if 0 <= li < len(edates):
                days_since[i] = (dvals[i] - edates[li]) / np.timedelta64(1, "D")
                last_eps[i] = eps_s[li]
                last_rev[i] = rev_s[li]
            # same-day event: days_to=0 and days_since=0
            if 0 <= ni < len(edates) and edates[ni] == dvals[i]:
                days_since[i] = 0.0

        g["earn_days_to_next"] = days_to
        g["earn_days_since_last"] = days_since
        g["earn_next_is_bmo"] = next_bmo
        g["earn_next_is_amc"] = next_amc
        g["earn_last_eps_surprise_pct"] = last_eps
        g["earn_last_rev_surprise_pct"] = last_rev
        pieces.append(g)

    out = pd.concat(pieces, ignore_index=True)
    out["earn_is_day"] = (out["earn_days_to_next"] == 0).astype(float)
    out["earn_in_pre_window"] = (
        (out["earn_days_to_next"] >= 0) & (out["earn_days_to_next"] <= pre_window)
    ).astype(float)
    out["earn_in_post_window"] = (
        (out["earn_days_since_last"] > 0) & (out["earn_days_since_last"] <= post_window)
    ).astype(float)

    # Neutral fill for model rows without calendar (ETFs, missing names)
    for c in EARN_FEATURE_COLS:
        if c not in out.columns:
            out[c] = 0.0
        else:
            out[c] = out[c].replace([np.inf, -np.inf], np.nan)
            if c in (
                "earn_days_to_next",
                "earn_days_since_last",
                "earn_last_eps_surprise_pct",
                "earn_last_rev_surprise_pct",
            ):
                # keep NaN for distance when unknown; scorer may drop or fill
                pass
            else:
                out[c] = out[c].fillna(0.0)

    return out
