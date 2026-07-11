"""Static TTM fundamentals loader — offline, no LaCie required for unit test."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aether.loaders.fundamentals import (
    attach_static_fundamentals,
    load_fundamentals_table,
    load_symbol_fundamentals,
)
from aether.engine.scorer import LogisticScorer


def _write_fund(root: Path, symbol: str, *, pe: float, roe: float) -> None:
    d = root / symbol
    d.mkdir(parents=True)
    (d / "ratios_ttm.json").write_text(
        json.dumps(
            [
                {
                    "symbol": symbol,
                    "grossProfitMarginTTM": 0.4,
                    "operatingProfitMarginTTM": 0.3,
                    "netProfitMarginTTM": 0.2,
                    "currentRatioTTM": 1.5,
                    "debtToEquityRatioTTM": 0.5,
                    "priceToEarningsRatioTTM": pe,
                    "priceToBookRatioTTM": 4.0,
                    "priceToSalesRatioTTM": 5.0,
                }
            ]
        )
    )
    (d / "key_metrics_ttm.json").write_text(
        json.dumps(
            [
                {
                    "symbol": symbol,
                    "returnOnEquityTTM": roe,
                    "returnOnAssetsTTM": 0.1,
                    "evToSalesTTM": 6.0,
                    "evToEBITDATTM": 12.0,
                    "evToFreeCashFlowTTM": 20.0,
                    "netDebtToEBITDATTM": 0.2,
                    "incomeQualityTTM": 1.0,
                }
            ]
        )
    )


def test_load_symbol_fundamentals(tmp_path: Path):
    _write_fund(tmp_path, "AAPL", pe=25.0, roe=0.5)
    row = load_symbol_fundamentals("AAPL", root=tmp_path)
    assert row["symbol"] == "AAPL"
    assert row["fund_pe"] == 25.0
    assert row["fund_roe"] == 0.5
    assert row["fund_gross_margin"] == 0.4
    assert "fund_asof" in row


def test_attach_static_fundamentals(tmp_path: Path):
    _write_fund(tmp_path, "AAPL", pe=30.0, roe=0.4)
    _write_fund(tmp_path, "NVDA", pe=40.0, roe=0.6)
    panel = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "NVDA", "SPY"],
            "date": pd.to_datetime(
                ["2024-01-02", "2024-01-03", "2024-01-02", "2024-01-02"]
            ),
            "ret_1d": [0.01, -0.01, 0.02, 0.0],
        }
    )
    out = attach_static_fundamentals(panel, root=tmp_path)
    assert "fund_pe" in out.columns
    aapl = out[out["symbol"] == "AAPL"]
    assert (aapl["fund_pe"] == 30.0).all()
    spy = out[out["symbol"] == "SPY"]
    assert spy["fund_pe"].isna().all()


def test_scorer_tolerates_partial_fund_nan():
    """ETF rows with NaN fund_* must not zero the whole training set."""
    n = 120
    df = pd.DataFrame(
        {
            "ret_1d": [0.001] * n,
            "ret_5d": [0.002] * n,
            "px_vs_sma20": [0.01] * n,
            "rsi_14": [55.0] * n,
            "rvol_20": [0.15] * n,
            "trend_stack": [2.0] * n,
            "fund_pe": [25.0] * 60 + [float("nan")] * 60,
            "fund_roe": [0.2] * 60 + [float("nan")] * 60,
            "y_up_5d": [1.0 if i % 2 == 0 else 0.0 for i in range(n)],
        }
    )
    scorer = LogisticScorer(
        feature_cols=("ret_1d", "ret_5d", "px_vs_sma20", "rsi_14", "rvol_20", "trend_stack", "fund_pe", "fund_roe"),
        epochs=20,
    ).fit(df)
    assert scorer.w is not None
    assert len(scorer.w) >= 6
    p = scorer.predict_proba(df)
    assert len(p) == n
    assert (p >= 0).all() and (p <= 1).all()


def test_load_fundamentals_table(tmp_path: Path):
    _write_fund(tmp_path, "AAPL", pe=22.0, roe=0.3)
    _write_fund(tmp_path, "MSFT", pe=28.0, roe=0.35)
    t = load_fundamentals_table(["AAPL", "MSFT", "MISSING"], root=tmp_path)
    assert set(t["symbol"]) == {"AAPL", "MSFT"}
    assert float(t.loc[t["symbol"] == "AAPL", "fund_pe"].iloc[0]) == 22.0
