"""Quality score: ROIC and operating margin change, ranked within a group."""

import pytest

from ilovestock.models import Quality
from ilovestock.quality import margin_change, ranks, scores


def q(roic: float | None, chg: float | None) -> Quality:
    return Quality(roic, None, None, chg)


def test_margin_change_same_quarter_last_year():
    sales = [200.0, 150.0, 140.0, 130.0, 100.0]
    op = [30.0, 15.0, 14.0, 13.0, 10.0]
    assert margin_change(sales, op) == (15.0, 10.0, 5.0)


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
