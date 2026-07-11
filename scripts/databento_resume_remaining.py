#!/usr/bin/env python3
"""
Resume Databento cart on LaCie — only remaining items under $125 total spent.

Already downloaded (~$67.58):
  mini_tbbo_all_365, mini_ohlcv1s_all_180, itch_imbalance_all_365, mini_mbp1_tierA_30
Incomplete/skipped: itch_mbp10 (partial — DO NOT re-buy), rest of cart.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

KEY = os.getenv("DATABENTO_API_KEY")
if not KEY:
    raise SystemExit("DATABENTO_API_KEY missing")

import databento as db

ASOF = date(2026, 7, 10)
BUDGET = 125.0
ALREADY_SPENT = 67.579835772515  # from ledger completed items

OUT = Path(os.getenv("DATABENTO_DATA_DIR", str(ROOT / "data" / "databento")))
PURCHASED = OUT / "purchased"
PURCHASED.mkdir(parents=True, exist_ok=True)
LEDGER = OUT / "purchase_ledger_resume.json"

TIER_A = ["NVDA", "TSLA", "AAPL", "SPY", "QQQ"]
ALL = TIER_A + ["AMZN", "NFLX", "IWM", "CSCO", "AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA"]

# Remaining cart only — skip mbp-10 re-download (partial already billed risk)
CART = [
    {
        "name": "itch_mbo_nvda_3",
        "dataset": "XNAS.ITCH",
        "schema": "mbo",
        "symbols": ["NVDA"],
        "days": 3,
        "stype_in": "raw_symbol",
    },
    {
        "name": "opra_ohlcv1m_nvda_qqq_tsla_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "ohlcv-1m",
        "symbols": ["NVDA.OPT", "QQQ.OPT", "TSLA.OPT"],
        "days": 1,
        "stype_in": "parent",
    },
    {
        "name": "opra_trades_nvda_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "NVDA.OPT",
        "days": 1,
        "stype_in": "parent",
    },
    {
        "name": "opra_trades_tsla_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "TSLA.OPT",
        "days": 1,
        "stype_in": "parent",
    },
    {
        "name": "opra_trades_aapl_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "AAPL.OPT",
        "days": 1,
        "stype_in": "parent",
    },
    {
        "name": "basic_trades_tierA_14",
        "dataset": "XNAS.BASIC",
        "schema": "trades",
        "symbols": TIER_A,
        "days": 14,
        "stype_in": "raw_symbol",
    },
    {
        "name": "mini_trades_all_90",
        "dataset": "EQUS.MINI",
        "schema": "trades",
        "symbols": ALL,
        "days": 90,
        "stype_in": "raw_symbol",
    },
    {
        "name": "itch_tbbo_tierA_30",
        "dataset": "XNAS.ITCH",
        "schema": "tbbo",
        "symbols": TIER_A,
        "days": 30,
        "stype_in": "raw_symbol",
    },
]


def main() -> int:
    client = db.Historical(KEY)
    spent = ALREADY_SPENT
    ledger = {
        "budget_usd": BUDGET,
        "already_spent_usd": ALREADY_SPENT,
        "spent_usd": spent,
        "as_of": ASOF.isoformat(),
        "out": str(PURCHASED),
        "items": [],
    }
    print(f"Resume on {PURCHASED}", flush=True)
    print(f"Budget ${BUDGET} already_spent ${spent:.4f} headroom ${BUDGET-spent:.4f}", flush=True)

    for item in CART:
        name = item["name"]
        dest = PURCHASED / name
        dbn = dest / f"{name}.dbn.zst"
        if dbn.exists() and dbn.stat().st_size > 1_000_000:
            print(f"SKIP exists {name} ({dbn.stat().st_size} bytes)", flush=True)
            continue

        start = ASOF - timedelta(days=item["days"])
        print(f"\n>>> QUOTE {name}", flush=True)
        try:
            cost = float(
                client.metadata.get_cost(
                    dataset=item["dataset"],
                    schema=item["schema"],
                    symbols=item["symbols"],
                    start=start.isoformat(),
                    end=ASOF.isoformat(),
                    stype_in=item["stype_in"],
                )
            )
        except Exception as e:
            print(f"  quote fail: {e}", flush=True)
            ledger["items"].append({**item, "status": "quote_failed", "error": str(e)})
            continue

        print(f"  cost=${cost:.4f} would_total=${spent+cost:.4f}", flush=True)
        if spent + cost > BUDGET:
            print("  SKIP over budget", flush=True)
            ledger["items"].append({**item, "status": "skipped_over_budget", "quoted_cost": cost})
            continue

        dest.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            print(f"  DOWNLOAD...", flush=True)
            store = client.timeseries.get_range(
                dataset=item["dataset"],
                schema=item["schema"],
                symbols=item["symbols"],
                start=start.isoformat(),
                end=ASOF.isoformat(),
                stype_in=item["stype_in"],
                path=str(dbn),
            )
            spent += cost
            meta = {
                **{k: item[k] for k in item},
                "symbols": item["symbols"] if isinstance(item["symbols"], str) else list(item["symbols"]),
                "start": start.isoformat(),
                "end": ASOF.isoformat(),
                "quoted_cost_usd": cost,
                "path": str(dbn),
                "elapsed_s": round(time.time() - t0, 2),
                "status": "downloaded",
                "cumulative_spent_usd": spent,
            }
            # light convert for small schemas
            try:
                if item["schema"] in {"ohlcv-1m", "ohlcv-1s", "imbalance"} and hasattr(store, "to_df"):
                    df = store.to_df()
                    pq = dest / f"{name}.parquet"
                    df.to_parquet(pq)
                    meta["rows"] = len(df)
                    meta["parquet"] = str(pq)
            except Exception as ce:
                meta["convert_warning"] = str(ce)

            (dest / "meta.json").write_text(json.dumps(meta, indent=2))
            ledger["items"].append(meta)
            ledger["spent_usd"] = spent
            ledger["headroom_usd"] = BUDGET - spent
            LEDGER.write_text(json.dumps(ledger, indent=2))
            print(f"  OK ${cost:.4f} total=${spent:.4f}", flush=True)
        except Exception as e:
            print(f"  FAIL {e}", flush=True)
            traceback.print_exc()
            ledger["items"].append({**item, "status": "download_failed", "quoted_cost": cost, "error": str(e)})
            LEDGER.write_text(json.dumps(ledger, indent=2))

    ledger["spent_usd"] = spent
    ledger["headroom_usd"] = BUDGET - spent
    LEDGER.write_text(json.dumps(ledger, indent=2))
    print(f"\nDONE total_spent~${spent:.4f} headroom=${BUDGET-spent:.4f}", flush=True)
    print(f"Ledger {LEDGER}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
