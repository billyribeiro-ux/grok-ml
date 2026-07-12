"""
Earnings / pre-earnings event study for **index constituents**.

Local only. No network. Does not invent events or prices.

Trade frames:
  - post_*  : reaction after the print
  - pre_*   : run-up into the print (buy-the-rumor)
  - pre8    : 8-session window ending T-1 (sell before news)
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
    pre_days: tuple[int, ...] = (1, 3, 5, 8),
    post_days: tuple[int, ...] = (1, 3, 5),
) -> pd.DataFrame:
    """
    One row per (symbol, earnings_date).

    Session-count windows (not calendar days):
      pre_ret_Nd   : return from close of T-N to close of T-1 (before print day)
      pre_vol_Nd   : std of daily rets in that window
      trail_vol_20 : std of 20 sessions ending at T-N (before entry)
      vol_spike_8  : pre_vol_8d / trail_vol_20  (vol expansion into event)
      mom_5/20_at_t8, ret_1_at_t8 : known at 8-session entry (no leak of pre_ret_8)
      sell_news_ret: T-1 close → first post close (gap through news)
      post_ret_Nd  : reaction after print day
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

    # previous surprise per symbol for entry features
    ev_sorted = ev.sort_values(["symbol", "date"])
    prev_surprise: dict[tuple[str, pd.Timestamp], float] = {}
    for sym, g in ev_sorted.groupby("symbol"):
        prev = np.nan
        for _, r in g.iterrows():
            ed = pd.Timestamp(r["date"]).normalize()
            prev_surprise[(str(sym), ed)] = prev
            s = r.get("eps_surprise_pct")
            if s is not None and pd.notna(s):
                prev = float(s)

    rows: list[dict] = []
    for sym, e_sym in ev.groupby("symbol"):
        p = px[px["symbol"] == sym].set_index("date").sort_index()
        if p.empty:
            continue
        closes = p["close"].astype(float)
        opens = p["open"].astype(float) if "open" in p.columns else None
        highs = p["high"].astype(float) if "high" in p.columns else closes
        lows = p["low"].astype(float) if "low" in p.columns else closes
        daily_ret = closes.pct_change()

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
                "last_eps_surprise_pct": prev_surprise.get((str(sym), ed), np.nan),
            }

            pre = closes.loc[closes.index < ed]
            post = closes.loc[closes.index >= ed]

            # --- pre N-session run-up ending T-1 ---
            for n in pre_days:
                if len(pre) >= n + 1:
                    # closes: [entry=T-N, ..., T-1]  length n+1 → n returns
                    seg = pre.iloc[-(n + 1) :]
                    rec[f"pre_ret_{n}d"] = float(seg.iloc[-1] / seg.iloc[0] - 1.0)
                    rets = daily_ret.loc[seg.index].iloc[1:]  # n rets
                    rec[f"pre_vol_{n}d"] = float(rets.std()) if len(rets) >= 2 else np.nan
                    # high-low range expansion
                    if highs is not None and lows is not None:
                        hi = highs.loc[seg.index].max()
                        lo = lows.loc[seg.index].min()
                        mid = float(seg.mean())
                        rec[f"pre_range_{n}d"] = float((hi - lo) / mid) if mid else np.nan
                else:
                    rec[f"pre_ret_{n}d"] = np.nan
                    rec[f"pre_vol_{n}d"] = np.nan
                    rec[f"pre_range_{n}d"] = np.nan

            # --- entry features at T-8 (known when opening buy-the-rumor) ---
            if len(pre) >= 8 + 5:
                # T-8 is pre.iloc[-8]; history strictly before entry
                entry_px = float(pre.iloc[-8])
                hist = pre.iloc[:-8]
                rec["entry_t8_date"] = pre.index[-8]
                rec["entry_t8_close"] = entry_px
                rec["exit_t1_close"] = float(pre.iloc[-1])
                if len(hist) >= 20:
                    rec["mom_20_at_t8"] = float(hist.iloc[-1] / hist.iloc[-20] - 1.0)
                else:
                    rec["mom_20_at_t8"] = np.nan
                if len(hist) >= 5:
                    rec["mom_5_at_t8"] = float(hist.iloc[-1] / hist.iloc[-5] - 1.0)
                else:
                    rec["mom_5_at_t8"] = np.nan
                if len(hist) >= 2:
                    rec["ret_1_at_t8"] = float(hist.iloc[-1] / hist.iloc[-2] - 1.0)
                else:
                    rec["ret_1_at_t8"] = np.nan
                # trailing vol before entry (20 sessions)
                if len(hist) >= 21:
                    tr = daily_ret.loc[hist.index].iloc[-20:]
                    rec["trail_vol_20"] = float(tr.std()) if len(tr) >= 5 else np.nan
                else:
                    rec["trail_vol_20"] = np.nan
            else:
                rec["entry_t8_date"] = pd.NaT
                rec["entry_t8_close"] = np.nan
                rec["exit_t1_close"] = float(pre.iloc[-1]) if len(pre) else np.nan
                rec["mom_20_at_t8"] = np.nan
                rec["mom_5_at_t8"] = np.nan
                rec["ret_1_at_t8"] = np.nan
                rec["trail_vol_20"] = np.nan

            # vol spike: realized vol in 8d pre window vs trail
            pv8 = rec.get("pre_vol_8d")
            tv = rec.get("trail_vol_20")
            if pv8 is not None and tv is not None and pd.notna(pv8) and pd.notna(tv) and tv > 1e-12:
                rec["vol_spike_8"] = float(pv8 / tv)
            else:
                rec["vol_spike_8"] = np.nan

            # sell-the-news: T-1 close → first session on/after print
            if len(pre) and len(post):
                rec["sell_news_ret"] = float(post.iloc[0] / pre.iloc[-1] - 1.0)
            else:
                rec["sell_news_ret"] = np.nan

            # post reaction
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
