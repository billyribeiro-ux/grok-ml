"""LaCie-backed data source — optional; engine works without it via MockDailySource."""

from __future__ import annotations

from datetime import date
from typing import Sequence

import pandas as pd

from aether.engine.data_source import MarketDataSource
from aether.loaders.eod_bulk import load_core_panel_from_eod_bulk, list_eod_bulk_dates
from aether.paths import F1_CORE_SYMBOLS, LaCieNotMountedError, require_lacie


class LacieEodBulkSource(MarketDataSource):
    """
    Reads full-market daily history from eod-bulk for a fixed symbol list.
    Requires LaCie. Prefer MockDailySource for pure engine development.
    """

    def __init__(self, symbols: Sequence[str] | None = None) -> None:
        require_lacie()
        self._symbols = list(symbols or F1_CORE_SYMBOLS)
        self._panel: pd.DataFrame | None = None
        self._calendar: list[date] | None = None

    def symbols(self) -> list[str]:
        return list(self._symbols)

    def calendar(self) -> list[date]:
        if self._calendar is None:
            self._calendar = list_eod_bulk_dates()
        return list(self._calendar)

    def _ensure_panel(self, start: date | None, end: date | None) -> pd.DataFrame:
        # Load with start/end so parquet cache keys on the research window
        # (stable while early eod_bulk history is still filling). Full history
        # still available when start/end are None.
        key = (start, end)
        if self._panel is None or getattr(self, "_panel_key", None) != key:
            self._panel = load_core_panel_from_eod_bulk(
                self._symbols, start=start, end=end
            )
            self._panel_key = key
        return self._panel

    def history(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        df = self._ensure_panel(start, end)
        g = df[df["symbol"] == symbol][
            ["date", "open", "high", "low", "close", "adj_close", "volume"]
        ]
        return g.reset_index(drop=True)

    def panel(
        self,
        symbols: Sequence[str] | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        df = self._ensure_panel(start, end)
        if symbols is not None:
            df = df[df["symbol"].isin(list(symbols))]
        return df.reset_index(drop=True)
