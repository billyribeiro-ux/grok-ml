"""
Intraday feature builder for multi-TF chart bars (1hour / 15min / 5min / 1min).

Local only. Bars must already be on LaCie — no network, no invented prices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_intraday_features(panel: pd.DataFrame, *, min_bars: int = 40) -> pd.DataFrame:
    """
    panel columns: symbol, date, open, high, low, close, volume
    Returns per-bar features + forward labels y_up_1 / y_up_5 (next 1 / 5 bars).
    """
    if panel.empty:
        return panel
    need = {"symbol", "date", "close"}
    if not need.issubset(panel.columns):
        raise ValueError(f"panel needs {need}")

    frames: list[pd.DataFrame] = []
    for sym, g in panel.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        if len(g) < min_bars:
            continue
        c = g["close"].astype(float)
        h = g["high"].astype(float) if "high" in g.columns else c
        l = g["low"].astype(float) if "low" in g.columns else c
        v = g["volume"].astype(float) if "volume" in g.columns else pd.Series(0.0, index=g.index)
        o = g["open"].astype(float) if "open" in g.columns else c

        g["ret_1"] = c.pct_change()
        g["ret_5"] = c.pct_change(5)
        g["ret_20"] = c.pct_change(20)
        g["vol_20"] = g["ret_1"].rolling(20).std()
        g["rvol_20"] = v / v.rolling(20).mean().replace(0, np.nan)
        g["range_pct"] = (h - l) / c.replace(0, np.nan)
        g["gap_pct"] = o / c.shift(1) - 1.0
        g["px_vs_sma20"] = c / c.rolling(20).mean() - 1.0
        g["px_vs_sma50"] = c / c.rolling(50).mean() - 1.0
        # RSI-ish 14
        delta = c.diff()
        up = delta.clip(lower=0).rolling(14).mean()
        down = (-delta.clip(upper=0)).rolling(14).mean()
        rs = up / down.replace(0, np.nan)
        g["rsi_14"] = 100 - (100 / (1 + rs))
        g["mom_20"] = c / c.shift(20) - 1.0

        # labels: next bar / 5-bar direction (honest future; train/test must cut in time)
        fwd1 = c.shift(-1) / c - 1.0
        fwd5 = c.shift(-5) / c - 1.0
        # Keep NaN where the forward return is unknown (the last 1 / 5 bars).
        # `(fwd > 0).astype(float)` would map NaN -> 0.0, inventing a "price
        # went down" label for an outcome that has not happened yet, and the
        # caller's dropna guard would then be a no-op.
        g["y_up_1"] = np.where(fwd1.isna(), np.nan, (fwd1 > 0).astype(float))
        g["y_up_5"] = np.where(fwd5.isna(), np.nan, (fwd5 > 0).astype(float))
        g["fwd_ret_1"] = fwd1
        g["fwd_ret_5"] = fwd5
        frames.append(g)

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out
