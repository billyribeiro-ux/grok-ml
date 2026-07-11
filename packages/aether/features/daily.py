"""
Daily feature builders — as-of safe (only past information on each row).

F1 spine: simple, auditable features for SPY/QQQ/IWM core.
No look-ahead: all rolling windows use past bars only (pandas default).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _per_symbol_features(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date").copy()
    px = g["adj_close"].astype(float)

    g["ret_1d"] = px.pct_change(1)
    g["ret_5d"] = px.pct_change(5)
    g["ret_20d"] = px.pct_change(20)

    g["sma_5"] = px.rolling(5, min_periods=5).mean()
    g["sma_20"] = px.rolling(20, min_periods=20).mean()
    g["sma_50"] = px.rolling(50, min_periods=50).mean()
    g["sma_200"] = px.rolling(200, min_periods=200).mean()

    g["px_vs_sma20"] = px / g["sma_20"] - 1.0
    g["px_vs_sma50"] = px / g["sma_50"] - 1.0
    g["sma20_vs_sma50"] = g["sma_20"] / g["sma_50"] - 1.0

    # True range / ATR-ish
    prev_close = px.shift(1)
    tr = pd.concat(
        [
            (g["high"] - g["low"]).abs(),
            (g["high"] - prev_close).abs(),
            (g["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    g["atr_14"] = tr.rolling(14, min_periods=14).mean()
    g["atr_pct"] = g["atr_14"] / px

    # Range position in prior 20d (no future)
    roll_low = g["low"].rolling(20, min_periods=20).min()
    roll_high = g["high"].rolling(20, min_periods=20).max()
    span = (roll_high - roll_low).replace(0, np.nan)
    g["range_pos_20d"] = (px - roll_low) / span

    vol = g["volume"].astype(float)
    g["vol_sma_20"] = vol.rolling(20, min_periods=20).mean()
    g["vol_z_20"] = (vol - g["vol_sma_20"]) / g["vol_sma_20"].replace(0, np.nan)

    # Simple RSI 14 (Wilder-lite via ewm)
    delta = px.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    g["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

    # Realized vol
    g["rvol_20"] = g["ret_1d"].rolling(20, min_periods=20).std() * np.sqrt(252)

    # Gap vs prior close
    g["gap_pct"] = g["open"].astype(float) / prev_close - 1.0

    # Trend flags (for mode routing later)
    g["above_sma200"] = (px > g["sma_200"]).astype("float64")
    g["trend_stack"] = (
        (g["sma_5"] > g["sma_20"]).astype("float64")
        + (g["sma_20"] > g["sma_50"]).astype("float64")
        + (g["sma_50"] > g["sma_200"]).astype("float64")
    )

    return g


def build_daily_features(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Input panel columns: symbol, date, open, high, low, close, adj_close, volume
    Output: same + feature columns. NaNs at warm-up — honest, not filled with lies.
    """
    need = {"symbol", "date", "open", "high", "low", "close", "volume"}
    missing = need - set(panel.columns)
    if missing:
        raise ValueError(f"panel missing columns: {missing}")

    df = panel.copy()
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()

    parts = [_per_symbol_features(g) for _, g in df.groupby("symbol", sort=False)]
    if not parts:
        return df.iloc[0:0].copy()

    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
    # as-of marker: feature row only uses data on or before `date`
    out["as_of"] = out["date"]
    out["feature_set"] = "daily_f1_v1"
    return out
