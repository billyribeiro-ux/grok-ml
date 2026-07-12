"""Earnings specialist unit tests — synthetic event table, no LaCie."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aether.engine.earnings_specialist import prepare_frame


def test_prepare_post1d():
    ev = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "earnings_date": pd.to_datetime(["2024-01-25", "2024-01-24"]),
            "time": ["amc", "bmo"],
            "pre_ret_1d": [0.01, 0.0],
            "pre_ret_3d": [0.02, 0.01],
            "pre_ret_5d": [0.03, -0.01],
            "pre_ret_8d": [0.04, 0.02],
            "vol_spike_8": [1.2, 0.9],
            "post_ret_1d": [0.02, -0.03],
            "epsEstimated": [1.5, None],
            "last_eps_surprise_pct": [0.05, -0.01],
        }
    )
    df, label, feats = prepare_frame(ev, "post1d")
    assert label == "y_up_post_1d"
    assert len(df) == 2
    assert df.loc[0, label] == 1.0
    assert df.loc[1, label] == 0.0
    assert "pre_ret_8d" in feats


def test_prepare_pre8_buy_rumor():
    ev = pd.DataFrame(
        {
            "symbol": ["AAPL", "X"],
            "earnings_date": pd.to_datetime(["2024-01-25", "2024-02-01"]),
            "time": ["amc", "bmo"],
            "pre_ret_8d": [0.05, np.nan],
            "mom_20_at_t8": [0.1, 0.0],
            "mom_5_at_t8": [0.02, 0.0],
            "ret_1_at_t8": [0.01, 0.0],
            "trail_vol_20": [0.02, 0.02],
            "epsEstimated": [1.0, 1.0],
            "last_eps_surprise_pct": [0.0, 0.0],
        }
    )
    df, label, feats = prepare_frame(ev, "pre8")
    assert label == "y_up_pre8"
    assert len(df) == 1  # nan pre_ret_8d dropped
    assert df.iloc[0][label] == 1.0
    assert "mom_20_at_t8" in feats
    assert "pre_ret_8d" not in feats  # no label leak into features
