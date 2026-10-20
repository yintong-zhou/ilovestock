"""yfinance provider: prices, quarterly financials, next earnings date. Unofficial source."""

import math
from datetime import date

import pandas as pd
import yfinance as yf

from ilovestock.models import Fundamentals
from ilovestock.providers.base import DataError

HISTORY_PERIOD = "2y"  # enough for SMA 200d, RS SMA 52w, DMI warm-up
COLUMNS = ["Open", "High", "Low", "Close", "Volume", "Dividends"]


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


class YahooProvider:
    def history(self, ticker: str) -> pd.DataFrame:
        df = yf.Ticker(ticker).history(period=HISTORY_PERIOD, auto_adjust=True)
        if df.empty:
            raise DataError(f"{ticker}: nessun prezzo da Yahoo")
        df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
        return df.reindex(columns=COLUMNS)

    def fundamentals(self, ticker: str) -> Fundamentals:
        t = yf.Ticker(ticker)
        stmt = t.quarterly_income_stmt
        info = t.info or {}
        roe = _num(info.get("returnOnEquity"))
        dates = (t.calendar or {}).get("Earnings Date") or []
        # past or stale dates are handled by the earnings rule (-> N/D)
        dates = sorted(d for d in dates if isinstance(d, date))
        return Fundamentals(
            sales=_row(stmt, "Total Revenue"),
            eps=_row(stmt, "Diluted EPS", "Basic EPS"),
            roe_pct=None if roe is None else roe * 100,
            market_cap=_num(info.get("marketCap")),
            next_earnings=dates[0] if dates else None,
        )
