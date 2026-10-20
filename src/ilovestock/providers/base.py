"""Provider interface: any source implementing it can replace yfinance without touching rules."""

from typing import Protocol

import pandas as pd

from ilovestock.models import Fundamentals

BENCHMARK = "^GSPC"  # S&P 500


class DataError(Exception):
    """Data source returned nothing usable for a ticker."""


class MarketDataProvider(Protocol):
    def history(self, ticker: str) -> pd.DataFrame:
        """Daily adjusted OHLCV + Dividends, tz-naive DatetimeIndex, oldest first."""
        ...

    def fundamentals(self, ticker: str) -> Fundamentals: ...
