from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ilovestock.analysis import analyze_many
from ilovestock.config import load
from ilovestock.models import CriterionResult, Fundamentals, Status, TradePlan, Verdict
from ilovestock.providers.yahoo import YahooProvider
from ilovestock.rules.earnings import earnings, post_earnings
from ilovestock.rules.fundamental import fundamental, growth_pct, market_cap_band
from ilovestock.rules.technical import (
    breakout_volume,
    consolidation,
    donchian_breakout,
    technical,
)
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
        ("sales_growth_yoy_pct", 20.0, "Sales growth", Status.FAIL),
        ("eps_growth_yoy_pct", 15.0, "EPS growth", Status.FAIL),
        ("sales", [110.0, 100.0], "Sales growth", Status.ND),  # yoy needs 5 quarters
        ("roe_pct", 15.0, "ROE", Status.FAIL),
        ("roe_pct", None, "ROE", Status.ND),
        ("inst_own_pct", 80.0, "Institutional own", Status.FAIL),
        ("inst_own_pct", None, "Institutional own", Status.ND),
        ("inst_trans_pct", 0.0, "Institutional trans", Status.FAIL),
        ("inst_trans_pct", None, "Institutional trans", Status.ND),
        ("market_cap", 30e6, "Market cap", Status.FAIL),
        ("market_cap", 50e9, "Market cap", Status.FAIL),
        ("market_cap", None, "Market cap", Status.ND),
    ],
)
def test_fundamental_thresholds(field, value, prefix, status):
    results = fundamental(good_fundamentals(**{field: value}), prices(), CFG)
    assert by_name(results, prefix).status == status


def test_qoq_growth_uses_yahoo_quarters_not_finviz():
    f = good_fundamentals(sales=[110.0, 100.0], sales_growth_yoy_pct=50.0)
    r = by_name(fundamental(f, prices(), replace(CFG, growth_basis="qoq")), "Sales growth")
    assert (r.status, r.value, r.note) == (Status.FAIL, 10.0, "source: Yahoo")


def test_yoy_growth_prefers_finviz():
    f = good_fundamentals(sales_growth_yoy_pct=25.0)
    r = by_name(fundamental(f, prices(), CFG), "Sales growth YOY")
    assert (r.status, r.value, r.note) == (Status.PASS, 25.0, "source: Finviz")


def test_source_and_missing_notes():
    f = good_fundamentals(roe_pct=None, sources={"market_cap": "Finviz"}, note="Finviz error: x")
    results = fundamental(f, prices(), CFG)
    assert by_name(results, "ROE").note == "missing data; Finviz error: x"
    assert by_name(results, "Market cap").note == "source: Finviz"


def test_finviz_dividend_preferred_over_history():
    results = fundamental(good_fundamentals(dividend_yield_pct=0.31), prices(), CFG)
    assert by_name(results, "Dividend").status == Status.FAIL


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
    assert r == {"Relative": Status.PASS, "Donchian": Status.FAIL, "Consolidation": Status.PASS,
                 "Breakout": Status.FAIL, "DMI": Status.FAIL, "SMA": Status.PASS}  # fmt: skip


def _weeks(highs, lows, volumes, end="2026-10-16"):
    """Daily bars, one per weekday, from weekly (high, low, volume); close = high."""
    days = pd.bdate_range(end=end, periods=5 * len(highs))
    rows = [
        (h, h, lo, h, v / 5)
        for h, lo, v in zip(highs, lows, volumes, strict=True)
        for _ in range(5)
    ]
    return pd.DataFrame(rows, index=days, columns=["Open", "High", "Low", "Close", "Volume"])


@pytest.mark.parametrize(
    "low,volume,expected",
    [
        (80, 300, (Status.PASS, Status.PASS, Status.PASS)),  # 20% base, breakout on volume
        (80, 50, (Status.PASS, Status.PASS, Status.FAIL)),  # no volume: not a valid breakout
        (40, 300, (Status.PASS, Status.FAIL, Status.PASS)),  # 60% correction: too deep
    ],
)
def test_breakout_needs_base_and_volume(low, volume, expected):
    daily = _weeks([100] * 10 + [110], [low] * 10 + [100], [100] * 10 + [volume])
    got = tuple(f(daily).status for f in (donchian_breakout, consolidation, breakout_volume))
    assert got == expected


def test_running_week_is_not_a_breakout():
    done = _weeks([100] * 11, [80] * 11, [100] * 11)
    monday = pd.DataFrame([[120, 120, 119, 120, 50]], columns=done.columns,
                          index=[pd.Timestamp("2026-10-19")])  # fmt: skip
    daily = pd.concat([done, monday])  # breaks out on Monday, week not closed yet
    assert donchian_breakout(daily).status == Status.FAIL


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
        TradePlan(entry=10, stop=9, target=13, shares=0, discarded="0 shares"),
    ],
)
def test_verdict_invalid_plan_blocks(plan):
    assert verdict(FUND, TECH, EARN, plan)[0] == Verdict.NO_BUY


def test_allow_missing_skips_fundamental_nd_only():
    assert verdict(FUND, TECH, EARN, PLAN, allow_missing=True) == (Verdict.BUY, [])
    fund = [*FUND]
    fund[3] = CriterionResult("inst", Status.ND, None, "")
    # never a plain BUY with missing data: BUY* lists what was skipped
    assert verdict(fund, TECH, EARN, PLAN, allow_missing=True) == (
        Verdict.BUY_INCOMPLETE,
        ["inst: N/D"],
    )
    fund[2] = CriterionResult("roe", Status.FAIL, 1, "")
    assert verdict(fund, TECH, EARN, PLAN, allow_missing=True)[0] == Verdict.NO_BUY
    earn = CriterionResult("earnings", Status.ND, None, "")
    assert verdict(FUND, TECH, earn, PLAN, allow_missing=True)[0] == Verdict.NO_BUY


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_value_is_nd(value):
    c = CriterionResult("SMA 200d", Status.PASS, value, "> 10", "x")
    assert (c.status, c.value, c.note) == (Status.ND, None, "x; non-finite value")


def test_analysis_error_stays_with_its_ticker(fake_yf):
    class Broken(YahooProvider):
        def history(self, t):
            df = super().history(t)
            return df if t == "^GSPC" else df.drop(columns="High")  # malformed prices

    cfg = load(Path("does-not-exist.toml"))
    (r,) = analyze_many(["HZO"], Broken(), cfg, date(2026, 10, 20))
    assert r.verdict == Verdict.NO_BUY and r.error and r.reasons[0].startswith("Analysis error")


def _closes(*values, end="2026-10-20"):
    return pd.DataFrame({"Close": values}, index=pd.bdate_range(end=end, periods=len(values)))


@pytest.mark.parametrize(
    "closes,end,last,amc,status",
    [
        # report Mon 10-19 after the close: reaction is Tue 10-20 (+2%), 1 session is enough
        ((100, 100, 100, 100, 102), "2026-10-20", date(2026, 10, 19), True, Status.PASS),
        # same report, the reaction session is not in the data yet
        ((100, 100, 100, 100), "2026-10-19", date(2026, 10, 19), True, Status.FAIL),
        # before the open on 10-16: +8% reaction, only 3 sessions of the 5 needed
        ((100, 100, 108, 107, 109), "2026-10-20", date(2026, 10, 16), False, Status.FAIL),
        # -6% reaction 5 sessions ago: waited enough
        ((100, 94, 95, 96, 97, 96), "2026-10-20", date(2026, 10, 14), False, Status.PASS),
    ],
)
def test_post_earnings_waits_for_reaction(closes, end, last, amc, status):
    assert post_earnings(last, amc, _closes(*closes, end=end)).status == status


def test_post_earnings_unknown_date():
    daily = _closes(100, 101)
    assert post_earnings(None, None, daily, "Finviz").status == Status.PASS  # next announced
    assert post_earnings(None, None, daily, "Yahoo").status == Status.ND
