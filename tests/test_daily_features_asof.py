"""Unit tests that do not require LaCie."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aether.features.daily import build_daily_features


def _synth(symbol: str = "SPY", n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2020-01-01", periods=n)
    px = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, size=n))
    return pd.DataFrame(
        {
            "symbol": symbol,
            "date": dates,
            "open": px * 0.999,
            "high": px * 1.01,
            "low": px * 0.99,
            "close": px,
            "adj_close": px,
            "volume": rng.integers(1_000_000, 5_000_000, size=n),
        }
    )


def test_build_daily_features_shapes():
    panel = pd.concat([_synth("SPY"), _synth("QQQ")], ignore_index=True)
    feats = build_daily_features(panel)
    assert len(feats) == len(panel)
    assert "ret_1d" in feats.columns
    assert "rsi_14" in feats.columns
    assert "feature_set" in feats.columns
    assert feats["feature_set"].iloc[0] == "daily_f1_v1"


def test_no_lookahead_sma():
    """SMA_20 on day t must equal mean of closes[t-19:t+1] inclusive past only."""
    df = _synth("SPY", n=40)
    feats = build_daily_features(df)
    # row index 25 (0-based) has enough history
    row = feats.iloc[25]
    window = df["close"].iloc[25 - 19 : 26].astype(float)
    expected = window.mean()
    assert abs(float(row["sma_20"]) - float(expected)) < 1e-9
