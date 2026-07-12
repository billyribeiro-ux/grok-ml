"""Earnings calendar features — unit tests (no LaCie required)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aether.loaders.earnings import (
    EARN_FEATURE_COLS,
    attach_earnings_features,
    days_to_next_earnings,
)
from aether.engine.scorer import LogisticScorer


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "date": "2024-01-25",
                "time": "amc",
                "eps_surprise_pct": 0.05,
                "revenue_surprise_pct": 0.02,
            },
            {
                "symbol": "AAPL",
                "date": "2024-04-25",
                "time": "amc",
                "eps_surprise_pct": -0.01,
                "revenue_surprise_pct": 0.0,
            },
            {
                "symbol": "MSFT",
                "date": "2024-01-24",
                "time": "bmo",
                "eps_surprise_pct": 0.03,
                "revenue_surprise_pct": 0.01,
            },
        ]
    )


def test_days_to_next_earnings():
    nxt = days_to_next_earnings(_events(), "2024-01-20", symbols=["AAPL"])
    assert len(nxt) == 1
    assert nxt.iloc[0]["days_to_earnings"] == 5
    assert nxt.iloc[0]["time"] == "amc"


def test_attach_earnings_pre_post_windows():
    daily = pd.DataFrame(
        {
            "symbol": ["AAPL"] * 5,
            "date": pd.to_datetime(
                ["2024-01-22", "2024-01-23", "2024-01-24", "2024-01-25", "2024-01-26"]
            ),
            "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "ret_1d": [0.01] * 5,
        }
    )
    out = attach_earnings_features(daily, _events(), pre_window=5, post_window=5)
    for c in EARN_FEATURE_COLS:
        assert c in out.columns
    day = out[out["date"] == "2024-01-25"].iloc[0]
    assert day["earn_is_day"] == 1.0
    assert day["earn_days_to_next"] == 0.0
    assert day["earn_next_is_amc"] == 1.0
    assert day["earn_in_pre_window"] == 1.0
    # day after
    post = out[out["date"] == "2024-01-26"].iloc[0]
    assert post["earn_days_since_last"] == 1.0
    assert post["earn_in_post_window"] == 1.0
    assert post["earn_last_eps_surprise_pct"] == 0.05


def test_scorer_accepts_earn_features():
    n = 80
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "ret_1d": rng.normal(0, 0.01, n),
            "ret_5d": rng.normal(0, 0.02, n),
            "earn_days_to_next": rng.integers(0, 40, n).astype(float),
            "earn_in_pre_window": rng.integers(0, 2, n).astype(float),
            "earn_last_eps_surprise_pct": rng.normal(0, 0.05, n),
            "y_up_5d": rng.integers(0, 2, n).astype(float),
        }
    )
    # pad other required-ish cols via only subset present — scorer uses intersection
    sc = LogisticScorer(
        feature_cols=(
            "ret_1d",
            "ret_5d",
            "earn_days_to_next",
            "earn_in_pre_window",
            "earn_last_eps_surprise_pct",
        ),
        epochs=20,
    )
    sc.fit(df)
    p = sc.predict_proba(df)
    assert len(p) == n
    assert np.all((p >= 0) & (p <= 1))
