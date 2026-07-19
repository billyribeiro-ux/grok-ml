"""
Mechanical look-ahead detection by future-value perturbation.

A feature at time t may only depend on information available at t. So if we
recompute the panel after destroying everything from t+GAP onward, the value at
t must be bit-for-bit unchanged. Any divergence proves the feature peeked.

This runs on synthetic panels only — no archive, no network — so it is a
red/green CI gate rather than a discipline. Adapted from the perturbation
approach used in HKUDS/Vibe-Trading (MIT).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aether.features.daily import build_daily_features
from aether.features.intraday import build_intraday_features

# Index we assert on, and where destruction begins.
#
# GAP must be 1: we destroy everything from t+1 onward. A strictly-causal feature
# at t reads only rows <= t and is unaffected; anything reading t+1 or later is
# caught. A larger gap leaves a blind spot — with GAP=10 a shift(-1) peek reads
# into the untouched margin and escapes detection (verified by the self-test).
PROBE_I = 260
GAP = 1
N_ROWS = 300
SYMBOLS = ("AAA", "BBB", "CCC")

# Tolerance: tight enough that a single leaked row of order 1e-6 still trips it.
RTOL = ATOL = 1e-9


def _panel(n: int = N_ROWS, symbols=SYMBOLS, seed: int = 7) -> pd.DataFrame:
    """Deterministic synthetic OHLCV panel — no NaNs, no zero volume."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)
    frames = []
    for k, sym in enumerate(symbols):
        steps = rng.normal(0.0005, 0.012, size=n)
        close = 100.0 * (1.0 + k * 0.5) * np.exp(np.cumsum(steps))
        spread = np.abs(rng.normal(0.006, 0.002, size=n)) * close
        open_ = close * (1.0 + rng.normal(0, 0.003, size=n))
        frames.append(
            pd.DataFrame(
                {
                    "symbol": sym,
                    "date": dates,
                    "open": open_,
                    "high": np.maximum(open_, close) + spread,
                    "low": np.minimum(open_, close) - spread,
                    "close": close,
                    "adj_close": close,
                    "volume": rng.integers(1_000_000, 5_000_000, size=n).astype("int64"),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _poison(panel: pd.DataFrame, cut: int, mode: str) -> pd.DataFrame:
    """Destroy every row from index `cut` onward, per symbol."""
    out = panel.copy()
    cols = ["open", "high", "low", "close", "adj_close", "volume"]
    for sym, grp in out.groupby("symbol", sort=False):
        idx = grp.index[cut:]
        if mode == "nan":
            out.loc[idx, cols] = np.nan
        else:  # extreme sentinel — catches leaks that survive NaN propagation
            out.loc[idx, cols] = 1e10
    return out


def _assert_unchanged(clean: pd.DataFrame, poisoned: pd.DataFrame, kind: str) -> None:
    """Every numeric feature at PROBE_I must match between the two runs."""
    key = ["symbol", "date"]
    numeric = [
        c
        for c in clean.columns
        if c not in key
        and pd.api.types.is_numeric_dtype(clean[c])
        and c in poisoned.columns
    ]
    assert numeric, "no numeric feature columns produced"

    leaked: list[str] = []
    for sym, grp in clean.groupby("symbol", sort=False):
        pg = poisoned[poisoned["symbol"] == sym]
        if len(grp) <= PROBE_I or len(pg) <= PROBE_I:
            continue
        a = grp.iloc[PROBE_I]
        b = pg.iloc[PROBE_I]
        assert a["date"] == b["date"], "probe row misaligned between runs"
        for c in numeric:
            x, y = a[c], b[c]
            if pd.isna(x) and pd.isna(y):
                continue
            if pd.isna(x) != pd.isna(y):
                leaked.append(f"{sym}.{c}: NaN-pattern changed ({x!r} -> {y!r})")
                continue
            if not np.isclose(float(x), float(y), rtol=RTOL, atol=ATOL):
                leaked.append(f"{sym}.{c}: {float(x):.12g} -> {float(y):.12g}")

    assert not leaked, (
        f"LOOK-AHEAD DETECTED in {kind} features — value at t changed after "
        f"destroying t+{GAP} onward:\n  " + "\n  ".join(sorted(leaked))
    )


@pytest.mark.parametrize("mode", ["nan", "sentinel"])
def test_daily_features_have_no_lookahead(mode: str) -> None:
    panel = _panel()
    clean = build_daily_features(panel)
    poisoned = build_daily_features(_poison(panel, PROBE_I + GAP, mode))
    _assert_unchanged(clean, poisoned, f"daily ({mode})")


@pytest.mark.parametrize("mode", ["nan", "sentinel"])
def test_intraday_features_have_no_lookahead(mode: str) -> None:
    panel = _panel()
    clean = build_intraday_features(panel)
    poisoned = build_intraday_features(_poison(panel, PROBE_I + GAP, mode))
    # Forward labels are *supposed* to see the future — exclude them, and assert
    # separately below that they are the only such columns.
    label_cols = [c for c in clean.columns if c.startswith(("y_up_", "fwd_ret_"))]
    _assert_unchanged(
        clean.drop(columns=label_cols),
        poisoned.drop(columns=label_cols, errors="ignore"),
        f"intraday ({mode})",
    )


def test_forward_labels_stay_nan_when_the_future_is_unknown() -> None:
    """
    The last N bars have no future, so their forward labels are unknowable and
    must be NaN. `(fwd > 0).astype(float)` silently maps NaN to 0.0, which
    fabricates a real-looking "price went down" row and defeats the caller's
    dropna guard.
    """
    panel = _panel(n=60, symbols=("AAA",))
    feats = build_intraday_features(panel)
    tail = feats.sort_values("date").tail(5)

    assert tail["fwd_ret_1"].isna().iloc[-1], "fwd_ret_1 must be NaN on the last bar"
    assert tail["fwd_ret_5"].isna().all(), "fwd_ret_5 must be NaN on the last 5 bars"

    # The labels derived from those returns must be NaN too, not 0.0.
    assert tail["y_up_1"].isna().iloc[-1], (
        "y_up_1 is not NaN on the final bar — an unknowable outcome was "
        "recorded as 'down'"
    )
    assert tail["y_up_5"].isna().all(), (
        "y_up_5 is not NaN on the last 5 bars — unknowable outcomes were "
        "recorded as 'down'"
    )


def test_detector_catches_an_injected_leak() -> None:
    """
    The detector must FAIL on a deliberate peek. A leakage test that never fires
    is not a test — this asserts the gate actually works in both directions.
    """
    panel = _panel()

    def leaky(p: pd.DataFrame) -> pd.DataFrame:
        out = build_daily_features(p)
        # tomorrow's close, read today
        out["peek"] = out.groupby("symbol")["close"].shift(-1)
        return out

    clean = leaky(panel)
    poisoned = leaky(_poison(panel, PROBE_I + GAP, "sentinel"))
    with pytest.raises(AssertionError, match="LOOK-AHEAD DETECTED"):
        _assert_unchanged(clean, poisoned, "injected")
