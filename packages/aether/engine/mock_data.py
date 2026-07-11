"""Synthetic multi-asset daily data for offline engine development."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from aether.engine.data_source import MarketDataSource

# Deterministic seeds per symbol for reproducibility
_DEFAULT_UNIVERSE = (
    "SPY",
    "QQQ",
    "IWM",
    "AAPL",
    "NVDA",
    "TSLA",
    "SQQQ",
    "TZA",
    "SH",
    "UVXY",
)


class MockDailySource(MarketDataSource):
    """
    Generates correlated GBM-like paths with regime shifts.
    No network. No LaCie. Honest synthetic labels for unit/integration tests.
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        start: date = date(2019, 1, 2),
        end: date = date(2026, 7, 10),
        seed: int = 42,
    ) -> None:
        self._symbols = list(symbols or _DEFAULT_UNIVERSE)
        self._start = start
        self._end = end
        self._seed = seed
        self._cache: dict[str, pd.DataFrame] = {}
        self._calendar = _bdays(start, end)
        self._build_all()

    def symbols(self) -> list[str]:
        return list(self._symbols)

    def calendar(self) -> list[date]:
        return list(self._calendar)

    def history(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        if symbol not in self._cache:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "adj_close", "volume"]
            )
        df = self._cache[symbol]
        if start is not None:
            df = df[df["date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["date"] <= pd.Timestamp(end)]
        return df.reset_index(drop=True)

    def _build_all(self) -> None:
        rng = np.random.default_rng(self._seed)
        n = len(self._calendar)
        # market factor
        mkt = rng.normal(0.00025, 0.011, size=n)
        # inject a bear regime mid-sample
        mid = n // 2
        mkt[mid : mid + 40] = rng.normal(-0.004, 0.025, size=40)
        # vol spike near end
        mkt[-30:] = rng.normal(0.0, 0.03, size=30)

        betas = {
            "SPY": 1.0,
            "QQQ": 1.15,
            "IWM": 1.1,
            "AAPL": 1.05,
            "NVDA": 1.4,
            "TSLA": 1.5,
            "SQQQ": -2.8,
            "TZA": -2.7,
            "SH": -0.95,
            "UVXY": -1.2,  # rough: spikes when market dumps
        }
        for i, sym in enumerate(self._symbols):
            b = betas.get(sym, 1.0)
            idio = rng.normal(0.0, 0.008 + 0.002 * (i % 5), size=n)
            if sym == "UVXY":
                rets = -1.5 * mkt + np.abs(mkt) * 0.5 + idio
            else:
                rets = b * mkt + idio
            px0 = 100.0 + 10.0 * i
            close = px0 * np.cumprod(1.0 + rets)
            open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.001, n))
            high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.01, n))
            low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.01, n))
            vol = rng.integers(1_000_000, 20_000_000, size=n)
            self._cache[sym] = pd.DataFrame(
                {
                    "date": pd.to_datetime(self._calendar),
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "adj_close": close,
                    "volume": vol,
                }
            )


def _bdays(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out
