"""Indicators vs an independent implementation (TA-Lib) on a real recorded price series."""

import numpy as np
import pandas as pd
import talib

from ilovestock import indicators as ind


def test_sma_matches_talib(hzo_daily):
    c = hzo_daily["Close"]
    np.testing.assert_allclose(ind.sma(c, 200), talib.SMA(c, 200), equal_nan=True)


def test_dmi_matches_talib_after_warmup(hzo_daily):
    h, lo, c = hzo_daily["High"], hzo_daily["Low"], hzo_daily["Close"]
    d = ind.dmi(h, lo, c, ind.DMI_DAYS).iloc[-200:]
    ref = pd.DataFrame(
        {
            "plus_di": talib.PLUS_DI(h, lo, c, ind.DMI_DAYS),
            "minus_di": talib.MINUS_DI(h, lo, c, ind.DMI_DAYS),
            "adx": talib.ADX(h, lo, c, ind.DMI_DAYS),
        }
    ).iloc[-200:]
    np.testing.assert_allclose(d, ref, atol=1e-3)


def test_donchian_uses_previous_bars_only(hzo_daily):
    w = ind.weekly(hzo_daily)
    upper, lower = ind.donchian(w["High"], w["Low"], 10)
    np.testing.assert_allclose(upper, talib.MAX(w["High"], 10).shift(1), equal_nan=True)
    np.testing.assert_allclose(lower, talib.MIN(w["Low"], 10).shift(1), equal_nan=True)


def test_donchian_small_example():
    high = pd.Series([1.0, 3, 2, 5, 4])
    upper, _ = ind.donchian(high, high, 3)
    assert upper.tolist()[3:] == [3, 5]  # max of the 3 bars before, current excluded


def test_weekly_bars(hzo_daily):
    w = ind.weekly(hzo_daily)
    assert (w.index.dayofweek == 4).all()
    first = hzo_daily.loc[: w.index[1]].loc[w.index[0] + pd.Timedelta(days=1) :]
    assert w["High"].iloc[1] == first["High"].max()
    assert w["Close"].iloc[1] == first["Close"].iloc[-1]


def test_relative_strength_aligns_dates():
    a = pd.Series([2.0, 4.0, 6.0], index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"]))
    b = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    assert ind.relative_strength(a, b).tolist() == [4.0, 3.0]
