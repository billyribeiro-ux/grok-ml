"""
Paper simulation of buy-the-rumor / sell-the-news (T-8 → T-1) using OOS specialist scores.

Local only. Reads earnings_specialist_*_pre8_oos.parquet from LaCie research.
Does not invent fills — uses realized pre_ret_8d as trade PnL when signal fires.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from aether.paths import PROCESSED, require_lacie

RESEARCH = PROCESSED / "research"


@dataclass
class Pre8BacktestResult:
    universe: str
    n_oos: int
    n_long: int
    n_short: int
    n_flat: int
    long_threshold: float
    short_threshold: float
    sum_long_only: float
    sum_long_short: float
    # legacy alias for cockpit (sum of event PnLs, equal notional — not multi-year compound)
    cum_long_only: float
    cum_long_short: float
    mean_long: float | None
    mean_short: float | None
    mean_flat_skip: float | None
    hit_rate_long: float | None
    hit_rate_short: float | None
    max_dd_long_only: float
    written_at: str
    path: str | None = None


def _max_dd(rets: np.ndarray) -> float:
    """Max drawdown on equal-notional sequential event equity (1 + r compounding)."""
    if len(rets) == 0:
        return 0.0
    # use only traded events for path
    traded = rets[rets != 0]
    if len(traded) == 0:
        return 0.0
    eq = np.cumprod(1.0 + traded)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / np.maximum(peak, 1e-12)
    return float(dd.min())


def run_pre8_backtest(
    universe: str = "sp500",
    *,
    long_threshold: float = 0.55,
    short_threshold: float = 0.45,
    write: bool = True,
) -> Pre8BacktestResult:
    require_lacie()
    path = RESEARCH / f"earnings_specialist_{universe}_pre8_oos.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing OOS scores: {path} — run earnings-specialist --mode pre8")
    df = pd.read_parquet(path)
    if "p_up" not in df.columns:
        raise ValueError("oos parquet missing p_up")
    pnl_col = "pnl" if "pnl" in df.columns else "pre_ret_8d"
    if pnl_col not in df.columns:
        raise ValueError("oos parquet missing pnl/pre_ret_8d")

    df = df.copy()
    df["earnings_date"] = pd.to_datetime(df["earnings_date"])
    df = df.sort_values("earnings_date")
    # drop absurd outliers again
    df = df[pd.to_numeric(df[pnl_col], errors="coerce").abs() <= 0.50]

    p = df["p_up"].to_numpy(dtype=float)
    pnl = df[pnl_col].to_numpy(dtype=float)

    long_m = p >= long_threshold
    short_m = p <= short_threshold
    flat_m = ~(long_m | short_m)

    long_rets = pnl[long_m]
    short_rets = -pnl[short_m]  # short the name into the print
    flat_rets = pnl[flat_m]

    # equal-notional per signal event (honest: not a levered multi-year compound of 2k trades)
    strat_long = np.where(long_m, pnl, 0.0)
    strat_ls = np.where(long_m, pnl, np.where(short_m, -pnl, 0.0))
    sum_lo = float(strat_long.sum())
    sum_ls = float(strat_ls.sum())

    result = Pre8BacktestResult(
        universe=universe,
        n_oos=int(len(df)),
        n_long=int(long_m.sum()),
        n_short=int(short_m.sum()),
        n_flat=int(flat_m.sum()),
        long_threshold=long_threshold,
        short_threshold=short_threshold,
        sum_long_only=sum_lo,
        sum_long_short=sum_ls,
        cum_long_only=sum_lo,
        cum_long_short=sum_ls,
        mean_long=float(long_rets.mean()) if len(long_rets) else None,
        mean_short=float(short_rets.mean()) if len(short_rets) else None,
        mean_flat_skip=float(flat_rets.mean()) if len(flat_rets) else None,
        hit_rate_long=float((long_rets > 0).mean()) if len(long_rets) else None,
        hit_rate_short=float((short_rets > 0).mean()) if len(short_rets) else None,
        max_dd_long_only=_max_dd(strat_long) if long_m.any() else 0.0,
        written_at=datetime.now(timezone.utc).isoformat(),
    )

    if write:
        out = RESEARCH / f"pre8_backtest_{universe}.json"
        payload = asdict(result)
        payload["note"] = (
            "Equal-notional sum of OOS event PnLs (not concurrent multi-name portfolio). "
            "Long = buy T-8 sell T-1 when p_up>=threshold. "
            "Short = opposite when p_up<=short_threshold. "
            "cum_* aliases sum_* for cockpit display."
        )
        out.write_text(json.dumps(payload, indent=2, default=str))
        result.path = str(out)
    return result


def run_all_pre8_backtests() -> dict[str, Pre8BacktestResult]:
    out = {}
    for u in ("sp500", "iwm", "nasdaq"):
        try:
            out[u] = run_pre8_backtest(u)
        except FileNotFoundError as e:
            print(f"skip {u}: {e}", flush=True)
    return out
