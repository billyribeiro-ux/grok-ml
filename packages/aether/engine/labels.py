"""Multi-horizon path labels — train what we trade (distributional, as-of safe)."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Horizons in trading days
DEFAULT_HORIZONS = (1, 5, 20)

_HORIZON_RE = re.compile(r"_(\d+)d$")


def label_horizon(label_col: str) -> int:
    """
    Trading-day horizon encoded in a label name, e.g. 'y_up_20d' -> 20.

    The purge gap between train and test must be at least this large: a row at
    index i has its label resolved at i+h, so training on rows within h of the
    cut leaks outcomes from inside the test window.
    """
    m = _HORIZON_RE.search(label_col)
    if not m:
        raise ValueError(
            f"cannot infer horizon from label column {label_col!r} — "
            "expected a name ending in '_<n>d' (e.g. 'y_up_5d')"
        )
    return int(m.group(1))


def add_forward_labels(
    df: pd.DataFrame,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    price_col: str = "adj_close",
) -> pd.DataFrame:
    """
    For each symbol, attach forward returns and MFE/MAE over horizons.

    Labels at row t use only future path relative to t (for training).
    At inference, labels are unavailable — engine never reads them online.
    """
    parts = []
    for _, g in df.groupby("symbol", sort=False):
        parts.append(_label_one(g.sort_values("date").copy(), horizons, price_col))
    if not parts:
        return df.copy()
    return pd.concat(parts, ignore_index=True)


def _label_one(g: pd.DataFrame, horizons: tuple[int, ...], price_col: str) -> pd.DataFrame:
    px = g[price_col].astype(float).values
    n = len(px)
    high = g["high"].astype(float).values
    low = g["low"].astype(float).values

    for h in horizons:
        fwd = np.full(n, np.nan)
        mfe = np.full(n, np.nan)
        mae = np.full(n, np.nan)
        # simple direction label
        y = np.full(n, np.nan)
        for i in range(n - h):
            p0 = px[i]
            p1 = px[i + h]
            fwd[i] = p1 / p0 - 1.0
            window_high = high[i + 1 : i + h + 1].max()
            window_low = low[i + 1 : i + h + 1].min()
            mfe[i] = window_high / p0 - 1.0
            mae[i] = window_low / p0 - 1.0
            y[i] = 1.0 if fwd[i] > 0 else 0.0
        g[f"fwd_ret_{h}d"] = fwd
        g[f"mfe_{h}d"] = mfe
        g[f"mae_{h}d"] = mae
        g[f"y_up_{h}d"] = y
        # pivot quality: large giveback of prior impulse (soft top/bottom fuel)
        prior = pd.Series(px).pct_change(h).values
        g[f"reversal_score_{h}d"] = -np.sign(prior) * fwd  # positive if reverts prior move
    return g
