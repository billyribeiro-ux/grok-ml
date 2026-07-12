"""Intraday feature builder tests — synthetic bars."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aether.features.intraday import build_intraday_features


def test_build_intraday_features_labels():
    n = 80
    rng = np.random.default_rng(0)
    px = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * n,
            "date": pd.date_range("2024-01-02 09:30", periods=n, freq="15min"),
            "open": px,
            "high": px * 1.01,
            "low": px * 0.99,
            "close": px,
            "volume": rng.integers(1e5, 1e6, n),
        }
    )
    out = build_intraday_features(df, min_bars=40)
    assert "ret_1" in out.columns
    assert "y_up_1" in out.columns
    assert "y_up_5" in out.columns
    assert out["y_up_1"].dropna().isin([0.0, 1.0]).all()
