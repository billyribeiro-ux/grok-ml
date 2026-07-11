"""
Baseline probabilistic scorer — pure numpy logistic regression.

Trains on past labels only (walk-forward ready). No sklearn dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

FEATURE_COLS = (
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "px_vs_sma20",
    "px_vs_sma50",
    "sma20_vs_sma50",
    "atr_pct",
    "range_pos_20d",
    "vol_z_20",
    "rsi_14",
    "rvol_20",
    "gap_pct",
    "above_sma200",
    "trend_stack",
    "breadth_integrity",
    "uncertainty",
    "vol_regime",
    "trend_energy",
)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -40, 40)
    return 1.0 / (1.0 + np.exp(-z))


@dataclass
class LogisticScorer:
    """Binary direction scorer P(up) for a fixed horizon label column."""

    feature_cols: tuple[str, ...] = FEATURE_COLS
    lr: float = 0.05
    epochs: int = 80
    l2: float = 1e-3
    w: np.ndarray | None = None
    b: float = 0.0
    mu: np.ndarray | None = None
    sig: np.ndarray | None = None
    label_col: str = "y_up_5d"

    def _xy(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
        cols = [c for c in self.feature_cols if c in df.columns]
        if not cols:
            raise ValueError("no feature columns present")
        x = df[cols].astype(float).to_numpy()
        y = df[self.label_col].astype(float).to_numpy()
        mask = np.isfinite(x).all(axis=1) & np.isfinite(y)
        return x[mask], y[mask], cols

    def fit(self, df: pd.DataFrame) -> LogisticScorer:
        x, y, cols = self._xy(df)  # type: ignore[misc]
        self.feature_cols = tuple(cols)
        if len(y) < 50:
            # underdetermined — zero model (always 0.5)
            self.w = np.zeros(len(cols))
            self.b = 0.0
            self.mu = np.zeros(len(cols))
            self.sig = np.ones(len(cols))
            return self

        self.mu = x.mean(axis=0)
        self.sig = x.std(axis=0)
        self.sig[self.sig < 1e-8] = 1.0
        xn = (x - self.mu) / self.sig

        w = np.zeros(xn.shape[1])
        b = 0.0
        n = xn.shape[0]
        for _ in range(self.epochs):
            p = _sigmoid(xn @ w + b)
            err = p - y
            grad_w = (xn.T @ err) / n + self.l2 * w
            grad_b = float(err.mean())
            w -= self.lr * grad_w
            b -= self.lr * grad_b
        self.w = w
        self.b = b
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        if self.w is None or self.mu is None or self.sig is None:
            return np.full(len(df), 0.5)
        cols = list(self.feature_cols)
        x = np.zeros((len(df), len(cols)))
        for j, c in enumerate(cols):
            if c in df.columns:
                x[:, j] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).to_numpy()
        xn = (x - self.mu) / self.sig
        p = _sigmoid(xn @ self.w + self.b)
        # if row had all-nan originals, keep 0.5
        return p

    def score_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["p_up"] = self.predict_proba(out)
        out["p_down"] = 1.0 - out["p_up"]
        return out
