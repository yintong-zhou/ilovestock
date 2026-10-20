from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ilovestock.config import load
from ilovestock.models import CriterionResult, Fundamentals, Status, TradePlan, Verdict
from ilovestock.rules.earnings import earnings
from ilovestock.rules.fundamental import fundamental, growth_pct, market_cap_band
from ilovestock.rules.technical import technical
from ilovestock.rules.verdict import verdict

CFG = load(Path("does-not-exist.toml"))


def good_fundamentals(**kw) -> Fundamentals:
    base = dict(
        sales=[130.0, 100.0, 90.0, 80.0, 70.0],
        eps=[1.2, 1.0, 0.9, 0.8, 0.5],
        roe_pct=20.0,
        market_cap=1e9,
        next_earnings=date(2026, 12, 1),
        inst_own_pct=50.0,
        inst_trans_pct=1.5,
    )
    return Fundamentals(**{**base, **kw})


def prices(dividends: float = 0.0) -> pd.DataFrame:
    idx = pd.bdate_range("2025-01-01", periods=300)
    return pd.DataFrame({"Close": 10.0, "Dividends": 0.0}, index=idx).assign(
        Dividends=lambda d: np.where(d.index == idx[-5], dividends, 0.0)
    )


def by_name(results, prefix):
    return next(r for r in results if r.name.startswith(prefix))


# --- growth ---
def test_growth_qoq_and_yoy():
    s = [130.0, 100.0, 90.0, 80.0, 65.0]
    assert growth_pct(s, "qoq")[0] == pytest.approx(30)
    assert growth_pct(s, "yoy")[0] == pytest.approx(100)


def test_growth_missing_quarters_is_none():
    assert growth_pct([1.0, 2.0], "yoy")[0] is None
    assert growth_pct([1.0, None], "qoq")[0] is None


def test_growth_non_positive_base_is_none():
    value, note = growth_pct([0.66, -0.12], "qoq")
    assert value is None and "base" in note


# --- fundamental criteria ---
def test_all_fundamentals_pass():
    results = fundamental(good_fundamentals(), prices(), CFG)
    assert [r.status for r in results] == [Status.PASS] * 7


@pytest.mark.parametrize(
    "field,value,prefix,status",
    [
        ("sales", [110.0, 100.0], "Crescita vendite", Status.FAIL),
        ("eps", [1.1, 1.0], "Crescita EPS", Status.FAIL),
        ("roe_pct", 15.0, "ROE", Status.FAIL),
        ("roe_pct", None, "ROE", Status.ND),
        ("inst_own_pct", 80.0, "Istituzionali", Status.FAIL),
        ("inst_own_pct", None, "Istituzionali", Status.ND),
        ("inst_trans_pct", 0.0, "Transazioni", Status.FAIL),
        ("inst_trans_pct", None, "Transazioni", Status.ND),
        ("market_cap", 30e6, "Market cap", Status.FAIL),
        ("market_cap", 50e9, "Market cap", Status.FAIL),
        ("market_cap", None, "Market cap", Status.ND),
    ],
)
def test_fundamental_thresholds(field, value, prefix, status):
    results = fundamental(good_fundamentals(**{field: value}), prices(), CFG)
    assert by_name(results, prefix).status == status


def test_dividend_payer_fails():
    results = fundamental(good_fundamentals(), prices(dividends=0.2), CFG)
    assert by_name(results, "Dividend").status == Status.FAIL


def test_dividend_missing_column_is_nd():
    results = fundamental(good_fundamentals(), prices().drop(columns="Dividends"), CFG)
    assert by_name(results, "Dividend").status == Status.ND


def test_market_cap_bands():
    assert [market_cap_band(x * 1e6, CFG) for x in (10, 100, 1000, 5000, 50000, 300000)] == [
        "nano", "micro", "small", "mid", "large", "giant"
    ]  # fmt: skip


# --- earnings ---
@pytest.mark.parametrize(
    "next_date,status",
    [
        (date(2026, 11, 1), Status.PASS),  # 12 days
        (date(2026, 10, 30), Status.FAIL),  # 10 days: not > 10
        (date(2026, 10, 1), Status.ND),  # stale date
        (None, Status.ND),
    ],
)
def test_earnings(next_date, status):
    assert earnings(next_date, date(2026, 10, 20)).status == status


# --- technical ---
def test_technical_on_recorded_data(hzo_daily, bench_close):
    r = {c.name.split()[0]: c.status for c in technical(hzo_daily, bench_close)}
    # values checked against the recorded HZO series (Oct 2026)
    assert r == {"Forza": Status.PASS, "Donchian": Status.FAIL, "DMI": Status.FAIL,
                 "SMA": Status.PASS}  # fmt: skip


def test_technical_short_history_is_nd(hzo_daily, bench_close):
    results = technical(hzo_daily.iloc[-40:], bench_close.iloc[-40:])
    assert all(c.status == Status.ND for c in results)


# --- verdict: one case per blocking criterion ---
def _pass(name):
    return CriterionResult(name, Status.PASS, 1, "")


FUND = [_pass(f"f{i}") for i in range(7)]
TECH = [_pass(f"t{i}") for i in range(4)]
EARN = _pass("earnings")
PLAN = TradePlan(entry=10, stop=9, target=13, shares=5)


def test_verdict_buy_when_everything_passes():
    assert verdict(FUND, TECH, EARN, PLAN) == (Verdict.BUY, [])


@pytest.mark.parametrize("i", range(7))
@pytest.mark.parametrize("status", [Status.FAIL, Status.ND])
def test_verdict_each_fundamental_blocks(i, status):
    fund = [*FUND]
    fund[i] = CriterionResult(f"f{i}", status, None, "")
    v, reasons = verdict(fund, TECH, EARN, PLAN)
    assert v == Verdict.NO_BUY and reasons == [f"f{i}: {status}"]


@pytest.mark.parametrize("i", range(4))
def test_verdict_each_technical_blocks(i):
    tech = [*TECH]
    tech[i] = CriterionResult(f"t{i}", Status.FAIL, 0, "")
    assert verdict(FUND, tech, EARN, PLAN)[0] == Verdict.NO_BUY


@pytest.mark.parametrize("status", [Status.FAIL, Status.ND])
def test_verdict_earnings_blocks(status):
    earn = CriterionResult("earnings", status, None, "")
    assert verdict(FUND, TECH, earn, PLAN)[0] == Verdict.NO_BUY


@pytest.mark.parametrize(
    "plan",
    [
        None,
        TradePlan(entry=10, stop=9, discarded="R:R 1.5 < 2"),
        TradePlan(entry=10, stop=9, target=13, shares=0, discarded="0 azioni"),
    ],
)
def test_verdict_invalid_plan_blocks(plan):
    assert verdict(FUND, TECH, EARN, plan)[0] == Verdict.NO_BUY


def test_allow_missing_skips_fundamental_nd_only():
    fund = [*FUND]
    fund[3] = CriterionResult("inst", Status.ND, None, "")
    assert verdict(fund, TECH, EARN, PLAN, allow_missing=True)[0] == Verdict.BUY
    fund[2] = CriterionResult("roe", Status.FAIL, 1, "")
    assert verdict(fund, TECH, EARN, PLAN, allow_missing=True)[0] == Verdict.NO_BUY
    earn = CriterionResult("earnings", Status.ND, None, "")
    assert verdict(FUND, TECH, earn, PLAN, allow_missing=True)[0] == Verdict.NO_BUY
