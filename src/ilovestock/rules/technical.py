"""Technical confirmations, fixed parameters. Not enough history -> N/D.

Weekly signals use completed weeks only: the method confirms a breakout on the weekly close.
"""

import pandas as pd

from ilovestock import indicators as ind
from ilovestock.models import CriterionResult, Status

MIN_DMI_BARS = 10 * ind.DMI_DAYS  # Wilder smoothing needs a long warm-up to be stable
MAX_CORRECTION_PCT = 50  # method: consolidation correction < 50% (< 38% for short bases)


def _nd(name: str, threshold: str, note: str = "not enough history") -> CriterionResult:
    return CriterionResult(name, Status.ND, None, threshold, note)


def _ok(cond: bool) -> Status:
    return Status.PASS if cond else Status.FAIL


def relative_strength(daily: pd.DataFrame, bench_close: pd.Series) -> CriterionResult:
    name, thr = "Relative strength vs S&P 500 (w)", f"RS > SMA {ind.RS_SMA_WEEKS}w"
    rs = ind.relative_strength(daily["Close"], bench_close)
    rs_w = ind.drop_running_week(rs.resample("W-FRI").last().dropna(), daily.index[-1])
    if len(rs_w) < ind.RS_SMA_WEEKS:
        return _nd(name, thr)
    rs_sma = ind.sma(rs_w, ind.RS_SMA_WEEKS).iloc[-1]
    last = rs_w.iloc[-1]
    return CriterionResult(name, _ok(last > rs_sma), round(last / rs_sma, 3), thr, "value = RS/SMA")


def donchian_breakout(daily: pd.DataFrame) -> CriterionResult:
    name, thr = f"Donchian {ind.DONCHIAN_WEEKS}w", "weekly close > upper band"
    w = ind.completed_weeks(daily)
    if len(w) <= ind.DONCHIAN_WEEKS:
        return _nd(name, thr)
    upper, _ = ind.donchian(w["High"], w["Low"], ind.DONCHIAN_WEEKS)
    close = w["Close"].iloc[-1]
    note = f"week of {w.index[-1]:%Y-%m-%d}"
    return CriterionResult(
        name, _ok(close > upper.iloc[-1]), round(close, 2), f"> {upper.iloc[-1]:.2f}", note
    )


def _base(w: pd.DataFrame) -> pd.DataFrame:
    """The consolidation: the weeks before the last completed (breakout) week."""
    return w.iloc[-ind.DONCHIAN_WEEKS - 1 : -1]


def consolidation(daily: pd.DataFrame) -> CriterionResult:
    name, thr = f"Consolidation {ind.DONCHIAN_WEEKS}w", f"correction < {MAX_CORRECTION_PCT}%"
    w = ind.completed_weeks(daily)
    if len(w) <= ind.DONCHIAN_WEEKS:
        return _nd(name, thr)
    hi, lo = _base(w)["High"].max(), _base(w)["Low"].min()
    depth = (hi - lo) / hi * 100
    note = "value = correction %" + ("; < 38%: tight base" if depth < 38 else "")
    return CriterionResult(name, _ok(depth < MAX_CORRECTION_PCT), round(depth, 1), thr, note)


def breakout_volume(daily: pd.DataFrame) -> CriterionResult:
    name, thr = "Breakout volume", f"week > {ind.DONCHIAN_WEEKS}w average"
    w = ind.completed_weeks(daily)
    if len(w) <= ind.DONCHIAN_WEEKS:
        return _nd(name, thr)
    ratio = w["Volume"].iloc[-1] / _base(w)["Volume"].mean()  # 0 average -> inf -> N/D
    return CriterionResult(name, _ok(ratio > 1), round(ratio, 2), thr, "value = week / average")


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
        consolidation(daily),
        breakout_volume(daily),
        directional_movement(daily),
        above_sma(daily),
    ]
