"""
Pre8 buy-rumor threshold grid from OOS specialist scores.

Local only. Equal-notional event stats — not a concurrent multi-name book.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aether.paths import PROCESSED, require_lacie

RESEARCH = PROCESSED / "research"

DEFAULT_LONG_THRS = (0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70)
DEFAULT_SHORT_THRS = (0.50, 0.48, 0.45, 0.42, 0.40, 0.35)


def _grid_side(
    p_up: np.ndarray,
    pnl: np.ndarray,
    thresholds: tuple[float, ...] | list[float],
    *,
    side: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for thr in thresholds:
        m = p_up >= thr if side == "long" else p_up <= thr
        n = int(m.sum())
        if n == 0:
            rows.append({"thr": float(thr), "n": 0})
            continue
        rets = pnl[m] if side == "long" else -pnl[m]
        rows.append(
            {
                "thr": float(thr),
                "n": n,
                "mean": float(rets.mean()),
                "hit": float((rets > 0).mean()),
                "sum": float(rets.sum()),
                "median": float(np.median(rets)),
            }
        )
    return rows


def run_pre8_threshold_grid(
    universes: tuple[str, ...] = ("sp500", "iwm", "nasdaq"),
    *,
    long_thresholds: tuple[float, ...] = DEFAULT_LONG_THRS,
    short_thresholds: tuple[float, ...] = DEFAULT_SHORT_THRS,
    write: bool = True,
) -> dict[str, Any]:
    require_lacie()
    out: dict[str, Any] = {}
    for univ in universes:
        path = RESEARCH / f"earnings_specialist_{univ}_pre8_oos.parquet"
        if not path.exists():
            out[univ] = {"error": f"missing {path.name}"}
            continue
        df = pd.read_parquet(path)
        if "p_up" not in df.columns:
            out[univ] = {"error": "missing p_up"}
            continue
        pnl_col = "pnl" if "pnl" in df.columns else "pre_ret_8d"
        if pnl_col not in df.columns:
            out[univ] = {"error": "missing pnl/pre_ret_8d"}
            continue
        df = df[pd.to_numeric(df[pnl_col], errors="coerce").abs() <= 0.50].copy()
        p_up = df["p_up"].to_numpy(dtype=float)
        pnl = df[pnl_col].to_numpy(dtype=float)
        long_grid = _grid_side(p_up, pnl, long_thresholds, side="long")
        short_grid = _grid_side(p_up, pnl, short_thresholds, side="short")
        # best long with n>=20
        candidates = [r for r in long_grid if r.get("n", 0) >= 20 and "mean" in r]
        best_long = max(candidates, key=lambda r: r["mean"]) if candidates else None
        out[univ] = {
            "n_oos": int(len(df)),
            "base_up_rate": float((pnl > 0).mean()) if len(pnl) else None,
            "base_mean": float(pnl.mean()) if len(pnl) else None,
            "long_grid": long_grid,
            "short_grid": short_grid,
            "best_long_n20": best_long,
        }

    payload: dict[str, Any] = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Equal-notional OOS event grid for pre8 buy-rumor / short-into-print. "
            "Not a concurrent multi-name portfolio."
        ),
        "universes": out,
    }
    if write:
        dest = RESEARCH / "pre8_threshold_grid.json"
        dest.write_text(json.dumps(payload, indent=2, default=str))
        payload["path"] = str(dest)
    return payload
