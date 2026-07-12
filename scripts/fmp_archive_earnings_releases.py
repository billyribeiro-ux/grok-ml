#!/usr/bin/env python3
"""
Archive earnings release dates for Aether pre-earnings / earnings ML.

Hard pin: 2018-01-01 → 2026-07-10

Why daily calendar chunks:
  FMP `earnings-calendar` hard-caps at ~4000 rows per request.
  Multi-year (and even monthly) pulls were truncated to a single day.
  Peak single days are ~2k names → daily is complete and honest.

What we store (no invented rows):
  1) Market-wide daily calendar with includeReportTimes=true
     → date, symbol, epsActual/Estimated, revenueActual/Estimated,
       time (bmo/amc/…), periodEnding, confirmed, lastUpdated
  2) Per-year earnings-surprises-bulk CSVs (when plan allows)
  3) Consolidated panels (parquet) + per-symbol JSON for
     SP500 / IWM / NASDAQ universes (filter of the full calendar)
  4) Optional per-symbol `earnings` endpoint (full history, no BMO/AMC)

OUT (LaCie):
  data/raw/fmp/earnings_archive/
    calendar_daily/YYYY-MM-DD.json
    surprises_bulk/YYYY.csv
    panels/{all,sp500,iwm,nasdaq}_2018_20260710.parquet
    by_symbol/{sp500,iwm,nasdaq}/{SYM}.json
    meta.json

Usage:
  python scripts/fmp_archive_earnings_releases.py
  python scripts/fmp_archive_earnings_releases.py --skip-daily   # rebuild panels only
  python scripts/fmp_archive_earnings_releases.py --per-symbol sp500
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
LACIE = Path("/Volumes/LaCie/Aether/data/raw/fmp")
if not Path("/Volumes/LaCie/Aether").exists():
    raise SystemExit("LaCie not mounted at /Volumes/LaCie/Aether")

OUT = LACIE / "earnings_archive"
CAL_DIR = OUT / "calendar_daily"
SURP_DIR = OUT / "surprises_bulk"
PANEL_DIR = OUT / "panels"
BY_SYM = OUT / "by_symbol"

START = date(2018, 1, 1)
END = date(2026, 7, 10)
SLEEP = float(os.getenv("FMP_EARN_SLEEP", "0.35"))
MIN_DAY_BYTES = 20


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_sym(t: str) -> str:
    return t.replace("/", "_").replace("^", "")


def get_json(path: str, params: dict | None = None, retries: int = 5):
    p = dict(params or {})
    p["apikey"] = API_KEY
    last_status = None
    for attempt in range(retries):
        try:
            r = requests.get(f"{BASE}/{path}", params=p, timeout=90)
        except Exception as e:
            print(f"  req err {path}: {e}", flush=True)
            time.sleep(2 + attempt)
            continue
        last_status = r.status_code
        if r.status_code == 429:
            wait = 8 + attempt * 4
            print(f"  429 {path} sleep {wait}s", flush=True)
            time.sleep(wait)
            continue
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} {path} {r.text[:120]}", flush=True)
            time.sleep(1)
            continue
        try:
            return r.json()
        except Exception:
            return None
    print(f"  give up {path} last={last_status}", flush=True)
    return None


def get_bytes(path: str, params: dict | None = None, retries: int = 5) -> bytes | None:
    p = dict(params or {})
    p["apikey"] = API_KEY
    for attempt in range(retries):
        try:
            r = requests.get(f"{BASE}/{path}", params=p, timeout=120)
        except Exception as e:
            print(f"  req err {path}: {e}", flush=True)
            time.sleep(2 + attempt)
            continue
        if r.status_code == 429:
            wait = 10 + attempt * 5
            print(f"  429 bulk {path} sleep {wait}s", flush=True)
            time.sleep(wait)
            continue
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} {path} {r.text[:160]}", flush=True)
            return None
        return r.content
    return None


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_universe(name: str) -> list[str]:
    if name == "sp500":
        # prefer cached constituents from MTF/archive
        for p in [
            LACIE / "sp500_full" / "constituents.json",
            LACIE / "sp500_full" / "universe_meta.json",
        ]:
            if p.name == "constituents.json" and p.exists():
                data = json.loads(p.read_text())
                if isinstance(data, list):
                    return sorted(
                        {
                            str(x.get("symbol", "")).strip()
                            for x in data
                            if isinstance(x, dict) and x.get("symbol")
                        }
                    )
        data = get_json("sp500-constituent")
        if not isinstance(data, list):
            return []
        (LACIE / "sp500_full").mkdir(parents=True, exist_ok=True)
        (LACIE / "sp500_full" / "constituents.json").write_text(
            json.dumps(data, indent=2, default=str)
        )
        return sorted(
            {str(x.get("symbol", "")).strip() for x in data if x.get("symbol")}
        )

    if name == "iwm":
        hold = LACIE / "iwm_russell2000" / "holdings.json"
        if not hold.exists():
            return []
        rows = json.loads(hold.read_text())
        syms = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            t = (r.get("ticker") or r.get("symbol") or r.get("asset") or "").strip()
            if t:
                syms.append(t)
        if "IWM" not in {s.upper() for s in syms}:
            syms.append("IWM")
        return list(dict.fromkeys(syms))

    if name == "nasdaq":
        batch = LACIE / "nasdaq_full" / "batch_exchange_nasdaq.json"
        if not batch.exists():
            return []
        rows = json.loads(batch.read_text())
        return list(
            dict.fromkeys(
                str(r.get("symbol", "")).strip()
                for r in rows
                if isinstance(r, dict) and r.get("symbol")
            )
        )
    return []


def archive_daily_calendar(force: bool = False) -> dict:
    CAL_DIR.mkdir(parents=True, exist_ok=True)
    days = list(daterange(START, END))
    stats = {
        "days_total": len(days),
        "skipped": 0,
        "ok": 0,
        "empty": 0,
        "capped_4000": 0,
        "fail": 0,
        "rows": 0,
    }
    print(
        f"[daily] earnings-calendar {START}→{END} days={len(days)} includeReportTimes=true",
        flush=True,
    )
    for i, d in enumerate(days, 1):
        path = CAL_DIR / f"{d.isoformat()}.json"
        if not force and path.exists() and path.stat().st_size >= MIN_DAY_BYTES:
            stats["skipped"] += 1
            if i % 500 == 0:
                print(f"  progress {i}/{len(days)} (skip-heavy)", flush=True)
            continue

        data = get_json(
            "earnings-calendar",
            {
                "from": d.isoformat(),
                "to": d.isoformat(),
                "includeReportTimes": "true",
            },
        )
        time.sleep(SLEEP)

        if data is None:
            stats["fail"] += 1
            continue
        if not isinstance(data, list):
            stats["fail"] += 1
            continue
        if len(data) == 0:
            # honest empty day (weekends/holidays often empty)
            path.write_text("[]")
            stats["empty"] += 1
            continue
        if len(data) >= 4000:
            stats["capped_4000"] += 1
            print(f"  WARN day {d} hit 4000-cap — may be truncated", flush=True)

        payload = {
            "date": d.isoformat(),
            "n": len(data),
            "includeReportTimes": True,
            "downloaded_at": now(),
            "rows": data,
        }
        path.write_text(json.dumps(payload, default=str))
        stats["ok"] += 1
        stats["rows"] += len(data)
        if i % 50 == 0 or i == len(days):
            print(
                f"  day {i}/{len(days)} {d} rows={len(data)} "
                f"ok={stats['ok']} skip={stats['skipped']} fail={stats['fail']} cap={stats['capped_4000']}",
                flush=True,
            )
    return stats


def archive_surprises_bulk() -> dict:
    SURP_DIR.mkdir(parents=True, exist_ok=True)
    stats = {"ok": 0, "skip": 0, "fail": 0}
    print("[surprises] earnings-surprises-bulk by year", flush=True)
    for y in range(START.year, END.year + 1):
        path = SURP_DIR / f"{y}.csv"
        if path.exists() and path.stat().st_size > 1000:
            stats["skip"] += 1
            continue
        body = get_bytes("earnings-surprises-bulk", {"year": y})
        time.sleep(max(SLEEP, 1.0))
        if not body or len(body) < 50 or body[:1] == b"{":
            # JSON error body
            print(f"  year {y} fail/empty body={body[:120] if body else None}", flush=True)
            stats["fail"] += 1
            continue
        path.write_bytes(body)
        stats["ok"] += 1
        print(f"  year {y} bytes={len(body)}", flush=True)
    return stats


def _rows_from_day_file(path: Path) -> list[dict]:
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return []
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("rows"), list):
        return [r for r in raw["rows"] if isinstance(r, dict)]
    return []


def build_panels() -> dict:
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    BY_SYM.mkdir(parents=True, exist_ok=True)
    print("[panels] loading daily calendar files…", flush=True)
    rows: list[dict] = []
    files = sorted(
        p for p in CAL_DIR.glob("*.json") if not p.name.startswith("._")
    )
    for i, p in enumerate(files, 1):
        for r in _rows_from_day_file(p):
            # normalize
            sym = str(r.get("symbol") or "").strip()
            if not sym:
                continue
            dt = str(r.get("date") or p.stem)[:10]
            if dt < START.isoformat() or dt > END.isoformat():
                continue
            rows.append(
                {
                    "symbol": sym,
                    "date": dt,
                    "epsActual": r.get("epsActual"),
                    "epsEstimated": r.get("epsEstimated"),
                    "revenueActual": r.get("revenueActual"),
                    "revenueEstimated": r.get("revenueEstimated"),
                    "time": r.get("time"),  # bmo / amc / …
                    "periodEnding": r.get("periodEnding"),
                    "confirmed": r.get("confirmed"),
                    "lastUpdated": r.get("lastUpdated"),
                }
            )
        if i % 500 == 0 or i == len(files):
            print(f"  loaded files {i}/{len(files)} rows={len(rows)}", flush=True)

    if not rows:
        print("[panels] no rows — skip", flush=True)
        return {"rows": 0}

    df = pd.DataFrame(rows)
    # dedupe: same symbol+date keep last
    df = df.drop_duplicates(subset=["symbol", "date"], keep="last")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # surprise features (honest nulls when missing)
    df["eps_surprise"] = df["epsActual"] - df["epsEstimated"]
    df["eps_surprise_pct"] = df["eps_surprise"] / df["epsEstimated"].abs().replace(0, pd.NA)
    df["revenue_surprise"] = df["revenueActual"] - df["revenueEstimated"]
    df["revenue_surprise_pct"] = df["revenue_surprise"] / df["revenueEstimated"].abs().replace(
        0, pd.NA
    )

    all_path = PANEL_DIR / "all_2018_20260710.parquet"
    df.to_parquet(all_path, index=False)
    print(f"  all panel rows={len(df)} → {all_path}", flush=True)

    stats = {"all_rows": int(len(df)), "universes": {}}
    for uname in ("sp500", "iwm", "nasdaq"):
        syms = set(load_universe(uname))
        if not syms:
            print(f"  [{uname}] universe empty — skip", flush=True)
            continue
        sub = df[df["symbol"].isin(syms)].copy()
        outp = PANEL_DIR / f"{uname}_2018_20260710.parquet"
        sub.to_parquet(outp, index=False)

        # per-symbol JSON for ML loaders
        udir = BY_SYM / uname
        udir.mkdir(parents=True, exist_ok=True)
        # also mirror under universe tree
        mirror = {
            "sp500": LACIE / "sp500_full" / "earnings",
            "iwm": LACIE / "iwm_russell2000" / "earnings",
            "nasdaq": LACIE / "nasdaq_full" / "earnings",
        }[uname]
        mirror.mkdir(parents=True, exist_ok=True)

        n_sym = 0
        for sym, g in sub.groupby("symbol"):
            recs = g.drop(columns=[], errors="ignore").to_dict(orient="records")
            # clean NaN → null for JSON
            clean = []
            for rec in recs:
                clean.append(
                    {
                        k: (None if (isinstance(v, float) and pd.isna(v)) else v)
                        for k, v in rec.items()
                    }
                )
            body = json.dumps(
                {
                    "symbol": sym,
                    "window": f"{START.isoformat()}→{END.isoformat()}",
                    "n": len(clean),
                    "source": "earnings-calendar+includeReportTimes",
                    "events": clean,
                },
                indent=2,
                default=str,
            )
            (udir / f"{safe_sym(str(sym))}.json").write_text(body)
            (mirror / f"{safe_sym(str(sym))}.json").write_text(body)
            n_sym += 1

        # universe meta
        meta = {
            "universe": uname,
            "window": f"{START.isoformat()}→{END.isoformat()}",
            "n_symbols_with_events": n_sym,
            "n_events": int(len(sub)),
            "n_universe": len(syms),
            "built_at": now(),
            "time_values": (
                sub["time"].dropna().astype(str).value_counts().to_dict()
                if "time" in sub.columns
                else {}
            ),
        }
        (udir / "_meta.json").write_text(json.dumps(meta, indent=2, default=str))
        (mirror / "_meta.json").write_text(json.dumps(meta, indent=2, default=str))
        stats["universes"][uname] = meta
        print(
            f"  [{uname}] events={len(sub)} symbols_with_events={n_sym}/{len(syms)} → {outp}",
            flush=True,
        )

    return stats


def archive_per_symbol(universe: str, force: bool = False) -> dict:
    """
    Per-symbol /stable/earnings — full history but NO bmo/amc time field.
    Use as supplement; calendar panel is primary for release timing.
    """
    syms = load_universe(universe)
    if not syms:
        print(f"[per-symbol] {universe} empty", flush=True)
        return {"n": 0}
    out = OUT / "per_symbol_earnings" / universe
    out.mkdir(parents=True, exist_ok=True)
    stats = {"ok": 0, "skip": 0, "empty": 0, "fail": 0}
    print(f"[per-symbol] earnings endpoint universe={universe} n={len(syms)}", flush=True)
    for i, sym in enumerate(syms, 1):
        path = out / f"{safe_sym(sym)}.json"
        if not force and path.exists() and path.stat().st_size > 80:
            stats["skip"] += 1
            continue
        data = get_json("earnings", {"symbol": sym})
        time.sleep(SLEEP)
        if data is None:
            stats["fail"] += 1
            continue
        if not isinstance(data, list) or not data:
            path.write_text(
                json.dumps(
                    {"symbol": sym, "n": 0, "events": [], "downloaded_at": now()},
                    indent=2,
                )
            )
            stats["empty"] += 1
            continue
        # filter to pin window (keep pre-window for context? user said only pin — filter)
        filtered = []
        for r in data:
            if not isinstance(r, dict):
                continue
            dt = str(r.get("date") or "")[:10]
            if not dt or dt < START.isoformat() or dt > END.isoformat():
                continue
            filtered.append(r)
        path.write_text(
            json.dumps(
                {
                    "symbol": sym,
                    "window": f"{START.isoformat()}→{END.isoformat()}",
                    "n": len(filtered),
                    "n_raw_unfiltered": len(data),
                    "source": "earnings",
                    "note": "no report time (bmo/amc); join calendar panel for time",
                    "downloaded_at": now(),
                    "events": filtered,
                },
                indent=2,
                default=str,
            )
        )
        stats["ok"] += 1
        if i % 50 == 0 or i == len(syms):
            print(
                f"  {universe} {i}/{len(syms)} ok={stats['ok']} skip={stats['skip']} "
                f"empty={stats['empty']} fail={stats['fail']}",
                flush=True,
            )
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-daily", action="store_true", help="skip daily calendar pull")
    ap.add_argument("--skip-surprises", action="store_true")
    ap.add_argument("--skip-panels", action="store_true")
    ap.add_argument(
        "--per-symbol",
        default="",
        help="also pull /earnings per symbol: sp500,iwm,nasdaq or all",
    )
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    print(
        f"Earnings archive pin {START.isoformat()}→{END.isoformat()} out={OUT}",
        flush=True,
    )
    print(f"started {now()}", flush=True)

    summary: dict = {"window": f"{START.isoformat()}→{END.isoformat()}", "started": now()}

    if not args.skip_daily:
        summary["daily"] = archive_daily_calendar(force=args.force)
    if not args.skip_surprises:
        summary["surprises"] = archive_surprises_bulk()
    if not args.skip_panels:
        summary["panels"] = build_panels()

    if args.per_symbol:
        targets = (
            ["sp500", "iwm", "nasdaq"]
            if args.per_symbol.strip().lower() == "all"
            else [x.strip() for x in args.per_symbol.split(",") if x.strip()]
        )
        summary["per_symbol"] = {}
        for u in targets:
            summary["per_symbol"][u] = archive_per_symbol(u, force=args.force)

    summary["finished"] = now()
    (OUT / "meta.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str), flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
