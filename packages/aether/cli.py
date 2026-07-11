"""CLI entrypoints for F0/F1 + offline engine flight."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from aether.features.daily import build_daily_features
from aether.features.store import write_feature_frame
from aether.integrity import run_integrity
from aether.loaders.eod_bulk import load_core_panel_from_eod_bulk
from aether.paths import F1_CORE_SYMBOLS, LaCieNotMountedError


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
    parser.add_argument("--start", default="2019-01-01", help="YYYY-MM-DD")
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
        # drop pure warm-up rows where ret_1d is null for cleanliness of train later
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
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--name", default="offline_flight")
    args = parser.parse_args(argv)

    from datetime import date as date_cls

    from aether.engine.mock_data import MockDailySource
    from aether.engine.pipeline import run_offline_pipeline

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    start = date_cls.fromisoformat(args.start) if args.start else None
    end = date_cls.fromisoformat(args.end) if args.end else None

    if args.lacie:
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
        offline_telemetry=offline_tel,
        flight_name=name,
    )
    stats = {
        **result.backtest.stats,
        "calibration_brier": result.calibration.get("brier"),
        "train_rows": result.train_rows,
        "test_rows": result.test_rows,
        "telemetry": str(result.telemetry_path) if result.telemetry_path else None,
        "source": source_name,
    }
    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        print(f"Aether engine flight ({source_name})")
        print(f"  symbols: {symbols}")
        print(f"  feature rows: {len(result.features)}  train={result.train_rows} test={result.test_rows}")
        print(f"  calibration Brier (test): {result.calibration.get('brier')}")
        for k, v in result.backtest.stats.items():
            print(f"  {k}: {v}")
        if result.telemetry_path:
            print(f"  telemetry: {result.telemetry_path}")
        if source_name.startswith("Mock"):
            print("  note: MOCK data — plumbing + scorer only, not live edge.")
    sys.exit(0)


def main() -> None:
    """Unified entry: python -m aether.cli integrity|f1|engine-flight"""
    if len(sys.argv) < 2:
        print("usage: python -m aether.cli [integrity|f1|engine-flight] …")
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
    else:
        print(f"unknown command: {cmd}")
        sys.exit(2)


if __name__ == "__main__":
    main()
