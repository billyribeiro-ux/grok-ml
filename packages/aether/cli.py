"""CLI entrypoints for F0/F1 + offline engine flight + status."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from aether.features.daily import build_daily_features
from aether.features.store import write_feature_frame
from aether.integrity import run_integrity
from aether.loaders.eod_bulk import load_core_panel_from_eod_bulk
from aether.paths import F1_CORE_SYMBOLS, FMP_RAW, LACIE_ROOT, PROCESSED, LaCieNotMountedError


def cmd_integrity(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Aether F0 LaCie integrity check")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args(argv)

    report = run_integrity(write=True)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("Aether F0 integrity")
        print(f"  LaCie mounted: {report.lacie_mounted} ({report.lacie_root})")
        print(
            f"  eod_bulk: {report.eod_bulk_files} days "
            f"[{report.eod_bulk_min} → {report.eod_bulk_max}] "
            f"friday={report.eod_bulk_has_friday}"
        )
        print(f"  eod_2026-07-10 meta: {report.eod_friday_meta}")
        print(f"  iwm eod files: {report.iwm_eod_files}")
        print(f"  sector 1day: {report.sector_etf_1day}")
        print(f"  databento zst: {report.databento_zst}")
        if report.warnings:
            print("  warnings:")
            for w in report.warnings:
                print(f"    - {w}")
        if report.errors:
            print("  errors:")
            for e in report.errors:
                print(f"    - {e}")
        print(f"  OK: {report.ok}")
    sys.exit(0 if report.ok else 1)


def cmd_f1_features(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Aether F1 daily feature build (core symbols)")
    parser.add_argument(
        "--symbols",
        default=",".join(F1_CORE_SYMBOLS),
        help="comma-separated symbols",
    )
    parser.add_argument("--start", default="2018-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default="2026-07-10", help="YYYY-MM-DD")
    parser.add_argument(
        "--name",
        default="daily_f1_core_v1",
        help="feature store dataset name",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=None,
        help="optional cap on number of eod-bulk days (debug)",
    )
    args = parser.parse_args(argv)

    try:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        print(f"F1 features: symbols={symbols} range={args.start}→{args.end}")
        print("Loading eod-bulk panel (one pass)…")
        panel = load_core_panel_from_eod_bulk(
            symbols,
            start=args.start,
            end=args.end,
            max_days=args.max_days,
        )
        print(f"  panel rows={len(panel)} symbols={panel['symbol'].nunique() if len(panel) else 0}")
        if panel.empty:
            print("ERROR: empty panel — check LaCie eod_bulk", file=sys.stderr)
            sys.exit(2)

        print("Building daily features (as-of safe)…")
        feats = build_daily_features(panel)
        usable = feats.dropna(subset=["ret_1d"])
        print(f"  feature rows={len(feats)} usable_with_ret1d={len(usable)}")

        path = write_feature_frame(feats, args.name)
        print(f"  wrote {path}")
        print("F1 OK")
        sys.exit(0)
    except LaCieNotMountedError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise


def cmd_engine_flight(argv: list[str] | None = None) -> None:
    """Engine flight: mock by default, --lacie for real eod-bulk."""
    parser = argparse.ArgumentParser(description="Aether engine flight")
    parser.add_argument("--symbols", default="SPY,QQQ,IWM,SQQQ,TZA,SH")
    parser.add_argument("--equity", type=float, default=100_000.0)
    parser.add_argument("--lacie", action="store_true", help="use LaCie eod-bulk source")
    parser.add_argument(
        "--start",
        default="2018-01-01",
        help="pin train/test calendar (default 2018-01-01→2026-07-10 so growing eod_bulk does not shift cuts)",
    )
    parser.add_argument("--end", default="2026-07-10")
    parser.add_argument("--train-frac", type=float, default=0.7)
    parser.add_argument("--purge-days", type=int, default=5, help="embargo dates before OOS cut")
    parser.add_argument("--label", default="y_up_5d")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--name", default="offline_flight")
    parser.add_argument(
        "--core",
        action="store_true",
        help=f"use full F1_CORE_SYMBOLS ({len(F1_CORE_SYMBOLS)} names)",
    )
    parser.add_argument("--universe", default=None, help="named universe override")
    parser.add_argument("--max-positions", type=int, default=None)
    parser.add_argument("--min-confidence", type=float, default=None)
    parser.add_argument(
        "--no-promote",
        action="store_true",
        help="write stamped telemetry only; do not overwrite mission latest_flight.json",
    )
    parser.add_argument(
        "--json-dir",
        default=None,
        help="per-symbol OHLCV json directory (liquid/bonds/etn) instead of eod_bulk",
    )
    args = parser.parse_args(argv)

    from datetime import date as date_cls

    from aether.engine.mock_data import MockDailySource
    from aether.engine.pipeline import run_offline_pipeline
    from aether.engine.risk import RiskConfig
    from aether.engine.universe import all_named

    if args.universe:
        u = all_named().get(args.universe)
        if not u:
            print(f"unknown universe {args.universe}", file=sys.stderr)
            sys.exit(2)
        symbols = list(u.symbols)
    elif args.core:
        symbols = list(F1_CORE_SYMBOLS)
    else:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    start = date_cls.fromisoformat(args.start) if args.start else None
    end = date_cls.fromisoformat(args.end) if args.end else None

    # Research default: max_positions=5 won risk sweeps (higher sharpe, fewer rejections)
    risk = RiskConfig(
        max_positions=args.max_positions if args.max_positions is not None else 5,
        min_confidence=args.min_confidence if args.min_confidence is not None else 0.55,
    )

    if args.json_dir:
        from aether.engine.json_source import JsonOhlcvDirSource

        src = JsonOhlcvDirSource(args.json_dir, symbols=symbols or None)
        symbols = src.symbols()
        source_name = f"JsonOhlcvDirSource({args.json_dir})"
        offline_tel = False
        name = args.name if args.name != "offline_flight" else "json_dir_flight"
    elif args.lacie:
        from aether.engine.lacie_source import LacieEodBulkSource

        src = LacieEodBulkSource(symbols=symbols)
        source_name = "LacieEodBulkSource"
        offline_tel = False
        name = args.name if args.name != "offline_flight" else "lacie_flight"
    else:
        src = MockDailySource(symbols=symbols)
        source_name = "MockDailySource"
        offline_tel = True
        name = args.name

    result = run_offline_pipeline(
        source=src,
        symbols=symbols,
        start=start,
        end=end,
        start_equity_usd=args.equity,
        train_frac=args.train_frac,
        purge_days=args.purge_days,
        label_col=args.label,
        offline_telemetry=offline_tel,
        flight_name=name,
        risk=risk,
        promote_latest=not args.no_promote,
    )
    stats = {
        **result.backtest.stats,
        "calibration_brier": result.calibration.get("brier"),
        "train_rows": result.train_rows,
        "test_rows": result.test_rows,
        "cut_date": str(result.cut_date),
        "telemetry": str(result.telemetry_path) if result.telemetry_path else None,
        "source": source_name,
    }
    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        print(f"Aether engine flight ({source_name})")
        print(f"  symbols: {symbols}")
        print(f"  feature rows: {len(result.features)}  train={result.train_rows} test={result.test_rows}")
        print(f"  cut: {result.cut_date}  purge_days={args.purge_days}  label={args.label}")
        print(f"  calibration Brier (test): {result.calibration.get('brier')}")
        if result.scorer is not None:
            top = result.scorer.coefficient_table()[:5]
            if top:
                print("  top weights:")
                for r in top:
                    print(f"    {r['feature']}: {r['weight']}")
        for k, v in result.backtest.stats.items():
            print(f"  {k}: {v}")
        if result.telemetry_path:
            print(f"  telemetry: {result.telemetry_path}")
        if source_name.startswith("Mock"):
            print("  note: MOCK data — plumbing + scorer only, not live edge.")
    sys.exit(0)


def _dir_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for p in path.rglob("*"):
        if p.is_file() and not p.name.startswith("._"):
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def _count_non_dot(path: Path, pattern: str = "*") -> int:
    if not path.is_dir():
        return 0
    return sum(1 for p in path.glob(pattern) if p.is_file() and not p.name.startswith("._"))


def cmd_status(argv: list[str] | None = None) -> None:
    """Live archive + telemetry status (honest inventory while downloads run)."""
    parser = argparse.ArgumentParser(description="Aether status while archives download")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from aether.paths import EOD_BULK, FEATURE_STORE

    payload: dict = {
        "lacie_mounted": LACIE_ROOT.exists(),
        "lacie_root": str(LACIE_ROOT),
        "checked_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "archives": {},
        "telemetry": {},
        "download_logs": {},
    }

    archives = {
        "eod_bulk": EOD_BULK,
        "nasdaq_full": FMP_RAW / "nasdaq_full",
        "inverses_full": FMP_RAW / "inverses_full",
        "liquid_10_700": FMP_RAW / "liquid_10_700",
        "liquid_ohlcv_eod": FMP_RAW / "liquid_10_700" / "ohlcv_eod",
        "etn": FMP_RAW / "etn",
        "etn_ohlcv_eod": FMP_RAW / "etn" / "ohlcv_eod",
        "bonds": FMP_RAW / "bonds",
        "bonds_ohlcv_eod": FMP_RAW / "bonds" / "ohlcv_eod",
        "sector_etfs": FMP_RAW / "sector_etfs",
        "iwm_russell2000": FMP_RAW / "iwm_russell2000",
        "bandwidth_burn": FMP_RAW / "bandwidth_burn",
        "market_internals": FMP_RAW / "market_internals",
    }
    for name, p in archives.items():
        files = 0
        if p.is_dir():
            # recursive count for ohlcv trees (json/csv/parquet)
            for pat in ("*.csv", "*.json", "*.parquet"):
                files += sum(
                    1
                    for f in p.rglob(pat)
                    if f.is_file() and not f.name.startswith("._")
                )
        n_dirs = (
            sum(1 for c in p.iterdir() if c.is_dir() and not c.name.startswith("._"))
            if p.is_dir()
            else 0
        )
        payload["archives"][name] = {
            "path": str(p),
            "exists": p.exists(),
            "files_approx": files,
            "subdirs": n_dirs,
            "mb": round(_dir_mb(p), 1) if p.exists() else 0.0,
        }

    tel = PROCESSED / "telemetry"
    latest = tel / "latest_flight.json"
    if latest.exists():
        try:
            d = json.loads(latest.read_text())
            series = d.get("series") or {}
            payload["telemetry"] = {
                "latest": str(latest),
                "name": d.get("name"),
                "written_at": d.get("written_at"),
                "source": d.get("source"),
                "symbols": d.get("symbols"),
                "stats": d.get("stats"),
                "has_series": bool(series),
                "n_equity": len(series.get("equity_curve") or []),
                "n_fills": len(series.get("fills") or []),
                "n_signals": len(series.get("signals") or []),
                "n_weights": len(series.get("feature_weights") or []),
            }
        except Exception as e:
            payload["telemetry"] = {"error": str(e)}
    flights = []
    if tel.is_dir():
        for p in sorted(tel.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.name.startswith("._") or p.name.startswith("latest"):
                continue
            flights.append({"name": p.name, "mb": round(p.stat().st_size / 1e6, 3), "mtime": p.stat().st_mtime})
    payload["telemetry"]["flights"] = flights[:12]

    fs = FEATURE_STORE
    if fs.is_dir():
        payload["feature_store"] = [
            {
                "name": d.name,
                "mb": round(_dir_mb(d), 2),
            }
            for d in sorted(fs.iterdir())
            if d.is_dir() and not d.name.startswith("._")
        ]

    log_dir = LACIE_ROOT / "logs"
    if log_dir.is_dir():
        for log in sorted(log_dir.glob("*.log")):
            if log.name.startswith("._"):
                continue
            try:
                lines = log.read_text(errors="replace").splitlines()
                tail = lines[-3:] if lines else []
                payload["download_logs"][log.name] = {
                    "lines": len(lines),
                    "tail": tail,
                    "mb": round(log.stat().st_size / 1e6, 3),
                }
            except OSError:
                pass

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print("AETHER STATUS")
        print(f"  LaCie: {payload['lacie_mounted']}  {payload['lacie_root']}")
        print("  Archives:")
        for k, v in payload["archives"].items():
            print(f"    {k:18} exists={v['exists']} files≈{v['files_approx']} dirs={v['subdirs']} mb={v['mb']}")
        t = payload.get("telemetry") or {}
        if t.get("name"):
            print(f"  Telemetry: {t.get('name')}  series={t.get('has_series')}  eq={t.get('n_equity')} fills={t.get('n_fills')}")
            print(f"    written {t.get('written_at')}  source={t.get('source')}")
        print(f"  Flight files: {len(t.get('flights') or [])}")
        print("  Recent log tails:")
        for name in ("fmp_bandwidth_burn.log", "fmp_nasdaq_and_inverses_full.log", "session_b_liquid_etn_bonds.log"):
            info = (payload.get("download_logs") or {}).get(name)
            if info:
                print(f"    [{name}]")
                for line in info.get("tail") or []:
                    print(f"      {line}")
    # write snapshot for cockpit
    try:
        out = PROCESSED / "status" if LACIE_ROOT.exists() else Path(".aether") / "status"
        out.mkdir(parents=True, exist_ok=True)
        (out / "latest_status.json").write_text(json.dumps(payload, indent=2, default=str))
    except Exception:
        pass
    sys.exit(0)


def _write_research(name: str, payload: dict, *, tag: str | None = None) -> Path:
    from datetime import datetime, timezone

    from aether.paths import LACIE_ROOT

    if LACIE_ROOT.exists():
        d = LACIE_ROOT / "data" / "processed" / "research"
    else:
        d = Path(".aether") / "research"
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"_{tag}" if tag else ""
    path = d / f"{name}{suffix}_{stamp}.json"
    text = json.dumps(payload, indent=2, default=str)
    path.write_text(text)
    # Tagged research keeps its own latest_*_tag.json; only untagged
    # (or tag=custom/mission) overwrites the primary latest_{name}.json.
    if not tag or tag in ("custom", "mission", "primary"):
        (d / f"latest_{name}.json").write_text(text)
    if tag:
        (d / f"latest_{name}_{tag}.json").write_text(text)
    return path


def cmd_walkforward(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Multi-fold purged walk-forward research")
    parser.add_argument("--symbols", default="SPY,QQQ,IWM,SQQQ,SH")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--min-train-frac", type=float, default=0.4)
    parser.add_argument("--label", default="y_up_5d")
    parser.add_argument("--lacie", action="store_true")
    parser.add_argument("--universe", default=None, help="named universe e.g. sector_spdr, research_liquid")
    parser.add_argument("--max-positions", type=int, default=5)
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-07-10")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from datetime import date as date_cls

    import pandas as pd

    from aether.engine.risk import RiskConfig
    from aether.engine.universe import all_named
    from aether.engine.walkforward import report_to_dict, run_walkforward

    if args.universe:
        u = all_named().get(args.universe)
        if not u:
            print(f"unknown universe {args.universe}; have {list(all_named())}", file=sys.stderr)
            sys.exit(2)
        symbols = list(u.symbols)
    else:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    start = date_cls.fromisoformat(args.start) if args.start else None
    end = date_cls.fromisoformat(args.end) if args.end else None

    if args.lacie:
        from aether.engine.lacie_source import LacieEodBulkSource

        panel = LacieEodBulkSource(symbols=symbols).panel(start=start, end=end)
        source = "LacieEodBulkSource"
    else:
        from aether.engine.mock_data import MockDailySource

        panel = MockDailySource(symbols=symbols, seed=11).panel(start=start, end=end)
        source = "MockDailySource"
    if start is not None:
        panel = panel[panel["date"] >= pd.Timestamp(start)]
    if end is not None:
        panel = panel[panel["date"] <= pd.Timestamp(end)]

    rep = run_walkforward(
        panel,
        n_folds=args.folds,
        min_train_frac=args.min_train_frac,
        purge_days=args.purge_days,
        label_col=args.label,
        risk=RiskConfig(
            max_positions=args.max_positions,
            min_confidence=args.min_confidence,
        ),
        symbols=symbols,
    )
    payload = {
        "kind": "walkforward",
        "source": source,
        **report_to_dict(rep),
    }
    tag = args.universe or "custom"
    path = _write_research("walkforward", payload, tag=tag)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"Walk-forward ({source}) folds={len(rep.folds)} purge={args.purge_days}")
        print(f"  symbols: {symbols}")
        print(f"  aggregate: {json.dumps(rep.aggregate, indent=2)}")
        for f in rep.folds:
            tr = f.stats.get("total_return")
            sh = f.stats.get("sharpe_like")
            print(
                f"  fold {f.fold}: {f.test_start}→{f.test_end} "
                f"ret={tr} sharpe={sh} brier={f.brier}"
            )
        print(f"  wrote {path}")
    sys.exit(0)


def cmd_horizon_compare(argv: list[str] | None = None) -> None:
    """Single-cut OOS compare across label horizons (1d/5d/20d)."""
    parser = argparse.ArgumentParser(description="Label-horizon OOS compare")
    parser.add_argument("--symbols", default="SPY,QQQ,IWM,SQQQ,SH,AAPL,NVDA")
    parser.add_argument("--lacie", action="store_true")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-07-10")
    parser.add_argument("--max-positions", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from datetime import date as date_cls

    from aether.engine.pipeline import run_offline_pipeline
    from aether.engine.risk import RiskConfig

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    start = date_cls.fromisoformat(args.start)
    end = date_cls.fromisoformat(args.end)
    if args.lacie:
        from aether.engine.lacie_source import LacieEodBulkSource

        src = LacieEodBulkSource(symbols=symbols)
        source = "LacieEodBulkSource"
    else:
        from aether.engine.mock_data import MockDailySource

        src = MockDailySource(symbols=symbols, seed=5)
        source = "MockDailySource"

    rows = []
    for label, purge in (("y_up_1d", 1), ("y_up_5d", 5), ("y_up_20d", 20)):
        r = run_offline_pipeline(
            source=src,
            symbols=symbols,
            start=start,
            end=end,
            train_frac=0.7,
            purge_days=purge,
            label_col=label,
            write_telemetry=False,
            risk=RiskConfig(max_positions=args.max_positions),
            flight_name=f"horizon_{label}",
        )
        rows.append(
            {
                "label": label,
                "purge_days": purge,
                "train_rows": r.train_rows,
                "test_rows": r.test_rows,
                "brier": r.calibration.get("brier"),
                **r.backtest.stats,
                "top_weights": (r.scorer.coefficient_table()[:5] if r.scorer else []),
            }
        )
        print(f"  {label}: ret={rows[-1].get('total_return')} sharpe={rows[-1].get('sharpe_like')}")

    payload = {
        "kind": "horizon_compare",
        "source": source,
        "symbols": symbols,
        "window": f"{args.start}→{args.end}",
        "rows": rows,
    }
    path = _write_research("horizon_compare", payload)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"wrote {path}")
    sys.exit(0)


def cmd_risk_sweep(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Risk-config OOS sweep (single cut)")
    parser.add_argument("--symbols", default="SPY,QQQ,IWM,SQQQ,SH,AAPL,NVDA")
    parser.add_argument("--lacie", action="store_true")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-07-10")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from datetime import date as date_cls

    import pandas as pd

    from aether.engine.walkforward import risk_sweep

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    start = date_cls.fromisoformat(args.start) if args.start else None
    end = date_cls.fromisoformat(args.end) if args.end else None
    if args.lacie:
        from aether.engine.lacie_source import LacieEodBulkSource

        panel = LacieEodBulkSource(symbols=symbols).panel(start=start, end=end)
        source = "LacieEodBulkSource"
    else:
        from aether.engine.mock_data import MockDailySource

        panel = MockDailySource(symbols=symbols, seed=3).panel(start=start, end=end)
        source = "MockDailySource"
    if start is not None:
        panel = panel[panel["date"] >= pd.Timestamp(start)]
    if end is not None:
        panel = panel[panel["date"] <= pd.Timestamp(end)]

    rows = risk_sweep(panel)
    payload = {
        "kind": "risk_sweep",
        "source": source,
        "symbols": symbols,
        "window": f"{args.start}→{args.end}",
        "rows": rows,
    }
    path = _write_research("risk_sweep", payload)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"Risk sweep ({source}) n={len(rows)}")
        for r in rows:
            print(
                f"  pos={r['max_positions']} conf={r['min_confidence']} "
                f"risk={r['max_risk_per_trade']} → ret={r.get('total_return')} "
                f"sharpe={r.get('sharpe_like')} dd={r.get('max_drawdown')} "
                f"fills={r.get('n_fills')} rej={r.get('n_rejections')}"
            )
        print(f"  wrote {path}")
    sys.exit(0)


def cmd_archive_status(argv: list[str] | None = None) -> None:
    """Local-only: earnings panels + multi-TF inventory (no network)."""
    parser = argparse.ArgumentParser(description="Aether archive status (earnings + MTF)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report: dict = {"window": "2018-01-01→2026-07-10"}
    try:
        from aether.loaders.earnings import PANEL_FILES, earnings_panel

        earn = {}
        for name, path in PANEL_FILES.items():
            if path.exists():
                df = earnings_panel(name)
                times = (
                    df["time"].astype(str).value_counts(dropna=False).to_dict()
                    if "time" in df.columns
                    else {}
                )
                earn[name] = {
                    "path": str(path),
                    "events": int(len(df)),
                    "symbols": int(df["symbol"].nunique()) if not df.empty else 0,
                    "times": {str(k): int(v) for k, v in times.items()},
                }
            else:
                earn[name] = {"path": str(path), "missing": True}
        report["earnings"] = earn
    except Exception as e:
        report["earnings_error"] = str(e)

    try:
        from aether.loaders.mtf_charts import inventory

        report["mtf"] = {
            u: inventory(u).to_dict(orient="records") for u in ("sp500", "iwm", "nasdaq")
        }
    except Exception as e:
        report["mtf_error"] = str(e)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("Aether archive status (local)")
        print(f"  window: {report['window']}")
        if "earnings" in report:
            print("  earnings panels:")
            for k, v in report["earnings"].items():
                if v.get("missing"):
                    print(f"    {k}: MISSING")
                else:
                    print(
                        f"    {k}: events={v['events']} symbols={v['symbols']} times={v.get('times')}"
                    )
        if "mtf" in report:
            print("  multi-TF files:")
            for u, rows in report["mtf"].items():
                for r in rows:
                    print(
                        f"    {u}/{r['interval']}: nonempty={r['nonempty']} "
                        f"empty={r['empty_markers']} files={r['files']}"
                    )
    sys.exit(0)


def cmd_earnings_specialist(argv: list[str] | None = None) -> None:
    """Train/evaluate pre-earnings specialist from LaCie event tables."""
    parser = argparse.ArgumentParser(description="Aether earnings specialist (local)")
    parser.add_argument("--universe", default="sp500", choices=["sp500", "iwm", "nasdaq"])
    parser.add_argument("--train-frac", type=float, default=0.7)
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from aether.engine.earnings_specialist import run_earnings_specialist

    try:
        r = run_earnings_specialist(
            args.universe,
            train_frac=args.train_frac,
            min_confidence=args.min_confidence,
            write=True,
        )
    except Exception as e:
        print(f"earnings-specialist failed: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(
            json.dumps(
                {
                    "universe": r.universe,
                    "accuracy": r.accuracy,
                    "brier": r.brier,
                    "base_rate": r.base_rate,
                    "lift": r.lift,
                    "n_train": r.n_train,
                    "n_test": r.n_test,
                    "cut_date": r.cut_date,
                    "long_only_mean_post_1d": r.long_only_mean_post_1d,
                    "short_only_mean_post_1d": r.short_only_mean_post_1d,
                    "path": r.path,
                },
                indent=2,
            )
        )
    else:
        print("Aether earnings specialist")
        print(f"  universe={r.universe} window={r.window}")
        print(f"  events={r.n_events} train={r.n_train} test={r.n_test} cut={r.cut_date}")
        print(f"  accuracy={r.accuracy:.4f} base_rate={r.base_rate:.4f} lift={r.lift:.4f}")
        print(f"  brier={r.brier:.4f}")
        print(f"  OOS mean post_1d @p>={args.min_confidence}: {r.long_only_mean_post_1d}")
        print(f"  OOS mean post_1d @p<={1-args.min_confidence:.2f}: {r.short_only_mean_post_1d}")
        print(f"  wrote {r.path}")
    sys.exit(0)


def cmd_mtf_research(argv: list[str] | None = None) -> None:
    """SP500 multi-TF research flight from completed LaCie charts."""
    parser = argparse.ArgumentParser(description="Aether SP500 multi-TF research (local)")
    parser.add_argument("--interval", default="15min", choices=["1hour", "15min", "5min", "1min"])
    parser.add_argument("--label", default="y_up_5", choices=["y_up_1", "y_up_5"])
    parser.add_argument("--train-frac", type=float, default=0.7)
    parser.add_argument("--min-confidence", type=float, default=0.55)
    parser.add_argument(
        "--symbol-limit",
        type=int,
        default=0,
        help="0 = all SP500 with files; else cap for faster runs",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from aether.engine.mtf_research import run_sp500_mtf_research

    try:
        r = run_sp500_mtf_research(
            interval=args.interval,
            label=args.label,
            train_frac=args.train_frac,
            min_confidence=args.min_confidence,
            symbol_limit=args.symbol_limit or None,
            write=True,
        )
    except Exception as e:
        print(f"mtf-research failed: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(
            json.dumps(
                {
                    "interval": r.interval,
                    "label": r.label,
                    "n_symbols": r.n_symbols,
                    "n_bars": r.n_bars,
                    "accuracy": r.accuracy,
                    "brier": r.brier,
                    "base_rate": r.base_rate,
                    "lift": r.lift,
                    "mean_fwd_when_long": r.mean_fwd_when_long,
                    "mean_fwd_when_short": r.mean_fwd_when_short,
                    "path": r.path,
                },
                indent=2,
            )
        )
    else:
        print("Aether SP500 multi-TF research")
        print(f"  interval={r.interval} label={r.label} symbols={r.n_symbols} bars={r.n_bars}")
        print(f"  train={r.n_train} test={r.n_test} cut={r.cut_date}")
        print(f"  accuracy={r.accuracy:.4f} base={r.base_rate:.4f} lift={r.lift:.4f} brier={r.brier:.4f}")
        print(f"  mean fwd @long conf: {r.mean_fwd_when_long}")
        print(f"  mean fwd @short conf: {r.mean_fwd_when_short}")
        print(f"  wrote {r.path}")
    sys.exit(0)


def main() -> None:
    """Unified entry: python -m aether.cli integrity|f1|engine-flight|status|walkforward|risk-sweep"""
    if len(sys.argv) < 2:
        print(
            "usage: python -m aether.cli "
            "[integrity|f1|engine-flight|status|walkforward|risk-sweep|"
            "horizon|archive-status|earnings-specialist|mtf-research] …"
        )
        sys.exit(2)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "integrity":
        cmd_integrity(rest)
    elif cmd in ("f1", "f1-features"):
        cmd_f1_features(rest)
    elif cmd in ("engine-flight", "flight", "engine", "lacie-flight"):
        if cmd == "lacie-flight" and "--lacie" not in rest:
            rest = ["--lacie", *rest]
        cmd_engine_flight(rest)
    elif cmd in ("status", "st"):
        cmd_status(rest)
    elif cmd in ("walkforward", "wf", "walk-forward"):
        cmd_walkforward(rest)
    elif cmd in ("risk-sweep", "risk_sweep", "sweep"):
        cmd_risk_sweep(rest)
    elif cmd in ("horizon", "horizon-compare", "horizons"):
        cmd_horizon_compare(rest)
    elif cmd in ("archive-status", "archives", "mtf-status", "earnings-status"):
        cmd_archive_status(rest)
    elif cmd in ("earnings-specialist", "earn-ml", "earnings-ml"):
        cmd_earnings_specialist(rest)
    elif cmd in ("mtf-research", "mtf", "sp500-mtf"):
        cmd_mtf_research(rest)
    else:
        print(f"unknown command: {cmd}")
        sys.exit(2)


if __name__ == "__main__":
    main()
