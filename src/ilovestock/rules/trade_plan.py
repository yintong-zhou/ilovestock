"""Trade plan: entry, technical stop, take profit in R multiples, position sizing.

Defaults chosen for open decisions (configurable where the course allows):
- D5 stop: lowest low of the previous 10 weeks (the consolidation low = lower Donchian band).
- D6 entry: breakout = last close (price already above the band); pullback = retest of the
  upper Donchian band; restart = above the previous completed week's high.
"""

import math

import pandas as pd

from ilovestock import indicators as ind
from ilovestock.config import Config
from ilovestock.models import TradePlan

MIN_R_MULTIPLE = 2.0


def risk_band(risk_pct: float) -> str:
    if risk_pct < 0.5:
        return "very conservative"
    if risk_pct <= 1:
        return "moderate"
    return "aggressive"


def size_position(
    capital: float, risk_pct: float, max_position_pct: float, entry: float, stop: float
) -> tuple[int, str]:
    """(shares, binding). shares = floor(max_loss / (entry - stop)), capped by exposure."""
    max_loss = capital * risk_pct / 100
    # round() absorbs float noise like 100 / (50.2 - 50.1) = 999.99999
    by_risk = math.floor(round(max_loss / (entry - stop), 6))
    by_cap = math.floor(round(capital * max_position_pct / 100 / entry, 6))
    return (by_cap, "exposure") if by_cap < by_risk else (by_risk, "risk")


def entry_level(daily: pd.DataFrame, weekly: pd.DataFrame, upper: pd.Series, mode: str) -> float:
    if mode == "pullback":
        return float(upper.iloc[-1])
    if mode == "restart":
        return float(weekly["High"].iloc[-2])
    return float(daily["Close"].iloc[-1])


def consolidation_info(w: pd.DataFrame) -> list[str]:
    """D7: informational only, does not affect the verdict."""
    base = w.iloc[-ind.DONCHIAN_WEEKS - 1 : -1]
    hi, lo = base["High"].max(), base["Low"].min()
    depth = (hi - lo) / hi * 100
    label = "< 38%" if depth < 38 else "< 50%" if depth < 50 else ">= 50% (too deep)"
    vol_ratio = w["Volume"].iloc[-1] / base["Volume"].mean()
    return [
        f"Consolidation correction {ind.DONCHIAN_WEEKS}w: {depth:.1f}% ({label})",
        f"Current week volume / {ind.DONCHIAN_WEEKS}w average: {vol_ratio:.2f}x",
    ]


def trade_plan(daily: pd.DataFrame, cfg: Config) -> TradePlan | None:
    """None if there is not enough weekly history to place entry and stop."""
    w = ind.weekly(daily)
    if len(w) <= ind.DONCHIAN_WEEKS:
        return None
    upper, lower = ind.donchian(w["High"], w["Low"], ind.DONCHIAN_WEEKS)
    _, lower_fast = ind.donchian(w["High"], w["Low"], ind.DONCHIAN_FAST_WEEKS)
    entry = round(entry_level(daily, w, upper, cfg.entry_mode), 2)
    stop = round(float(lower.iloc[-1]), 2)
    plan = TradePlan(
        entry=entry,
        stop=stop,
        max_loss=round(cfg.capital * cfg.risk_pct / 100, 2),
        risk_band=risk_band(cfg.risk_pct),
        trailing_stop_10w=stop,
        trailing_stop_8w=round(float(lower_fast.iloc[-1]), 2),
        info=consolidation_info(w),
    )
    risk = entry - stop
    if risk <= 0:
        plan.discarded = f"entry {entry} <= stop {stop}"
        return plan
    plan.target = round(entry + cfg.r_multiple * risk, 2)
    plan.shares, plan.binding = size_position(
        cfg.capital, cfg.risk_pct, cfg.max_position_pct, entry, stop
    )
    plan.effective_risk = round(plan.shares * risk, 2)
    plan.position_value = round(plan.shares * entry, 2)
    plan.info.append(
        f"Scale-out: ½ at {entry + risk:.2f} (1R), ½ above {entry + 3 * risk:.2f} (3R)"
    )
    if cfg.r_multiple < MIN_R_MULTIPLE:
        plan.discarded = f"R:R {cfg.r_multiple:g} < {MIN_R_MULTIPLE:g}"
    elif plan.shares < 1:
        plan.discarded = "0 shares: capital or risk too low for this stop"
    return plan
