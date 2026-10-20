"""The 4 technical confirmations, fixed parameters. Not enough history -> N/D."""

import pandas as pd

from ilovestock import indicators as ind
from ilovestock.models import CriterionResult, Status

MIN_DMI_BARS = 10 * ind.DMI_DAYS  # Wilder smoothing needs a long warm-up to be stable


def _nd(name: str, threshold: str, note: str = "not enough history") -> CriterionResult:
    return CriterionResult(name, Status.ND, None, threshold, note)


def _ok(cond: bool) -> Status:
    return Status.PASS if cond else Status.FAIL


def relative_strength(daily: pd.DataFrame, bench_close: pd.Series) -> CriterionResult:
    name, thr = "Relative strength vs S&P 500 (w)", f"RS > SMA {ind.RS_SMA_WEEKS}w"
    rs = ind.relative_strength(daily["Close"], bench_close)
    rs_w = rs.resample("W-FRI").last().dropna()
    if len(rs_w) < ind.RS_SMA_WEEKS:
        return _nd(name, thr)
    rs_sma = ind.sma(rs_w, ind.RS_SMA_WEEKS).iloc[-1]
    last = rs_w.iloc[-1]
    return CriterionResult(name, _ok(last > rs_sma), round(last / rs_sma, 3), thr, "value = RS/SMA")


def donchian_breakout(daily: pd.DataFrame) -> CriterionResult:
    name, thr = f"Donchian {ind.DONCHIAN_WEEKS}w", "price > upper band"
    w = ind.weekly(daily)
    if len(w) <= ind.DONCHIAN_WEEKS:
        return _nd(name, thr)
    upper, _ = ind.donchian(w["High"], w["Low"], ind.DONCHIAN_WEEKS)
    price = daily["Close"].iloc[-1]
    return CriterionResult(
        name, _ok(price > upper.iloc[-1]), round(price, 2), f"> {upper.iloc[-1]:.2f}"
    )


def directional_movement(daily: pd.DataFrame) -> CriterionResult:
    name, thr = f"DMI {ind.DMI_DAYS}d", "ADX rising and below +DI and -DI"
    if len(daily) < MIN_DMI_BARS:
        return _nd(name, thr)
    d = ind.dmi(daily["High"], daily["Low"], daily["Close"], ind.DMI_DAYS)
    adx, prev_adx = d["adx"].iloc[-1], d["adx"].iloc[-2]
    plus, minus = d["plus_di"].iloc[-1], d["minus_di"].iloc[-1]
    cond = adx > prev_adx and adx < plus and adx < minus
    value = f"ADX {adx:.1f} (prev. {prev_adx:.1f}), +DI {plus:.1f}, -DI {minus:.1f}"
    return CriterionResult(name, _ok(cond), value, thr)


def above_sma(daily: pd.DataFrame) -> CriterionResult:
    name, thr = f"SMA {ind.SMA_DAYS}d", "price > SMA"
    if len(daily) < ind.SMA_DAYS:
        return _nd(name, thr)
    level = ind.sma(daily["Close"], ind.SMA_DAYS).iloc[-1]
    price = daily["Close"].iloc[-1]
    return CriterionResult(name, _ok(price > level), round(price, 2), f"> {level:.2f}")


def technical(daily: pd.DataFrame, bench_close: pd.Series) -> list[CriterionResult]:
    return [
        relative_strength(daily, bench_close),
        donchian_breakout(daily),
        directional_movement(daily),
        above_sma(daily),
    ]
