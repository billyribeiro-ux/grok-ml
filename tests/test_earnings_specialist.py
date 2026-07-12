"""Earnings specialist unit tests — synthetic event table, no LaCie."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aether.engine.earnings_specialist import (
    LABEL_COL,
    prepare_specialist_frame,
)


def test_prepare_specialist_frame_label_and_flags():
    ev = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "earnings_date": pd.to_datetime(["2024-01-25", "2024-04-25", "2024-01-24"]),
            "time": ["amc", "amc", "bmo"],
            "pre_ret_1d": [0.01, -0.02, 0.0],
            "pre_ret_3d": [0.02, -0.01, 0.01],
            "pre_ret_5d": [0.03, 0.0, -0.01],
            "post_ret_1d": [0.02, -0.03, 0.01],
            "epsEstimated": [1.5, 1.6, None],
        }
    )
    df = prepare_specialist_frame(ev)
    assert len(df) == 3
    assert LABEL_COL in df.columns
    assert df.loc[0, LABEL_COL] == 1.0
    assert df.loc[1, LABEL_COL] == 0.0
    assert df.loc[0, "is_amc"] == 1.0
    assert df.loc[2, "is_bmo"] == 1.0
    assert df.loc[0, "has_eps_estimate"] == 1.0
    assert df.loc[2, "has_eps_estimate"] == 0.0


def test_prepare_drops_missing_post():
    ev = pd.DataFrame(
        {
            "symbol": ["X"],
            "earnings_date": pd.to_datetime(["2024-01-01"]),
            "time": ["bmo"],
            "pre_ret_1d": [0.0],
            "post_ret_1d": [np.nan],
        }
    )
    df = prepare_specialist_frame(ev)
    assert len(df) == 0
