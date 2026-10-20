"""yfinance provider: prices, quarterly financials, next earnings date. Unofficial source."""

import math
from datetime import date

import pandas as pd
import yfinance as yf

from ilovestock.models import Fundamentals
from ilovestock.providers.base import DataError

HISTORY_PERIOD = "2y"  # enough for SMA 200d, RS SMA 52w, DMI warm-up
COLUMNS = ["Open", "High", "Low", "Close", "Volume", "Dividends"]
MARKET_TZ = "America/New_York"
MARKET_CLOSE_HOUR = 16  # NYSE/NASDAQ regular close, New York time


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _row(stmt: pd.DataFrame, *names: str) -> list[float | None]:
    """First existing row among names, most recent quarter first."""
    for name in names:
        if name in stmt.index:
            row = stmt.loc[name].sort_index(ascending=False)
            return [_num(v) for v in row]
    return []


def drop_partial_bar(df: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Drop today's bar while the session is still open: the method uses end-of-day data.

    `now` is New York time. ponytail: early-close days (13:00) keep dropping the bar until 16:00.
    """
    if len(df) and df.index[-1].date() == now.date() and now.hour < MARKET_CLOSE_HOUR:
        return df.iloc[:-1]
    return df


class YahooProvider:
    def history(self, ticker: str) -> pd.DataFrame:
        df = yf.Ticker(ticker).history(period=HISTORY_PERIOD, auto_adjust=True)
        if df.empty:
            raise DataError(f"{ticker}: no prices from Yahoo")
        df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
        df = drop_partial_bar(df, pd.Timestamp.now(tz=MARKET_TZ))
        if df.empty:
            raise DataError(f"{ticker}: no complete daily bar from Yahoo")
        return df.reindex(columns=COLUMNS)

    def fundamentals(self, ticker: str) -> Fundamentals:
        t = yf.Ticker(ticker)
        stmt = t.quarterly_income_stmt
        info = t.info or {}
        roe = _num(info.get("returnOnEquity"))
        inst = _num(info.get("heldPercentInstitutions"))
        dates = (t.calendar or {}).get("Earnings Date") or []
        # past or stale dates are handled by the earnings rule (-> N/D)
        dates = sorted(d for d in dates if isinstance(d, date))
        return Fundamentals(
            sales=_row(stmt, "Total Revenue"),
            eps=_row(stmt, "Diluted EPS", "Basic EPS"),
            roe_pct=None if roe is None else roe * 100,
            market_cap=_num(info.get("marketCap")),
            next_earnings=dates[0] if dates else None,
            inst_own_pct=None if inst is None else inst * 100,
        )
