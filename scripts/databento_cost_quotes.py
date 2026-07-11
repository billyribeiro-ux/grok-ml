#!/usr/bin/env python3
"""
Aether — Databento metadata.get_cost only (NO downloads).

Quotes USD cost for proposed historical pulls within a hard $125 budget.
Requires DATABENTO_API_KEY in project .env
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

KEY = os.getenv("DATABENTO_API_KEY") or os.getenv("DATABENTO_KEY")
if not KEY:
    raise SystemExit(
        "DATABENTO_API_KEY missing.\n"
        "Add to .env: DATABENTO_API_KEY=db-...\n"
        "Then re-run: python scripts/databento_cost_quotes.py"
    )

import databento as db  # noqa: E402

ASOF = date(2026, 7, 10)
OUT = ROOT / "data" / "databento" / "cost_quotes.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Priority symbol tiers for Aether
TIER_A = ["NVDA", "TSLA", "AAPL", "SPY", "QQQ"]
TIER_B = ["AMZN", "NFLX", "IWM", "CSCO"]
INVERSE = ["AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA"]
ALL_EQ = TIER_A + TIER_B + INVERSE

client = db.Historical(KEY)


def iso(d: date) -> str:
    return d.isoformat()


def cost(
    dataset: str,
    schema: str,
    symbols: list[str] | str,
    start: date,
    end: date,
    stype_in: str = "raw_symbol",
) -> dict[str, Any]:
    """Quote only — never download timeseries."""
    try:
        usd = client.metadata.get_cost(
            dataset=dataset,
            schema=schema,
            symbols=symbols,
            start=iso(start),
            end=iso(end),
            stype_in=stype_in,
        )
        return {
            "ok": True,
            "dataset": dataset,
            "schema": schema,
            "symbols": symbols if isinstance(symbols, str) else list(symbols),
            "n_symbols": 1 if isinstance(symbols, str) else len(symbols),
            "start": iso(start),
            "end": iso(end),
            "cost_usd": float(usd),
        }
    except Exception as e:
        return {
            "ok": False,
            "dataset": dataset,
            "schema": schema,
            "symbols": symbols if isinstance(symbols, str) else list(symbols),
            "start": iso(start),
            "end": iso(end),
            "error": f"{type(e).__name__}: {e}",
        }


def window(days: int) -> tuple[date, date]:
    end = ASOF
    start = ASOF - timedelta(days=days)
    return start, end


def main() -> int:
    results: list[dict[str, Any]] = []

    # Discover usable datasets/schemas (best-effort)
    print("Listing publishers / probing dataset ranges...\n")
    for ds in ["EQUS.MINI", "XNAS.ITCH", "XNAS.BASIC", "EQUS.SUMMARY", "OPRA.PILLAR"]:
        try:
            r = client.metadata.get_dataset_range(dataset=ds)
            print(f"  {ds}: available {r}")
            results.append({"probe": "dataset_range", "dataset": ds, "range": str(r), "ok": True})
        except Exception as e:
            print(f"  {ds}: FAIL {e}")
            results.append({"probe": "dataset_range", "dataset": ds, "ok": False, "error": str(e)})

    print("\n=== COST MATRIX (get_cost only) ===\n")

    # --- Tier 1: microstructure for top names ---
    scenarios = [
        # EQUS.MINI L1 — primary budget path
        ("T1a_mini_tbbo_tierA_90d", "EQUS.MINI", "tbbo", TIER_A, 90),
        ("T1b_mini_trades_tierA_90d", "EQUS.MINI", "trades", TIER_A, 90),
        ("T1c_mini_mbp1_tierA_90d", "EQUS.MINI", "mbp-1", TIER_A, 90),
        ("T1d_mini_tbbo_tierA_30d", "EQUS.MINI", "tbbo", TIER_A, 30),
        ("T1e_mini_tbbo_tierA_180d", "EQUS.MINI", "tbbo", TIER_A, 180),
        ("T1f_mini_tbbo_tierAB_90d", "EQUS.MINI", "tbbo", TIER_A + TIER_B, 90),
        ("T1g_mini_tbbo_all_eq_30d", "EQUS.MINI", "tbbo", ALL_EQ, 30),
        # XNAS.ITCH deeper
        ("T1h_itch_tbbo_tierA_30d", "XNAS.ITCH", "tbbo", TIER_A, 30),
        ("T1i_itch_trades_tierA_30d", "XNAS.ITCH", "trades", TIER_A, 30),
        ("T1j_itch_mbp1_tierA_30d", "XNAS.ITCH", "mbp-1", TIER_A, 30),
        ("T1k_itch_mbp10_tierA_7d", "XNAS.ITCH", "mbp-10", TIER_A, 7),
        ("T1l_itch_mbo_NVDA_3d", "XNAS.ITCH", "mbo", ["NVDA"], 3),
        # Second bars
        ("T3a_mini_ohlcv1s_tierA_30d", "EQUS.MINI", "ohlcv-1s", TIER_A, 30),
        ("T3b_mini_ohlcv1s_tierA_90d", "EQUS.MINI", "ohlcv-1s", TIER_A, 90),
        ("T3c_mini_ohlcv1m_tierA_365d", "EQUS.MINI", "ohlcv-1m", TIER_A, 365),
        # Imbalance
        ("T2a_itch_imbalance_tierA_180d", "XNAS.ITCH", "imbalance", TIER_A, 180),
        ("T2b_itch_imbalance_tierA_365d", "XNAS.ITCH", "imbalance", TIER_A, 365),
        # XNAS.BASIC for TRF-inclusive trades
        ("T1m_basic_trades_tierA_30d", "XNAS.BASIC", "trades", TIER_A, 30),
        ("T1n_basic_tbbo_tierA_30d", "XNAS.BASIC", "tbbo", TIER_A, 30),
        # Options OPRA — careful
        ("T4a_opra_def_underlyings_7d", "OPRA.PILLAR", "definition", TIER_A, 7),
        ("T4b_opra_trades_AAPL_7d", "OPRA.PILLAR", "trades", ["AAPL"], 7),
        ("T4c_opra_trades_NVDA_7d", "OPRA.PILLAR", "trades", ["NVDA"], 7),
        ("T4d_opra_trades_SPY_7d", "OPRA.PILLAR", "trades", ["SPY"], 7),
        ("T4e_opra_mbp1_NVDA_3d", "OPRA.PILLAR", "mbp-1", ["NVDA"], 3),
        ("T4f_opra_ohlcv1m_tierA_7d", "OPRA.PILLAR", "ohlcv-1m", TIER_A, 7),
    ]

    # Parent symbology variants for options (if raw fails)
    opra_parent_try = [
        ("T4g_opra_trades_parent_NVDA_7d", "OPRA.PILLAR", "trades", "NVDA.OPT", 7, "parent"),
        ("T4h_opra_trades_parent_SPY_7d", "OPRA.PILLAR", "trades", "SPY.OPT", 7, "parent"),
    ]

    for name, dataset, schema, symbols, days in scenarios:
        start, end = window(days)
        print(f"quoting {name} ...", flush=True)
        row = cost(dataset, schema, symbols, start, end)
        row["id"] = name
        row["lookback_days"] = days
        results.append(row)
        if row.get("ok"):
            print(f"  → ${row['cost_usd']:.4f}")
        else:
            print(f"  → ERR {row.get('error')}")

    for name, dataset, schema, symbols, days, stype in opra_parent_try:
        start, end = window(days)
        print(f"quoting {name} (stype={stype}) ...", flush=True)
        row = cost(dataset, schema, symbols, start, end, stype_in=stype)
        row["id"] = name
        row["lookback_days"] = days
        row["stype_in"] = stype
        results.append(row)
        if row.get("ok"):
            print(f"  → ${row['cost_usd']:.4f}")
        else:
            print(f"  → ERR {row.get('error')}")

    # Bundle recommendations: cumulative cost of best path
    ok_costs = {
        r["id"]: r["cost_usd"]
        for r in results
        if r.get("ok") and "id" in r and "cost_usd" in r
    }

    # Proposed packages
    packages = {
        "package_A_micro_core": [
            "T1d_mini_tbbo_tierA_30d",
            "T3a_mini_ohlcv1s_tierA_30d",
            "T2a_itch_imbalance_tierA_180d",
        ],
        "package_B_micro_90d": [
            "T1a_mini_tbbo_tierA_90d",
            "T3b_mini_ohlcv1s_tierA_90d",
            "T2a_itch_imbalance_tierA_180d",
        ],
        "package_C_plus_options_week": [
            "T1d_mini_tbbo_tierA_30d",
            "T3a_mini_ohlcv1s_tierA_30d",
            "T2a_itch_imbalance_tierA_180d",
            "T4c_opra_trades_NVDA_7d",
            "T4d_opra_trades_SPY_7d",
        ],
    }

    package_totals: dict[str, Any] = {}
    for pkg, ids in packages.items():
        total = 0.0
        missing = []
        parts = []
        for i in ids:
            if i in ok_costs:
                total += ok_costs[i]
                parts.append({"id": i, "cost_usd": ok_costs[i]})
            else:
                missing.append(i)
        package_totals[pkg] = {
            "total_usd": total,
            "within_125": total <= 125.0,
            "parts": parts,
            "missing_or_failed": missing,
            "headroom_usd": 125.0 - total,
        }

    summary = {
        "as_of": iso(ASOF),
        "budget_usd": 125.0,
        "note": "Quotes only via metadata.get_cost — no data downloaded",
        "quotes": [r for r in results if "id" in r],
        "probes": [r for r in results if "probe" in r],
        "packages": package_totals,
        "ok_costs": ok_costs,
    }

    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print("PACKAGE TOTALS (sum of independent get_cost quotes)")
    print("=" * 70)
    for pkg, info in package_totals.items():
        flag = "OK" if info["within_125"] else "OVER"
        print(f"  [{flag}] {pkg}: ${info['total_usd']:.4f}  headroom=${info['headroom_usd']:.4f}")
        if info["missing_or_failed"]:
            print(f"         missing: {info['missing_or_failed']}")

    print(f"\nSaved: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
