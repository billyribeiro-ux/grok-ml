#!/usr/bin/env python3
"""
Databento bulletproof purchase — NEW KEY.

Rules (non-negotiable):
1. Hard budget $120 (buffer $5 under typical $125 credits)
2. Re-quote every item immediately before download
3. Write ONLY to /Volumes/LaCie/Aether/data/raw/databento/purchased_v2/
4. Count spend ONLY after file exists and size >= min_bytes
5. NEVER delete any databento files
6. Stop permanently if cumulative would exceed budget
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
load_dotenv(ROOT / ".env", override=True)

KEY = os.getenv("DATABENTO_API_KEY")
if not KEY:
    raise SystemExit("DATABENTO_API_KEY missing")

import databento as db

ASOF = date(2026, 7, 10)
HARD_BUDGET = 120.0  # never exceed; $5 buffer under $125

LACIE = Path("/Volumes/LaCie/Aether")
if not LACIE.exists():
    raise SystemExit("LaCie /Volumes/LaCie/Aether NOT mounted — abort, refuse to write local")

OUT = LACIE / "data" / "raw" / "databento" / "purchased_v2"
OUT.mkdir(parents=True, exist_ok=True)
LEDGER = LACIE / "data" / "raw" / "databento" / "ledger_v2.json"
PLAN = LACIE / "data" / "raw" / "databento" / "purchase_plan_newkey.json"

TIER_A = ["NVDA", "TSLA", "AAPL", "SPY", "QQQ"]
TIER_B = ["AMZN", "NFLX", "IWM", "CSCO"]
INV = ["AAPD", "NVDD", "TSLS", "AMZD", "NFXS", "CSCS", "SH", "PSQ", "RWM", "SQQQ", "SPXU", "TZA"]
ALL = TIER_A + TIER_B + INV

# Best-of-best cart (from quotes) — order is download priority
CART = [
    {
        "name": "mini_tbbo_all_365",
        "dataset": "EQUS.MINI",
        "schema": "tbbo",
        "symbols": ALL,
        "days": 365,
        "stype_in": "raw_symbol",
        "min_bytes": 50_000_000,
        "why": "Full-universe trade+BBO 1y — primary microstructure",
    },
    {
        "name": "mini_ohlcv1s_all_180",
        "dataset": "EQUS.MINI",
        "schema": "ohlcv-1s",
        "symbols": ALL,
        "days": 180,
        "stype_in": "raw_symbol",
        "min_bytes": 10_000_000,
        "why": "1-second bars FMP lacks",
    },
    {
        "name": "itch_imbalance_all_365",
        "dataset": "XNAS.ITCH",
        "schema": "imbalance",
        "symbols": ALL,
        "days": 365,
        "stype_in": "raw_symbol",
        "min_bytes": 1_000_000,
        "why": "Open/close auction imbalance",
    },
    {
        "name": "basic_trades_tierA_30",
        "dataset": "XNAS.BASIC",
        "schema": "trades",
        "symbols": TIER_A,
        "days": 30,
        "stype_in": "raw_symbol",
        "min_bytes": 50_000_000,
        "why": "TRF-inclusive off-exchange volume",
    },
    {
        "name": "opra_ohlcv1m_5u_1d",
        "dataset": "OPRA.PILLAR",
        "schema": "ohlcv-1m",
        "symbols": ["NVDA.OPT", "TSLA.OPT", "AAPL.OPT", "QQQ.OPT", "SPY.OPT"],
        "days": 1,
        "stype_in": "parent",
        "min_bytes": 1_000_000,
        "why": "Options surface sample 5 underlyings",
    },
    {
        "name": "opra_trades_nvda_3d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "NVDA.OPT",
        "days": 3,
        "stype_in": "parent",
        "min_bytes": 1_000_000,
        "why": "NVDA options print tape 3d",
    },
    {
        "name": "opra_trades_aapl_3d",
        "dataset": "OPRA.PILLAR",
        "schema": "trades",
        "symbols": "AAPL.OPT",
        "days": 3,
        "stype_in": "parent",
        "min_bytes": 500_000,
        "why": "AAPL options print tape 3d",
    },
    {
        "name": "mini_mbp1_tierA_7",
        "dataset": "EQUS.MINI",
        "schema": "mbp-1",
        "symbols": TIER_A,
        "days": 7,
        "stype_in": "raw_symbol",
        "min_bytes": 20_000_000,
        "why": "BBO quote stream 7d top names",
    },
    {
        "name": "itch_mbo_nvda_tsla_3",
        "dataset": "XNAS.ITCH",
        "schema": "mbo",
        "symbols": ["NVDA", "TSLA"],
        "days": 3,
        "stype_in": "raw_symbol",
        "min_bytes": 50_000_000,
        "why": "Full L3 book NVDA+TSLA 3d",
    },
    {
        "name": "mini_tbbo_iwm_proxy_90",
        "dataset": "EQUS.MINI",
        "schema": "tbbo",
        "symbols": ["IWM", "RWM", "TZA"],
        "days": 90,
        "stype_in": "raw_symbol",
        "min_bytes": 1_000_000,
        "why": "Small-cap complex tape",
    },
]


def load_ledger() -> dict[str, Any]:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {
        "hard_budget_usd": HARD_BUDGET,
        "spent_usd": 0.0,
        "items": [],
        "key_prefix": KEY[:6] if KEY else None,
    }


def save_ledger(ledger: dict[str, Any]) -> None:
    ledger["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ledger["headroom_usd"] = HARD_BUDGET - float(ledger.get("spent_usd", 0))
    LEDGER.write_text(json.dumps(ledger, indent=2))


def main() -> int:
    client = db.Historical(KEY)
    ledger = load_ledger()
    spent = float(ledger.get("spent_usd", 0.0))
    done_names = {i.get("name") for i in ledger.get("items", []) if i.get("status") == "downloaded"}

    print("=" * 70, flush=True)
    print("DATABENTO BULLETPROOF v2 — NEW KEY", flush=True)
    print(f"OUT={OUT}", flush=True)
    print(f"HARD_BUDGET=${HARD_BUDGET}  already_spent=${spent:.4f}", flush=True)
    print("=" * 70, flush=True)

    for item in CART:
        name = item["name"]
        if name in done_names:
            print(f"\nSKIP already downloaded: {name}", flush=True)
            continue

        dest = OUT / name
        dest.mkdir(parents=True, exist_ok=True)
        dbn_path = dest / f"{name}.dbn.zst"

        # resume if file already complete
        if dbn_path.exists() and dbn_path.stat().st_size >= item["min_bytes"]:
            print(f"\nSKIP file exists: {name} ({dbn_path.stat().st_size} bytes)", flush=True)
            # if not in ledger, don't re-charge — mark present only
            ledger["items"].append(
                {
                    "name": name,
                    "status": "already_on_disk",
                    "path": str(dbn_path),
                    "bytes": dbn_path.stat().st_size,
                    "note": "not re-downloaded",
                }
            )
            save_ledger(ledger)
            continue

        start = ASOF - timedelta(days=item["days"])
        print(f"\n>>> RE-QUOTE {name}", flush=True)
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
            print(f"  QUOTE FAIL: {e}", flush=True)
            ledger["items"].append({"name": name, "status": "quote_failed", "error": str(e)})
            save_ledger(ledger)
            continue

        print(f"  cost=${cost:.4f}  spent=${spent:.4f}  would=${spent+cost:.4f}", flush=True)
        if spent + cost > HARD_BUDGET + 1e-9:
            print(f"  STOP — would exceed hard budget ${HARD_BUDGET}", flush=True)
            ledger["items"].append(
                {
                    "name": name,
                    "status": "skipped_over_budget",
                    "quoted_cost": cost,
                    "spent_before": spent,
                }
            )
            save_ledger(ledger)
            break

        print(f"  DOWNLOAD → {dbn_path}", flush=True)
        t0 = time.time()
        # In-progress marker so path is known even mid-stream
        (dest / "IN_PROGRESS.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "path": str(dbn_path),
                    "quoted_cost": cost,
                    "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "status": "downloading",
                },
                indent=2,
            )
        )
        ledger["items"].append(
            {
                "name": name,
                "status": "downloading",
                "quoted_cost": cost,
                "path": str(dbn_path),
                "spent_before": spent,
            }
        )
        save_ledger(ledger)
        try:
            client.timeseries.get_range(
                dataset=item["dataset"],
                schema=item["schema"],
                symbols=item["symbols"],
                start=start.isoformat(),
                end=ASOF.isoformat(),
                stype_in=item["stype_in"],
                path=str(dbn_path),
            )
        except Exception as e:
            print(f"  DOWNLOAD EXCEPTION: {e}", flush=True)
            traceback.print_exc()
            # verify if partial file exists — do NOT count as success
            sz = dbn_path.stat().st_size if dbn_path.exists() else 0
            ledger["items"].append(
                {
                    "name": name,
                    "status": "download_failed",
                    "quoted_cost": cost,
                    "error": str(e),
                    "partial_bytes": sz,
                    "note": "NOT counted toward spent — check portal for any charge",
                }
            )
            save_ledger(ledger)
            # if exception after stream, portal may still charge — stop to be safe
            print("  ABORT remaining cart after failure (protect budget)", flush=True)
            break

        # VERIFY on disk
        if not dbn_path.exists():
            print("  VERIFY FAIL: file missing after get_range", flush=True)
            ledger["items"].append(
                {
                    "name": name,
                    "status": "verify_missing",
                    "quoted_cost": cost,
                    "note": "NOT counted — check portal",
                }
            )
            save_ledger(ledger)
            print("  ABORT remaining", flush=True)
            break

        sz = dbn_path.stat().st_size
        if sz < item["min_bytes"]:
            print(f"  VERIFY FAIL: size {sz} < min {item['min_bytes']}", flush=True)
            ledger["items"].append(
                {
                    "name": name,
                    "status": "verify_too_small",
                    "quoted_cost": cost,
                    "bytes": sz,
                    "note": "NOT counted as success — inspect file; portal may have charged",
                }
            )
            save_ledger(ledger)
            print("  ABORT remaining", flush=True)
            break

        # SUCCESS — count spend
        spent += cost
        meta = {
            "name": name,
            "dataset": item["dataset"],
            "schema": item["schema"],
            "symbols": item["symbols"] if isinstance(item["symbols"], str) else list(item["symbols"]),
            "stype_in": item["stype_in"],
            "start": start.isoformat(),
            "end": ASOF.isoformat(),
            "quoted_cost_usd": cost,
            "bytes": sz,
            "path": str(dbn_path),
            "elapsed_s": round(time.time() - t0, 2),
            "why": item["why"],
            "status": "downloaded",
            "cumulative_spent_usd": spent,
        }
        (dest / "meta.json").write_text(json.dumps(meta, indent=2))
        ledger["spent_usd"] = spent
        ledger["items"].append(meta)
        save_ledger(ledger)
        print(f"  OK verified {sz} bytes  spent_total=${spent:.4f}  headroom=${HARD_BUDGET-spent:.4f}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print(f"DONE spent=${spent:.4f} / ${HARD_BUDGET}  headroom=${HARD_BUDGET-spent:.4f}", flush=True)
    print(f"Ledger: {LEDGER}", flush=True)
    print(f"Data:   {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
