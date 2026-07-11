"""
Static TTM fundamentals from Session B archive (screener_fundamentals/).

Honest limits:
- Files are freeze snapshots as-of download date — NOT point-in-time history.
- We join constant-per-symbol columns onto the daily panel and tag fund_asof.
- Missing symbols (e.g. SPY ETF) stay NaN; scorer already drops non-finite rows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from aether.paths import FMP_RAW, require_lacie

# Default Session B fundamentals tree
DEFAULT_FUND_DIR = FMP_RAW / "liquid_10_700" / "screener_fundamentals"

# Sparse, interpretable TTM fields for the logistic scorer
# (keys match FMP stable ratios_ttm / key_metrics_ttm freeze files)
RATIO_FIELDS = (
    "grossProfitMarginTTM",
    "operatingProfitMarginTTM",
    "netProfitMarginTTM",
    "currentRatioTTM",
    "debtToEquityRatioTTM",
    "priceToEarningsRatioTTM",
    "priceToBookRatioTTM",
    "priceToSalesRatioTTM",
)

METRIC_FIELDS = (
    "returnOnEquityTTM",
    "returnOnAssetsTTM",
    "evToSalesTTM",
    "evToEBITDATTM",
    "evToFreeCashFlowTTM",
    "netDebtToEBITDATTM",
    "incomeQualityTTM",
)

# Map raw FMP keys → feature column names
RENAME = {
    "grossProfitMarginTTM": "fund_gross_margin",
    "operatingProfitMarginTTM": "fund_op_margin",
    "netProfitMarginTTM": "fund_net_margin",
    "returnOnEquityTTM": "fund_roe",
    "returnOnAssetsTTM": "fund_roa",
    "currentRatioTTM": "fund_current_ratio",
    "debtToEquityRatioTTM": "fund_debt_equity",
    "priceToEarningsRatioTTM": "fund_pe",
    "priceToBookRatioTTM": "fund_pb",
    "priceToSalesRatioTTM": "fund_ps",
    "evToSalesTTM": "fund_ev_sales",
    "evToEBITDATTM": "fund_ev_ebitda",
    "evToFreeCashFlowTTM": "fund_ev_fcf",
    "netDebtToEBITDATTM": "fund_net_debt_ebitda",
    "incomeQualityTTM": "fund_income_quality",
}

FUND_FEATURE_COLS = tuple(RENAME.values())


def fundamentals_dir() -> Path:
    require_lacie()
    return DEFAULT_FUND_DIR


def _read_json_first(path: Path) -> dict:
    if not path.exists() or path.stat().st_size < 2:
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    if isinstance(raw, list):
        return dict(raw[0]) if raw and isinstance(raw[0], dict) else {}
    if isinstance(raw, dict):
        # some endpoints nest under "data"
        if "data" in raw and isinstance(raw["data"], list) and raw["data"]:
            return dict(raw["data"][0]) if isinstance(raw["data"][0], dict) else {}
        return raw
    return {}


def load_symbol_fundamentals(
    symbol: str,
    root: Path | None = None,
) -> dict:
    """Load one symbol's TTM ratios + key metrics freeze. Empty dict if missing."""
    root = root or fundamentals_dir()
    d = root / symbol.upper()
    if not d.is_dir():
        return {}
    ratios = _read_json_first(d / "ratios_ttm.json")
    metrics = _read_json_first(d / "key_metrics_ttm.json")
    out: dict = {"symbol": symbol.upper()}
    for k in RATIO_FIELDS:
        if k in ratios and ratios[k] is not None:
            try:
                out[RENAME[k]] = float(ratios[k])
            except (TypeError, ValueError):
                pass
    for k in METRIC_FIELDS:
        if k in metrics and metrics[k] is not None:
            try:
                out[RENAME[k]] = float(metrics[k])
            except (TypeError, ValueError):
                pass
    # as-of from newest fund file mtime (honest freeze stamp)
    mtimes = []
    for name in ("ratios_ttm.json", "key_metrics_ttm.json"):
        p = d / name
        if p.exists():
            mtimes.append(p.stat().st_mtime)
    if mtimes:
        out["fund_asof"] = datetime.fromtimestamp(max(mtimes), tz=timezone.utc).date().isoformat()
    return out


def load_fundamentals_table(
    symbols: Iterable[str] | None = None,
    root: Path | None = None,
) -> pd.DataFrame:
    """
    Multi-symbol static fundamentals table.

    Columns: symbol + fund_* features (+ fund_asof).
    """
    root = root or fundamentals_dir()
    if not root.exists():
        return pd.DataFrame(columns=["symbol", *FUND_FEATURE_COLS, "fund_asof"])

    if symbols is None:
        syms = sorted(
            p.name
            for p in root.iterdir()
            if p.is_dir() and not p.name.startswith("._")
        )
    else:
        syms = [s.strip().upper() for s in symbols if s.strip()]

    rows = []
    for s in syms:
        row = load_symbol_fundamentals(s, root=root)
        if len(row) > 1:  # more than just symbol
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["symbol", *FUND_FEATURE_COLS, "fund_asof"])
    return pd.DataFrame(rows)


def attach_static_fundamentals(
    features: pd.DataFrame,
    *,
    root: Path | None = None,
    symbols: Iterable[str] | None = None,
) -> pd.DataFrame:
    """
    Left-join static TTM fundamentals onto a daily feature panel by symbol.

    Does not fabricate history — same fund_* values on every date for a symbol.
    """
    if features.empty or "symbol" not in features.columns:
        return features
    syms = symbols or features["symbol"].astype(str).unique().tolist()
    try:
        fund = load_fundamentals_table(syms, root=root)
    except Exception:
        # LaCie missing or corrupt — leave features unchanged
        return features
    if fund.empty:
        return features
    # drop fund_asof from merge key mess; keep as column
    out = features.merge(fund, on="symbol", how="left")
    return out
