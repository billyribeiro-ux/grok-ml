"""Regime / market state estimator — simple, auditable F1 version of z_t."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from aether.engine.types import RegimeState


def estimate_regime_from_features(
    feat_row: pd.Series,
    *,
    as_of: date | None = None,
) -> RegimeState:
    """
    Map daily F1 features → RegimeState axes in [-1,1] or [0,1].

    Uses only the as-of feature row (no future). When sensors missing,
    uncertainty rises — STAND_DOWN pressure increases.
    """
    def f(key: str, default: float = np.nan) -> float:
        v = feat_row.get(key, default)
        try:
            x = float(v)
            if np.isnan(x):
                return default
            return x
        except Exception:
            return default

    trend = 0.0
    # trend_stack is 0..3
    ts = f("trend_stack", 0.0)
    if not np.isnan(ts):
        trend = (ts / 3.0) * 2.0 - 1.0  # map to ~-1..1 if we had bipolar; here 0..1 → -1..1-ish
        trend = float(np.clip(ts / 3.0, 0, 1) * 2 - 1)

    # ret_20d as energy
    r20 = f("ret_20d", 0.0)
    if not np.isnan(r20):
        trend = float(np.clip(0.6 * trend + 0.4 * np.tanh(r20 * 8), -1, 1))

    rvol = f("rvol_20", 0.15)
    if np.isnan(rvol):
        rvol = 0.15
        miss_vol = 1.0
    else:
        miss_vol = 0.0
    vol_regime = float(np.clip(rvol / 0.40, 0, 1))  # 40% ann vol ~ extreme

    # breadth proxy: if only one name, unknown → high uncertainty contribution
    breadth = f("breadth_integrity", np.nan)
    if np.isnan(breadth):
        breadth = 0.5
        miss_breadth = 1.0
    else:
        miss_breadth = 0.0

    # liquidity stress from atr and vol z
    atr_pct = f("atr_pct", 0.02)
    vol_z = f("vol_z_20", 0.0)
    if np.isnan(atr_pct):
        atr_pct = 0.02
    if np.isnan(vol_z):
        vol_z = 0.0
    liquidity_stress = float(np.clip(atr_pct / 0.05 + max(0.0, vol_z) / 5.0, 0, 1))

    corr_disp = f("corr_dispersion", 0.5)
    if np.isnan(corr_disp):
        corr_disp = 0.5
        miss_corr = 1.0
    else:
        miss_corr = 0.0

    # uncertainty accumulates missing sensors + extreme vol
    uncertainty = float(
        np.clip(0.25 * miss_breadth + 0.25 * miss_vol + 0.2 * miss_corr + 0.3 * vol_regime, 0, 1)
    )

    d = as_of
    if d is None:
        raw_d = feat_row.get("date") or feat_row.get("as_of")
        d = pd.Timestamp(raw_d).date() if raw_d is not None else date.today()

    return RegimeState(
        as_of=d,
        trend_energy=trend,
        breadth_integrity=float(breadth),
        vol_regime=vol_regime,
        liquidity_stress=liquidity_stress,
        corr_dispersion=float(corr_disp),
        uncertainty=uncertainty,
        raw={
            "ret_20d": r20 if not np.isnan(r20) else 0.0,
            "rvol_20": rvol,
            "atr_pct": atr_pct,
            "trend_stack": ts if not np.isnan(ts) else 0.0,
        },
    )


def estimate_regime_panel(features: pd.DataFrame) -> pd.DataFrame:
    """Attach regime columns to a feature panel."""
    rows = []
    for _, r in features.iterrows():
        st = estimate_regime_from_features(r)
        rows.append(
            {
                "symbol": r.get("symbol"),
                "date": r.get("date"),
                "trend_energy": st.trend_energy,
                "breadth_integrity": st.breadth_integrity,
                "vol_regime": st.vol_regime,
                "liquidity_stress": st.liquidity_stress,
                "corr_dispersion": st.corr_dispersion,
                "uncertainty": st.uncertainty,
            }
        )
    return pd.DataFrame(rows)
