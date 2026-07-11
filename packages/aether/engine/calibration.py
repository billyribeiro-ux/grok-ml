"""Calibration utilities — reliability of probability-like confidences."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    n: int
    brier: float
    bins: list[dict]


def brier_score(y_true: np.ndarray, p: np.ndarray) -> float:
    y = y_true.astype(float)
    p = np.clip(p.astype(float), 0.0, 1.0)
    return float(np.mean((p - y) ** 2))


def reliability_table(
    y_true: np.ndarray,
    p: np.ndarray,
    n_bins: int = 10,
) -> CalibrationReport:
    y = y_true.astype(float)
    p = np.clip(p.astype(float), 0.0, 1.0)
    bins = []
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi if i < n_bins - 1 else p <= hi)
        if not np.any(mask):
            bins.append({"lo": lo, "hi": hi, "n": 0, "avg_p": None, "avg_y": None})
            continue
        bins.append(
            {
                "lo": float(lo),
                "hi": float(hi),
                "n": int(mask.sum()),
                "avg_p": float(p[mask].mean()),
                "avg_y": float(y[mask].mean()),
            }
        )
    return CalibrationReport(n=int(len(y)), brier=brier_score(y, p), bins=bins)


def summarize_signals(df: pd.DataFrame) -> dict:
    """df needs columns: confidence, y (0/1 realized)."""
    if df.empty or "confidence" not in df.columns or "y" not in df.columns:
        return {"n": 0, "brier": None}
    rep = reliability_table(df["y"].values, df["confidence"].values)
    return {"n": rep.n, "brier": rep.brier, "bins": rep.bins}
