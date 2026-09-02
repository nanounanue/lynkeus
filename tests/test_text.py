from __future__ import annotations

from datetime import datetime, timedelta

from lynkeus.text import age, bar, elapsed, spark

NOW = datetime(2026, 9, 2, 10, 11)


def test_spark_scales_to_the_block_range() -> None:
    assert spark([0, 4, 8]) == "▁▄█"
    assert spark([3, 3, 3]) == "▁▁▁"
    assert spark([]) == ""
    assert spark(list(range(10)), width=3) == "▁▄█"


def test_bar_splits_filled_and_rest() -> None:
    assert bar(12, 20, 10) == ("━━━━━━", "━━━━")
    assert bar(0, 0, 4) == ("", "━━━━")
    assert bar(5, 4, 4) == ("━━━━", "")


def test_age_buckets() -> None:
    assert age(NOW - timedelta(minutes=41), NOW) == "41m"
    assert age(NOW - timedelta(hours=2), NOW) == "2h"
    assert age(NOW - timedelta(days=1, hours=2), NOW) == "yesterday"
    assert age(NOW - timedelta(days=3), NOW) == "Sun"
    assert age(NOW - timedelta(days=20), NOW) == "Aug 13"
    assert age(None, NOW) == ""


def test_elapsed_is_hms() -> None:
    assert elapsed(NOW - timedelta(minutes=41, seconds=12), NOW) == "00:41:12"
