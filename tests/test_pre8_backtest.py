"""Unit tests for pre8 paper backtest helpers — no LaCie required."""

from __future__ import annotations

import numpy as np

from aether.engine.pre8_backtest import _max_dd
from aether.engine.pre8_threshold_grid import _grid_side


def test_max_dd_empty():
    assert _max_dd(np.array([])) == 0.0
    assert _max_dd(np.array([0.0, 0.0])) == 0.0


def test_max_dd_known_path():
    # +10%, -20% from peak → drawdown from 1.1 to 0.88 = -20%
    rets = np.array([0.10, -0.20])
    dd = _max_dd(rets)
    assert dd < 0
    assert abs(dd - (-0.20)) < 1e-9


def test_max_dd_ignores_zeros():
    rets = np.array([0.0, 0.05, 0.0, -0.10, 0.0])
    dd = _max_dd(rets)
    # path: 1.05 → 0.945 → dd = (0.945-1.05)/1.05
    expected = (0.945 - 1.05) / 1.05
    assert abs(dd - expected) < 1e-9


def test_grid_side_long():
    p_up = np.array([0.70, 0.60, 0.40, 0.55])
    pnl = np.array([0.02, -0.01, 0.05, 0.03])
    rows = _grid_side(p_up, pnl, (0.55, 0.65), side="long")
    assert rows[0]["n"] == 3  # 0.70, 0.60, 0.55
    assert abs(rows[0]["mean"] - np.mean([0.02, -0.01, 0.03])) < 1e-12
    assert rows[1]["n"] == 1
    assert abs(rows[1]["mean"] - 0.02) < 1e-12


def test_grid_side_short_negates_pnl():
    p_up = np.array([0.30, 0.70])
    pnl = np.array([0.04, -0.02])  # short the first: -0.04
    rows = _grid_side(p_up, pnl, (0.40,), side="short")
    assert rows[0]["n"] == 1
    assert abs(rows[0]["mean"] - (-0.04)) < 1e-12
