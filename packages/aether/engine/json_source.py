"""MarketDataSource over per-symbol JSON OHLCV trees (liquid/bonds/etn)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

import pandas as pd

from aether.engine.data_source import MarketDataSource
from aether.loaders.symbol_json import load_symbol_json_dir


class JsonOhlcvDirSource(MarketDataSource):
    def __init__(
        self,
        directory: Path | str,
        symbols: Sequence[str] | None = None,
        *,
        max_symbols: int | None = None,
    ) -> None:
        self._panel = load_symbol_json_dir(
            Path(directory), symbols=symbols, max_symbols=max_symbols
        )
        if self._panel.empty:
            raise RuntimeError(f"no OHLCV json rows in {directory}")
        self._symbols = sorted(self._panel["symbol"].unique().tolist())

    def symbols(self) -> list[str]:
        return list(self._symbols)

    def calendar(self) -> list[date]:
        return sorted(pd.to_datetime(self._panel["date"]).dt.date.unique().tolist())

    def history(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        df = self.panel(symbols=[symbol], start=start, end=end)
        return df[["date", "open", "high", "low", "close", "adj_close", "volume"]].reset_index(
            drop=True
        )

    def panel(
        self,
        symbols: Sequence[str] | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        df = self._panel
        if symbols is not None:
            df = df[df["symbol"].isin(list(symbols))]
        if start is not None:
            df = df[df["date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["date"] <= pd.Timestamp(end)]
        return df.reset_index(drop=True)
