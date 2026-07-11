#!/usr/bin/env python3
"""
Aether — Databento purchase within hard $125 budget.

1) Re-quote each line item with metadata.get_cost
2) Download only if cumulative cost <= BUDGET
3) Save DBN + optional parquet conversion where practical
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

KEY = os.getenv("DATABENTO_API_KEY")
if not KEY:
    raise SystemExit("DATABENTO_API_KEY missing")

import databento as db

ASOF = date(2026, 7, 10)
BUDGET = 125.0
OUT = ROOT / "data" / "databento" / "purchased"
OUT.mkdir(parents=True, exist_ok=True)

TIER_A = ["NVDA", "TSLA", "AAPL", "SPY", "QQQ"]
TIER_B = ["AMZN", "NFLX", "IWM", "CSCO"]
INV = ["AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA"]
ALL = TIER_A + TIER_B + INV

# Max-utility cart (ordered). Re-quoted at runtime; skip if would exceed budget.
CART: list[dict[str, Any]] = [
    {
        "name": "mini_tbbo_all_365",
        "dataset": "EQUS.MINI",
        "schema": "tbbo",
        "symbols": ALL,
        "days": 365,
        "stype_in": "raw_symbol",
        "why": "Full-universe trade+BBO tape — primary microstructure for all longs+inverses",
    },
    {
        "name": "mini_ohlcv1s_all_180",
        "dataset": "EQUS.MINI",
        "schema": "ohlcv-1s",
        "symbols": ALL,
        "days": 180,
        "stype_in": "raw_symbol",
        "why": "1-second bars FMP cannot provide — high-res reversal timing",
    },
    {
        "name": "itch_imbalance_all_365",
        "dataset": "XNAS.ITCH",
        "schema": "imbalance",
        "symbols": ALL,
        "days": 365,
        "stype_in": "raw_symbol",
        "why": "Open/close auction imbalance — day-trade top/bottom DNA",
    },
    {
        "name": "mini_mbp1_tierA_30",
        "dataset": "EQUS.MINI",
        "schema": "mbp-1",
        "symbols": TIER_A,
        "days": 30,
        "stype_in": "raw_symbol",
        "why": "Continuous BBO dynamics on most liquid names — spread/liquidity decode",
    },
    {
        "name": "itch_mbp10_top3_14",
        "dataset": "XNAS.ITCH",
        "schema": "mbp-10",
        "symbols": ["NVDA", "TSLA", "SPY"],
        "days": 14,
        "stype_in": "raw_symbol",
        "why": "L2 depth sample for book pressure at turns",
    },
    {
        "name": "itch_mbo_nvda_3",
        "dataset": "XNAS.ITCH",
        "schema": "mbo",
        "symbols": ["NVDA"],
        "days": 3,
        "stype_in": "raw_symbol",
        "why": "Full L3 order book sample — queue/cancel intelligence on flagship name",
    },
    {
        "name": "opra_ohlcv1m_nvda_qqq_tsla_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "ohlcv-1m",
        "symbols": ["NVDA.OPT", "QQQ.OPT", "TSLA.OPT"],
        "days": 1,
        "stype_in": "parent",
        "why": "Options surface minute bars for gamma/flow regime sample",
    },
    {
        "name": "opra_trades_nvda_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "NVDA.OPT",
        "days": 1,
        "stype_in": "parent",
        "why": "Full options print tape NVDA — unusual activity decode",
    },
    {
        "name": "opra_trades_tsla_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "TSLA.OPT",
        "days": 1,
        "stype_in": "parent",
        "why": "Full options print tape TSLA",
    },
    {
        "name": "opra_trades_aapl_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "AAPL.OPT",
        "days": 1,
        "stype_in": "parent",
        "why": "Full options print tape AAPL",
    },
    {
        "name": "basic_trades_tierA_14",
        "dataset": "XNAS.BASIC",
        "schema": "trades",
        "symbols": TIER_A,
        "days": 14,
        "stype_in": "raw_symbol",
        "why": "TRF-inclusive trades (off-exchange volume) sample",
    },
    {
        "name": "mini_trades_all_90",
        "dataset": "EQUS.MINI",
        "schema": "trades",
        "symbols": ALL,
        "days": 90,
        "stype_in": "raw_symbol",
        "why": "Extra trade-only tape if budget remains (tbbo already primary)",
    },
]


def main() -> int:
    client = db.Historical(KEY)
    ledger: list[dict[str, Any]] = []
    spent = 0.0

    print(f"BUDGET ${BUDGET:.2f}  ASOF {ASOF}")
    print("=" * 72)

    for item in CART:
        name = item["name"]
        start = ASOF - timedelta(days=item["days"])
        end = ASOF
        symbols = item["symbols"]
        stype = item["stype_in"]

        print(f"\n>>> QUOTE {name}")
        try:
            cost = float(
                client.metadata.get_cost(
                    dataset=item["dataset"],
                    schema=item["schema"],
                    symbols=symbols,
                    start=start.isoformat(),
                    end=end.isoformat(),
                    stype_in=stype,
                )
            )
        except Exception as e:
            print(f"  QUOTE FAIL: {e}")
            ledger.append({**item, "status": "quote_failed", "error": str(e)})
            continue

        print(f"  cost=${cost:.4f}  spent_so_far=${spent:.4f}  headroom=${BUDGET - spent:.4f}")
        if spent + cost > BUDGET + 1e-9:
            print(f"  SKIP — would exceed budget (${spent + cost:.4f} > ${BUDGET:.2f})")
            ledger.append({**item, "status": "skipped_over_budget", "quoted_cost": cost, "spent_before": spent})
            continue

        dest_dir = OUT / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        print(f"  DOWNLOAD → {dest_dir}")
        t0 = time.time()
        try:
            # Streaming historical pull; billed on use
            store = client.timeseries.get_range(
                dataset=item["dataset"],
                schema=item["schema"],
                symbols=symbols,
                start=start.isoformat(),
                end=end.isoformat(),
                stype_in=stype,
                path=str(dest_dir / f"{name}.dbn.zst"),
            )
            # store may be a DBNStore when path is set
            meta = {
                "name": name,
                "dataset": item["dataset"],
                "schema": item["schema"],
                "symbols": symbols if isinstance(symbols, str) else list(symbols),
                "stype_in": stype,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "quoted_cost_usd": cost,
                "why": item["why"],
                "path": str(dest_dir / f"{name}.dbn.zst"),
                "elapsed_s": round(time.time() - t0, 2),
            }
            # Try lightweight row count / to parquet sample if not enormous
            try:
                if hasattr(store, "to_df"):
                    # Only convert smaller schemas fully; large ones leave as DBN
                    heavy = item["schema"] in {"mbp-1", "mbp-10", "mbo", "trades", "tbbo"} and item["days"] >= 30
                    if not heavy:
                        df = store.to_df()
                        pq = dest_dir / f"{name}.parquet"
                        df.to_parquet(pq)
                        meta["rows"] = int(len(df))
                        meta["parquet"] = str(pq)
                    else:
                        meta["note"] = "left as DBN (heavy schema); convert later as needed"
                elif isinstance(store, db.DBNStore):
                    meta["dbn_store"] = True
            except Exception as conv_e:
                meta["convert_warning"] = str(conv_e)

            spent += cost
            meta["status"] = "downloaded"
            meta["cumulative_spent_usd"] = spent
            ledger.append(meta)
            (dest_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            print(f"  OK  elapsed={meta['elapsed_s']}s  cumulative_spent=${spent:.4f}")
        except Exception as e:
            print(f"  DOWNLOAD FAIL: {e}")
            traceback.print_exc()
            ledger.append(
                {
                    **item,
                    "status": "download_failed",
                    "quoted_cost": cost,
                    "error": str(e),
                    "spent_before": spent,
                }
            )
            # Do not add failed cost to spent (Databento typically charges on successful delivery;
            # if partial charge occurs, user should check portal. We keep conservative spent tracking
            # on quoted success path only for completed downloads.)
            continue

        # persist ledger after each success
        summary = {
            "budget_usd": BUDGET,
            "spent_usd": spent,
            "headroom_usd": BUDGET - spent,
            "as_of": ASOF.isoformat(),
            "items": ledger,
        }
        (OUT.parent / "purchase_ledger.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print(f"DONE  spent=${spent:.4f} / ${BUDGET:.2f}  headroom=${BUDGET - spent:.4f}")
    print(f"Ledger: {OUT.parent / 'purchase_ledger.json'}")
    print(f"Data:   {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
