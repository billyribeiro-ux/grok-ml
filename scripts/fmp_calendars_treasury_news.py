#!/usr/bin/env python3
"""
High-value optional FMP pull: calendars, treasury rates, news.
Runs slowly and respects rate limits.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    raise SystemExit("FMP_API_KEY missing")

BASE = "https://financialmodelingprep.com/stable"
ASOF = date(2026, 7, 10)
SLEEP = float(os.getenv("FMP_OPTIONAL_SLEEP", "0.7"))

OUT = Path("/Volumes/LaCie/Aether/data/raw/fmp/optional_high_value")
OUT.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AetherOptional/1.0"})
_ok = _skip = _fail = 0


def get(path: str, params: dict | None = None, retries: int = 12) -> tuple[int, bytes]:
    params = {**(params or {}), "apikey": API_KEY}
    for attempt in range(retries):
        if attempt == 0:
            time.sleep(SLEEP)
        try:
            r = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=300)
            if r.status_code == 429:
                wait = min(240, 5 * (2 ** min(attempt, 6)))
                print(f"  429 {path} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            return r.status_code, r.content
        except Exception as e:
            print(f"  err {path}: {e}", flush=True)
            time.sleep(1 + attempt)
    return 0, b""


def save(name: str, api: str, params: dict | None, out: Path, min_bytes: int = 30) -> bool:
    global _ok, _skip, _fail
    if out.exists() and out.stat().st_size >= min_bytes:
        _skip += 1
        return True
    st, body = get(api, params)
    if st != 200 or len(body) < min_bytes:
        _fail += 1
        print(f"  MISS/empty {name} status={st} len={len(body)}", flush=True)
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        json.loads(body)
        out = out.with_suffix(".json")
    except Exception:
        if b"," in body[:100]:
            out = out.with_suffix(".csv")
    out.write_bytes(body)
    _ok += 1
    print(f"  OK {name} ({len(body)/1e6:.2f} MB)", flush=True)
    return True


def phase_calendars() -> None:
    print("\n[calendars]", flush=True)
    cur = date(2015, 1, 1)
    while cur <= ASOF:
        end = min(cur + timedelta(days=365), ASOF)
        fr = cur.isoformat()
        to = end.isoformat()
        save(f"earnings_{fr}_{to}", "earnings-calendar", {"from": fr, "to": to}, OUT / "calendars" / f"earnings_{fr}_{to}.json")
        save(f"dividends_{fr}_{to}", "dividends-calendar", {"from": fr, "to": to}, OUT / "dividends" / f"dividends_{fr}_{to}.json")
        save(f"splits_{fr}_{to}", "splits-calendar", {"from": fr, "to": to}, OUT / "splits" / f"splits_{fr}_{to}.json")
        save(f"ipos_{fr}_{to}", "ipos-calendar", {"from": fr, "to": to}, OUT / "ipos" / f"ipos_{fr}_{to}.json")
        save(f"econcal_{fr}_{to}", "economic-calendar", {"from": fr, "to": to}, OUT / "economic" / f"economic_{fr}_{to}.json")
        cur = end + timedelta(days=1)


def phase_treasury() -> None:
    print("\n[treasury]", flush=True)
    save("treasury_2015_2026", "treasury-rates", {"from": "2015-01-01", "to": ASOF.isoformat()}, OUT / "macro" / "treasury_rates.json")


def phase_news() -> None:
    print("\n[news]", flush=True)
    for page in range(1, 21):
        save(f"gen_{page}", "news/general-latest", {"page": page, "limit": 100}, OUT / "news" / "general" / f"p{page:02d}.json", 30)
        save(f"fmpn_{page}", "news/fmp-articles", {"page": page, "limit": 20}, OUT / "news" / "fmp" / f"p{page:02d}.json", 20)
        save(f"press_{page}", "news/press-releases-latest", {"page": page, "limit": 100}, OUT / "news" / "press" / f"p{page:02d}.json", 20)
        save(f"stockn_{page}", "news/stock", {"page": page, "limit": 100}, OUT / "news" / "stock" / f"p{page:02d}.json", 20)


def main() -> int:
    print("=" * 60, flush=True)
    print("OPTIONAL HIGH-VALUE: calendars / treasury / news", flush=True)
    print("=" * 60, flush=True)
    phase_calendars()
    phase_treasury()
    phase_news()
    print(f"\nDONE optional ok={_ok} skip={_skip} fail={_fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
