"""Pluggable market data — LaCie later, mock now."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Iterable, Sequence

import pandas as pd

from aether.engine.types import Bar


class MarketDataSource(ABC):
    """Interface every data backend must satisfy (offline or LaCie)."""

    @abstractmethod
    def symbols(self) -> list[str]:
        ...

    @abstractmethod
    def calendar(self) -> list[date]:
        """Sorted trading days available."""

    @abstractmethod
    def history(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """
        Daily OHLCV panel for one symbol.
        Columns: date, open, high, low, close, adj_close, volume
        As-of: only bars with date <= end if end set.
        """

    def panel(
        self,
        symbols: Sequence[str] | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        syms = list(symbols) if symbols is not None else self.symbols()
        frames = []
        for s in syms:
            h = self.history(s, start=start, end=end)
            if h.empty:
                continue
            h = h.copy()
            h["symbol"] = s
            frames.append(h)
        if not frames:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adj_close",
                    "volume",
                ]
            )
        out = pd.concat(frames, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"]).dt.normalize()
        return out.sort_values(["symbol", "date"]).reset_index(drop=True)


class PanelFrameSource(MarketDataSource):
    """In-memory panel wrapper — reuse one eod_bulk load across research grids."""

    def __init__(self, panel: pd.DataFrame, *, name: str = "PanelFrameSource") -> None:
        if panel is None or panel.empty:
            raise ValueError("PanelFrameSource requires non-empty panel")
        need = {"symbol", "date", "open", "high", "low", "close", "volume"}
        missing = need - set(panel.columns)
        if missing:
            raise ValueError(f"panel missing columns {sorted(missing)}")
        self._name = name
        self._panel = panel.copy()
        self._panel["date"] = pd.to_datetime(self._panel["date"]).dt.normalize()
        if "adj_close" not in self._panel.columns:
            self._panel["adj_close"] = self._panel["close"]
        self._symbols = sorted(self._panel["symbol"].astype(str).unique().tolist())
        self._calendar = sorted(
            {pd.Timestamp(d).date() for d in self._panel["date"].unique()}
        )

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
        df = self._panel[self._panel["symbol"] == symbol]
        if start is not None:
            df = df[df["date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["date"] <= pd.Timestamp(end)]
        return df[
            ["date", "open", "high", "low", "close", "adj_close", "volume"]
        ].reset_index(drop=True)

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

    def bars_on(self, symbol: str, d: date) -> Bar | None:
        h = self.history(symbol, start=d, end=d)
        if h.empty:
            return None
        r = h.iloc[-1]
        ts = pd.Timestamp(r["date"]).to_pydatetime()
        return Bar(
            symbol=symbol,
            ts=ts,
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=int(r["volume"]),
            adj_close=float(r.get("adj_close", r["close"])),
        )
