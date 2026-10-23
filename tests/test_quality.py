"""Quality score: ROIC and operating margin change, ranked within a group."""

import pytest
from rich.console import Console

from ilovestock.models import Quality
from ilovestock.quality import margin_change, ranks, scores
from ilovestock.report import quality_text, screen_table
from ilovestock.screener import ScreenHit, ScreenResult


def q(roic: float | None, chg: float | None) -> Quality:
    return Quality(roic, None, None, chg)


def test_margin_change_same_quarter_last_year():
    sales = [200.0, 150.0, 140.0, 130.0, 100.0]
    op = [30.0, 15.0, 14.0, 13.0, 10.0]
    assert margin_change(sales, op) == (15.0, 10.0, 5.0)


def test_margin_change_rounds_after_subtracting():
    # 10.004% vs 9.996%: both show as 10.0, but the change is +0.008 pt, not 0
    assert margin_change([1000.0] * 5, [100.04, 1, 1, 1, 99.96]) == (10.0, 10.0, 0.01)


@pytest.mark.parametrize(
    "sales,op",
    [
        ([200.0, 1, 1, 1], [30.0, 1, 1, 1]),  # 4 quarters
        ([200.0, 1, 1, 1, 0.0], [30.0, 1, 1, 1, 10.0]),  # zero revenue
        ([200.0, 1, 1, 1, 100.0], [None, 1, 1, 1, 10.0]),  # missing value
    ],
)
def test_margin_change_nd(sales, op):
    assert margin_change(sales, op) == (None, None, None)


def test_ranks_ties_and_none():
    assert ranks([10.0, None, 10.0, 5.0]) == [1, None, 1, 3]


def test_scores_scale_and_average():
    assert scores([q(30, 3), q(20, 1), q(10, 2)]) == [100.0, 25.0, 25.0]


def test_scores_none_is_worst_and_single_is_100():
    assert scores([q(None, 1), q(10, None)]) == [50.0, 50.0]
    assert scores([q(5, 1)]) == [100.0]


def test_quality_text_signs_and_nd():
    assert quality_text(Quality(31.2, 18.1, 14.0, 4.1)) == "ROIC 31.2%, op. margin +4.1 pt"
    assert quality_text(Quality(5.0, 1.0, 1.5, -0.5)) == "ROIC 5.0%, op. margin -0.5 pt"
    assert quality_text(Quality(None, None, None, None)) == "ROIC N/D, op. margin N/D"


def test_screen_table_rounds_half_up_like_the_web():
    # the web shows Math.round(score); Python's round-half-even would print 12 here
    hit = ScreenHit("IJKL", "180M (micro)", Quality(None, None, None, None), 12.5, None, None)
    console = Console(record=True, width=200)
    console.print(screen_table(ScreenResult(3, 3, [], [hit])))
    row = next(line for line in console.export_text().splitlines() if "IJKL" in line)
    assert " 13 " in row and "ROIC N/D, margin N/D of 3" in row
