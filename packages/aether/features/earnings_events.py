"""
Earnings / pre-earnings event study labels from daily prices + earnings calendar.

Local only. No network. Does not invent events or prices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from aether.loaders.earnings import earnings_panel


def build_earnings_event_table(
    prices: pd.DataFrame,
    events: pd.DataFrame | None = None,
    *,
    universe: str = "sp500",
    pre_days: tuple[int, ...] = (1, 3, 5),
    post_days: tuple[int, ...] = (1, 3, 5),
) -> pd.DataFrame:
    """
    One row per (symbol, earnings_date) with pre/post close-to-close returns.

    prices: daily bars with symbol, date, close (or adj).
    Returns columns including:
      symbol, earnings_date, time, eps_surprise_pct, revenue_surprise_pct,
      pre_ret_{n}d, post_ret_{n}d, gap_ret (open vs prior close if open present)
    """
    if prices.empty:
        return pd.DataFrame()
    need = {"symbol", "date", "close"}
    if not need.issubset(prices.columns):
        raise ValueError(f"prices need {need}")

    px = prices.copy()
    px["date"] = pd.to_datetime(px["date"]).dt.normalize()
    px["symbol"] = px["symbol"].astype(str)
    px = px.sort_values(["symbol", "date"])

    if events is None:
        events = earnings_panel(universe)
    ev = events.copy()
    ev["date"] = pd.to_datetime(ev["date"]).dt.normalize()
    ev["symbol"] = ev["symbol"].astype(str)

    rows: list[dict] = []
    for sym, e_sym in ev.groupby("symbol"):
        p = px[px["symbol"] == sym].set_index("date").sort_index()
        if p.empty:
            continue
        closes = p["close"].astype(float)
        opens = p["open"].astype(float) if "open" in p.columns else None
        for _, er in e_sym.iterrows():
            ed = pd.Timestamp(er["date"]).normalize()
            rec: dict = {
                "symbol": sym,
                "earnings_date": ed,
                "time": er.get("time"),
                "epsActual": er.get("epsActual"),
                "epsEstimated": er.get("epsEstimated"),
                "eps_surprise_pct": er.get("eps_surprise_pct"),
                "revenue_surprise_pct": er.get("revenue_surprise_pct"),
                "confirmed": er.get("confirmed"),
            }
            # pre: return from T-n close to T-1 close (before event day)
            for n in pre_days:
                d0 = ed - pd.Timedelta(days=n + 7)  # lookback pad for weekends
                window = closes.loc[(closes.index < ed) & (closes.index >= d0)]
                if len(window) >= n + 1:
                    # last n sessions before event day
                    pre = window.iloc[-(n + 1) :]
                    if len(pre) >= 2:
                        rec[f"pre_ret_{n}d"] = float(pre.iloc[-1] / pre.iloc[0] - 1.0)
                    else:
                        rec[f"pre_ret_{n}d"] = np.nan
                else:
                    rec[f"pre_ret_{n}d"] = np.nan
            # post: from event day close (or next) to +n sessions
            post = closes.loc[closes.index >= ed]
            for n in post_days:
                if len(post) >= n + 1:
                    rec[f"post_ret_{n}d"] = float(post.iloc[n] / post.iloc[0] - 1.0)
                else:
                    rec[f"post_ret_{n}d"] = np.nan
            # gap: event day open / prior close
            if opens is not None and ed in opens.index:
                prior = closes.loc[closes.index < ed]
                if not prior.empty and pd.notna(opens.loc[ed]) and prior.iloc[-1]:
                    rec["gap_ret"] = float(opens.loc[ed] / prior.iloc[-1] - 1.0)
                else:
                    rec["gap_ret"] = np.nan
            else:
                rec["gap_ret"] = np.nan
            rows.append(rec)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["symbol", "earnings_date"]).reset_index(drop=True)
