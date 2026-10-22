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
    return f if math.isfinite(f) else None


def _row(stmt: pd.DataFrame, *names: str) -> list[float | None]:
    """First existing row among names, most recent quarter first."""
    for name in names:
        if name in stmt.index:
            row = stmt.loc[name].sort_index(ascending=False)
            return [_num(v) for v in row]
    return []


def session_end(metadata: dict) -> pd.Timestamp | None:
    """Today's regular close from Yahoo (13:00 on early-close days), New York time."""
    end = ((metadata or {}).get("currentTradingPeriod") or {}).get("regular", {}).get("end")
    if end is None:
        return None
    # yfinance 1.7 gives a tz-aware Timestamp; the raw Yahoo API gives epoch seconds
    ts = pd.Timestamp(end, unit="s") if isinstance(end, int | float) else pd.Timestamp(end)
    return (ts if ts.tzinfo else ts.tz_localize("UTC")).tz_convert(MARKET_TZ)


def drop_partial_bar(
    df: pd.DataFrame, now: pd.Timestamp, close: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Drop today's bar while the session is still open: the method uses end-of-day data.

    `now` is New York time; `close` is today's session end when Yahoo gives it, else 16:00.
    """
    if not len(df) or df.index[-1].date() != now.date():
        return df
    if close is not None and close.date() == now.date():
        still_open = now < close
    else:
        still_open = now.hour < MARKET_CLOSE_HOUR
    return df.iloc[:-1] if still_open else df


class YahooProvider:
    def history(self, ticker: str) -> pd.DataFrame:
        t = yf.Ticker(ticker)
        df = t.history(period=HISTORY_PERIOD, auto_adjust=True)
        if df.empty:
            raise DataError(f"{ticker}: no prices from Yahoo")
        # thresholds and the S&P 500 benchmark are in USD: other currencies would mix units
        meta = t.history_metadata or {}
        currency = meta.get("currency")
        if currency != "USD":
            raise DataError(f"{ticker}: quoted in {currency or 'unknown currency'}, not USD")
        df = df.dropna(subset=["Open", "High", "Low", "Close"])  # incomplete rows = missing data
        df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
        df = drop_partial_bar(df, pd.Timestamp.now(tz=MARKET_TZ), session_end(meta))
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
            operating_income=_row(stmt, "Operating Income"),
            roe_pct=None if roe is None else roe * 100,
            market_cap=_num(info.get("marketCap")),
            next_earnings=dates[0] if dates else None,
            inst_own_pct=None if inst is None else inst * 100,
        )
