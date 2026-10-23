from dataclasses import replace
from pathlib import Path

import pytest

from ilovestock import indicators as ind
from ilovestock.config import ConfigError, load
from ilovestock.rules.trade_plan import entry_level, risk_band, size_position, trade_plan

CFG = load(Path("does-not-exist.toml"))


# Method examples. max_loss 100 = capital 10,000 x 1%; cap 100% so it never binds.
def test_sizing_method_example_20_shares():
    assert size_position(10_000, 1, 100, entry=50, stop=45) == (20, "risk")


def test_sizing_method_example_100_shares():
    assert size_position(10_000, 1, 100, entry=50, stop=49) == (100, "risk")


def test_sizing_method_example_exposure_cap_40_shares():
    # capital 20,000, risk 0.5% -> max_loss 100; cap 10% -> 2,000 -> 40 shares at 50
    shares, binding = size_position(20_000, 0.5, 10, entry=50, stop=49)
    assert (shares, binding) == (40, "exposure")
    assert shares * (50 - 49) == 40  # effective risk 40 instead of 100


def test_sizing_float_noise():
    assert size_position(100_000, 0.1, 100, entry=50.2, stop=50.1)[0] == 1000  # 999.99999999998 raw


@pytest.mark.parametrize("risk_pct", [2.01, 5, 0, -1])
def test_risk_pct_out_of_range_rejected(risk_pct):
    with pytest.raises(ConfigError):
        load(Path("does-not-exist.toml"), {"risk_pct": risk_pct})


def test_risk_bands():
    assert [risk_band(x) for x in (0.3, 0.5, 1, 1.5, 2)] == [
        "very conservative", "moderate", "moderate", "aggressive", "aggressive"
    ]  # fmt: skip


def test_plan_on_recorded_data(hzo_daily):
    p = trade_plan(hzo_daily, CFG)
    assert p.entry == round(hzo_daily["Close"].iloc[-1], 2)
    assert p.stop < p.entry
    assert p.target == pytest.approx(p.entry + 3 * (p.entry - p.stop), abs=0.011)
    assert p.shares >= 1 and p.position_value <= CFG.capital * CFG.max_position_pct / 100
    assert p.effective_risk <= p.max_loss
    assert p.discarded is None


def test_plan_r_multiple_below_2_discarded(hzo_daily):
    p = trade_plan(hzo_daily, replace(CFG, r_multiple=1.5))
    assert p.discarded and "R:R" in p.discarded


def test_plan_zero_shares_discarded(hzo_daily):
    p = trade_plan(hzo_daily, replace(CFG, capital=10))
    assert p.shares == 0 and p.discarded


@pytest.mark.parametrize("mode", ["pullback", "restart"])
def test_entry_modes(hzo_daily, mode):
    assert (
        trade_plan(hzo_daily, replace(CFG, entry_mode=mode)).entry
        != trade_plan(hzo_daily, CFG).entry
    )


def test_plan_needs_history(hzo_daily):
    assert trade_plan(hzo_daily.iloc[-20:], CFG) is None


@pytest.mark.parametrize(
    "last_day,week",
    [
        ("2026-10-16", -1),  # data ends Friday: that week is complete, it is the previous one
        ("2026-10-19", -2),  # Monday: the last bar is the running week
    ],
)
def test_restart_uses_last_completed_week(hzo_daily, last_day, week):
    daily = hzo_daily.loc[:last_day]
    w = ind.weekly(daily)
    assert entry_level(daily, w, w["High"], "restart") == w["High"].iloc[week]
