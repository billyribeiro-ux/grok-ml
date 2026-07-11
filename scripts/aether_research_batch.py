#!/usr/bin/env python3
"""Reusable offline research batch — one eod panel load, no mission promote.

Examples:
  .venv/bin/python scripts/aether_research_batch.py --universe hybrid_plus_mega
  .venv/bin/python scripts/aether_research_batch.py --universe hybrid_sector_mission --conf 0.58 --pos 3
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))


def main() -> None:
    p = argparse.ArgumentParser(description="Aether research batch (promote_latest=False)")
    p.add_argument("--universe", default="hybrid_plus_mega")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2026-07-10")
    p.add_argument("--conf", type=float, nargs="+", default=[0.55, 0.58])
    p.add_argument("--pos", type=int, nargs="+", default=[3, 5])
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--multifold-best", type=int, default=2, help="walkforward top N by single-cut sharpe")
    args = p.parse_args()

    from aether.engine.data_source import PanelFrameSource
    from aether.engine.lacie_source import LacieEodBulkSource
    from aether.engine.pipeline import run_offline_pipeline
    from aether.engine.risk import RiskConfig
    from aether.engine.universe import all_named
    from aether.engine.walkforward import report_to_dict, run_walkforward

    u = all_named().get(args.universe)
    if not u:
        raise SystemExit(f"unknown universe {args.universe}; have {list(all_named())}")
    syms = list(u.symbols)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    res = Path("/Volumes/LaCie/Aether/data/processed/research")
    res.mkdir(parents=True, exist_ok=True)

    print(f"load {args.universe} n={len(syms)} {start}→{end}", flush=True)
    raw = LacieEodBulkSource(symbols=syms).panel(start=start, end=end)
    src = PanelFrameSource(raw)
    print(f"panel rows={len(raw)}", flush=True)

    rows: list[dict] = []
    for conf in args.conf:
        for pos in args.pos:
            name = f"{args.universe}_c{int(round(conf * 100)):02d}_p{pos}"
            print(f"FLIGHT {name}", flush=True)
            r = run_offline_pipeline(
                source=src,
                symbols=syms,
                start=start,
                end=end,
                train_frac=0.7,
                purge_days=5,
                label_col="y_up_5d",
                flight_name=name,
                promote_latest=False,
                risk=RiskConfig(max_positions=pos, min_confidence=conf),
            )
            st = r.backtest.stats
            row = {
                "name": name,
                "universe": args.universe,
                "min_confidence": conf,
                "max_positions": pos,
                "total_return": st.get("total_return"),
                "sharpe_like": st.get("sharpe_like"),
                "max_drawdown": st.get("max_drawdown"),
                "final_equity_usd": st.get("final_equity_usd"),
                "n_fills": st.get("n_fills"),
                "brier": r.calibration.get("brier"),
            }
            rows.append(row)
            print(
                f"  ret={row['total_return']:+.3f} sh={row['sharpe_like']:+.3f} "
                f"dd={row['max_drawdown']:.3f}",
                flush=True,
            )

    top = sorted(rows, key=lambda r: -(r.get("sharpe_like") or -9))[: max(1, args.multifold_best)]
    for t in top:
        conf, pos = float(t["min_confidence"]), int(t["max_positions"])
        print(f"WF {t['name']}", flush=True)
        rep = run_walkforward(
            raw,
            n_folds=args.folds,
            min_train_frac=0.55,
            purge_days=5,
            label_col="y_up_5d",
            risk=RiskConfig(max_positions=pos, min_confidence=conf),
            symbols=syms,
        )
        d = report_to_dict(rep)
        d["kind"] = "walkforward"
        d["tag"] = t["name"]
        d["written_at"] = datetime.now(timezone.utc).isoformat()
        (res / f"latest_walkforward_{t['name']}.json").write_text(
            json.dumps(d, indent=2, default=str)
        )
        t["multifold"] = d["aggregate"]
        print(f"  {d['aggregate']}", flush=True)

    out = {
        "kind": "research_batch",
        "written_at": datetime.now(timezone.utc).isoformat(),
        "universe": args.universe,
        "window": f"{args.start}→{args.end}",
        "rows": rows,
        "top_multifold": top,
    }
    path = res / f"research_batch_{args.universe}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    (res / f"latest_research_batch_{args.universe}.json").write_text(
        json.dumps(out, indent=2, default=str)
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
