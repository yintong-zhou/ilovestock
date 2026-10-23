"""Provider interface: any source implementing it can replace yfinance without touching rules."""

from typing import Protocol

import pandas as pd

from ilovestock.models import Fundamentals

BENCHMARK = "^GSPC"  # S&P 500
HISTORY_PERIOD = "2y"  # enough for SMA 200d, RS SMA 52w, DMI warm-up


class DataError(Exception):
    """Data source returned nothing usable for a ticker."""


class MarketDataProvider(Protocol):
    def history(self, ticker: str, period: str = HISTORY_PERIOD) -> pd.DataFrame:
        """Daily adjusted OHLCV + Dividends over `period` (yfinance code), tz-naive DatetimeIndex,
        oldest first."""
        ...

    def fundamentals(self, ticker: str) -> Fundamentals: ...
