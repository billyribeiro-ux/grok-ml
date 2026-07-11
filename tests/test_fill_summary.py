from datetime import date

from aether.engine.backtest import Fill
from aether.engine.telemetry import _bucket_reason, fill_summary


def test_bucket_reason_groups_scorer_conf():
    assert _bucket_reason("scorer_long_p=0.612") == "scorer_long"
    assert _bucket_reason("scorer_inverse_p=0.41") == "scorer_inverse"
    assert _bucket_reason("stop") == "stop"
    assert _bucket_reason("time_stop") == "time_stop"


def test_fill_summary_counts():
    fills = [
        Fill(date(2024, 1, 2), "SPY", "buy", 10, 100.0, "scorer_long_p=0.61"),
        Fill(date(2024, 1, 3), "SPY", "sell", 10, 101.0, "target"),
        Fill(date(2024, 1, 4), "SH", "buy", 5, 20.0, "scorer_inverse_p=0.4"),
    ]
    s = fill_summary(fills)
    assert s["n_total"] == 3
    assert s["by_symbol"]["SPY"] == 2
    assert s["by_reason"]["scorer_long"] == 1
    assert s["by_reason"]["scorer_inverse"] == 1
    assert s["by_reason"]["target"] == 1
