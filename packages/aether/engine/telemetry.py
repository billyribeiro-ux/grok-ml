"""Mission telemetry — write flight reports for cockpit / postmortems."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from aether.engine.backtest import BacktestResult, Fill
from aether.engine.types import Mode, Side, Signal
from aether.paths import PROCESSED, require_lacie

# Keep payload cockpit-friendly; densify without multi-MB dumps.
MAX_EQUITY_POINTS = 800
MAX_FILLS = 400
MAX_SIGNALS = 300
MAX_REJECTIONS = 100
MAX_BARS_PER_SYMBOL = 400


def telemetry_dir(offline: bool = False) -> Path:
    """Prefer LaCie processed/; fall back to repo .aether/telemetry if unmounted."""
    if not offline:
        try:
            require_lacie()
            d = PROCESSED / "telemetry"
            d.mkdir(parents=True, exist_ok=True)
            return d
        except Exception:
            pass
    root = Path(__file__).resolve().parents[3]
    d = root / ".aether" / "telemetry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _iso_date(v: Any) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()[:10]
        except Exception:
            pass
    s = str(v)
    return s[:10] if len(s) >= 10 else s


def _downsample_rows(rows: list[dict], max_n: int) -> list[dict]:
    if len(rows) <= max_n:
        return rows
    # always keep first + last; uniform sample in between
    if max_n < 3:
        return rows[-max_n:]
    idx = [0]
    mid = max_n - 2
    step = (len(rows) - 1) / (mid + 1)
    for i in range(1, mid + 1):
        idx.append(int(round(i * step)))
    idx.append(len(rows) - 1)
    # unique preserve order
    seen: set[int] = set()
    out: list[dict] = []
    for i in idx:
        if i not in seen and 0 <= i < len(rows):
            seen.add(i)
            out.append(rows[i])
    return out


def serialize_equity_curve(eq: pd.DataFrame, max_points: int = MAX_EQUITY_POINTS) -> list[dict]:
    if eq is None or eq.empty:
        return []
    df = eq.copy()
    rows: list[dict] = []
    for r in df.itertuples(index=False):
        d = getattr(r, "date", None)
        equity_cents = int(getattr(r, "equity_cents", 0))
        cash_cents = int(getattr(r, "cash_cents", 0)) if hasattr(r, "cash_cents") else None
        n_pos = int(getattr(r, "n_pos", 0)) if hasattr(r, "n_pos") else None
        day_pnl = int(getattr(r, "day_pnl_cents", 0)) if hasattr(r, "day_pnl_cents") else None
        dd = float(getattr(r, "drawdown", 0.0)) if hasattr(r, "drawdown") else None
        rows.append(
            {
                "date": _iso_date(d),
                "equity_usd": round(equity_cents / 100.0, 2),
                "equity_cents": equity_cents,
                "cash_usd": round(cash_cents / 100.0, 2) if cash_cents is not None else None,
                "n_pos": n_pos,
                "day_pnl_usd": round(day_pnl / 100.0, 2) if day_pnl is not None else None,
                "drawdown": round(dd, 6) if dd is not None else None,
            }
        )
    return _downsample_rows(rows, max_points)


def serialize_fills(fills: list[Fill], max_n: int = MAX_FILLS) -> list[dict]:
    out = [
        {
            "date": _iso_date(f.date),
            "symbol": f.symbol,
            "side": f.side,
            "qty": int(f.qty),
            "px": round(float(f.px), 4),
            "reason": f.reason,
            "notional_usd": round(float(f.qty) * float(f.px), 2),
        }
        for f in fills
    ]
    # keep most recent if truncated
    return out[-max_n:]


def _bucket_reason(reason: str) -> str:
    r = str(reason or "unknown")
    if r.startswith("scorer_long"):
        return "scorer_long"
    if r.startswith("scorer_inverse"):
        return "scorer_inverse"
    if r.startswith("scorer_"):
        return "scorer_other"
    if r in ("stop", "target", "time_stop"):
        return r
    if "inverse" in r:
        return "inverse"
    if "hunter" in r:
        return "hunter"
    if "farmer" in r:
        return "farmer"
    return r


def fill_summary(fills: list[Fill]) -> dict[str, Any]:
    by_sym: Counter[str] = Counter()
    by_side: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()
    by_reason_raw: Counter[str] = Counter()
    notional = 0.0
    for f in fills:
        by_sym[f.symbol] += 1
        by_side[f.side] += 1
        by_reason[_bucket_reason(str(f.reason))] += 1
        by_reason_raw[str(f.reason)] += 1
        notional += float(f.qty) * float(f.px)
    # keep top raw reasons only (dense scorer conf strings explode cardinality)
    top_raw = dict(by_reason_raw.most_common(24))
    return {
        "by_symbol": dict(by_sym),
        "by_side": dict(by_side),
        "by_reason": dict(by_reason),
        "by_reason_raw_top": top_raw,
        "n_total": len(fills),
        "gross_notional_usd": round(notional, 2),
    }


def serialize_signals(signals: list[Signal], max_n: int = MAX_SIGNALS) -> tuple[list[dict], dict]:
    by_mode: Counter[str] = Counter()
    by_side: Counter[str] = Counter()
    by_symbol: Counter[str] = Counter()
    rows: list[dict] = []
    for s in signals:
        by_mode[s.mode.value] += 1
        by_side[s.side.value] += 1
        by_symbol[s.symbol] += 1
        rows.append(
            {
                "date": _iso_date(s.as_of),
                "symbol": s.symbol,
                "side": s.side.value,
                "mode": s.mode.value,
                "confidence": round(float(s.confidence), 4),
                "expected_edge": round(float(s.expected_edge), 6),
                "stop_pct": round(float(s.stop_pct), 4),
                "target_pct": round(float(s.target_pct), 4),
                "size_fraction": round(float(s.size_fraction), 4),
                "reason": s.reason,
                "p_up": (
                    round(float(s.meta["p_up"]), 4)
                    if isinstance(s.meta, dict) and s.meta.get("p_up") is not None
                    else None
                ),
            }
        )
    # prefer actionable + recent for blotter display
    actionable = [
        r
        for r in rows
        if r["mode"] != Mode.STAND_DOWN.value and r["side"] != Side.FLAT.value
    ]
    stand = [r for r in rows if r["mode"] == Mode.STAND_DOWN.value]
    # last actionable first, then fill with stand_down
    blotter = (actionable[-max_n:] + stand[-(max(0, max_n - len(actionable[-max_n:]))):])[-max_n:]
    blotter = sorted(blotter, key=lambda r: (r["date"], r["symbol"]))
    summary = {
        "by_mode": dict(by_mode),
        "by_side": dict(by_side),
        "by_symbol": dict(by_symbol),
        "n_total": len(signals),
        "n_blotter": len(blotter),
        "truncated": len(signals) > len(blotter),
    }
    return blotter, summary


def serialize_rejections(rejections: list[dict], max_n: int = MAX_REJECTIONS) -> list[dict]:
    out = []
    for r in rejections[-max_n:]:
        out.append(
            {
                "date": _iso_date(r.get("date")),
                "symbol": r.get("symbol"),
                "reason": r.get("reason"),
            }
        )
    return out


def rejection_summary(rejections: list[dict]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for r in rejections:
        c[str(r.get("reason") or "unknown")] += 1
    return dict(c)


def serialize_ohlc_panel(
    features: pd.DataFrame | None,
    symbols: list[str],
    max_bars: int = MAX_BARS_PER_SYMBOL,
) -> dict[str, list[dict]]:
    """Honest OHLC from feature/panel frame for cockpit charts — never fabricated."""
    if features is None or features.empty:
        return {}
    need = {"symbol", "date", "open", "high", "low", "close"}
    if not need.issubset(set(features.columns)):
        # try close-only
        if not {"symbol", "date", "close"}.issubset(set(features.columns)):
            return {}
    out: dict[str, list[dict]] = {}
    for sym in symbols:
        sub = features[features["symbol"] == sym].sort_values("date")
        if sub.empty:
            continue
        if len(sub) > max_bars:
            sub = sub.iloc[-max_bars:]
        bars: list[dict] = []
        for r in sub.itertuples(index=False):
            bar = {
                "date": _iso_date(getattr(r, "date")),
                "close": round(float(getattr(r, "close")), 4),
            }
            for k in ("open", "high", "low", "volume"):
                if hasattr(r, k):
                    v = getattr(r, k)
                    if v is not None and pd.notna(v):
                        bar[k] = int(v) if k == "volume" else round(float(v), 4)
            # optional feature overlays if present
            for k in ("ret_1d", "px_vs_sma20", "p_up", "regime_uncertainty", "breadth_integrity"):
                if hasattr(r, k):
                    v = getattr(r, k)
                    if v is not None and pd.notna(v):
                        bar[k] = round(float(v), 6)
            bars.append(bar)
        out[sym] = bars
    return out


def build_series_payload(
    bt: BacktestResult,
    *,
    features: pd.DataFrame | None = None,
    symbols: list[str] | None = None,
    calibration: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    syms = symbols or []
    blotter, sig_summary = serialize_signals(bt.signals)
    equity = serialize_equity_curve(bt.equity_curve)
    fills = serialize_fills(bt.fills)
    rejections = serialize_rejections(bt.rejections)
    ohlc = serialize_ohlc_panel(features, syms) if features is not None else {}
    rej_by = rejection_summary(bt.rejections)
    fills_by = fill_summary(bt.fills)
    coeffs = (model or {}).get("coefficients") or []

    # drawdown series from equity (already includes drawdown)
    return {
        "equity_curve": equity,
        "fills": fills,
        "fill_summary": fills_by,
        "signals": blotter,
        "signal_summary": sig_summary,
        "rejections": rejections,
        "rejection_summary": rej_by,
        "calibration_bins": (calibration or {}).get("bins") or [],
        "feature_weights": coeffs,
        "model": model or {},
        "ohlc": ohlc,
        "meta": {
            "n_equity": len(equity),
            "n_fills_payload": len(fills),
            "n_fills_total": len(bt.fills),
            "n_signals_payload": len(blotter),
            "n_signals_total": len(bt.signals),
            "n_rejections_payload": len(rejections),
            "n_rejections_total": len(bt.rejections),
            "ohlc_symbols": list(ohlc.keys()),
            "n_feature_weights": len(coeffs),
        },
    }


def write_flight_report(
    *,
    name: str,
    stats: dict[str, Any],
    source: str,
    symbols: list[str],
    extra: dict[str, Any] | None = None,
    series: dict[str, Any] | None = None,
    offline: bool = False,
    promote_latest: bool = True,
) -> Path:
    """
    Write stamped telemetry JSON.

    promote_latest=True (default) updates latest_flight.json / latest_series.json
    for the mission dashboard. Research grids should pass promote_latest=False so
    exploratory flights do not clobber the mission book.
    """
    payload: dict[str, Any] = {
        "name": name,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "symbols": symbols,
        "stats": stats,
        "extra": extra or {},
        "laws": {
            "L0_truth": True,
            "note": (
                "Mock flights are plumbing only; not live edge."
                if "Mock" in source
                else "Paper walk-forward on real bars — not live routing."
            ),
        },
    }
    if series:
        payload["series"] = series

    d = telemetry_dir(offline=offline)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = d / f"{name}_{stamp}.json"
    text = json.dumps(payload, indent=2, default=str)
    path.write_text(text)
    if promote_latest:
        (d / "latest_flight.json").write_text(text)
        # compact series sidecar for tools that only want curves
        if series:
            sidecar = {
                "name": name,
                "written_at": payload["written_at"],
                "symbols": symbols,
                "equity_curve": series.get("equity_curve", []),
                "signal_summary": series.get("signal_summary", {}),
                "calibration_bins": series.get("calibration_bins", []),
                "meta": series.get("meta", {}),
            }
            (d / "latest_series.json").write_text(json.dumps(sidecar, indent=2, default=str))
    return path


def flight_from_backtest(
    bt: BacktestResult,
    *,
    name: str,
    source: str,
    symbols: list[str],
    offline: bool = False,
    extra: dict[str, Any] | None = None,
    features: pd.DataFrame | None = None,
    calibration: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
    promote_latest: bool = True,
) -> Path:
    series = build_series_payload(
        bt,
        features=features,
        symbols=symbols,
        calibration=calibration,
        model=model,
    )
    return write_flight_report(
        name=name,
        stats=bt.stats,
        source=source,
        symbols=symbols,
        extra=extra,
        series=series,
        offline=offline,
        promote_latest=promote_latest,
    )
