"""Technical indicators as pure functions on pandas Series/DataFrames.

Parameters are fixed course constants, never options: per-case tuning is a mistake per the course.
"""

import numpy as np
import pandas as pd

SMA_DAYS = 200
DONCHIAN_WEEKS = 10
DONCHIAN_FAST_WEEKS = 8  # faster trailing exit (informational)
DMI_DAYS = 18
RS_SMA_WEEKS = 52


def weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Daily OHLCV -> weekly bars ending Friday. The last bar may be the running week."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return daily[list(agg)].resample("W-FRI").agg(agg).dropna(subset=["Close"])


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def donchian(high: pd.Series, low: pd.Series, n: int) -> tuple[pd.Series, pd.Series]:
    """(upper, lower): max high / min low of the n PREVIOUS bars (current bar excluded)."""
    return high.rolling(n).max().shift(1), low.rolling(n).min().shift(1)


def dmi(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> pd.DataFrame:
    """+DI, -DI, ADX with Wilder smoothing (EMA alpha=1/n). Columns: plus_di, minus_di, adx."""
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0).where(up.notna())
    minus_dm = down.where((down > up) & (down > 0), 0.0).where(down.notna())
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1)
    tr = tr.max(axis=1).where(prev_close.notna())

    def wilder(s: pd.Series) -> pd.Series:
        return s.ewm(alpha=1 / n, adjust=False).mean()

    atr = wilder(tr)
    plus_di = 100 * wilder(plus_dm) / atr
    minus_di = 100 * wilder(minus_dm) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": wilder(dx)})


def relative_strength(close: pd.Series, benchmark: pd.Series) -> pd.Series:
    """Price / benchmark on common dates."""
    a, b = close.align(benchmark, join="inner")
    return a / b
