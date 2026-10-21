"""Offline fakes from recorded responses in tests/fixtures (execution/record_fixtures.py)."""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

FIX = Path(__file__).parent / "fixtures"


def raw_history(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(FIX / f"{ticker}_history.csv", index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    return df


class FakeTicker:
    """Stands in for yfinance.Ticker with recorded data."""

    def __init__(self, ticker: str):
        self.ticker = ticker

    def history(self, **_):
        return raw_history(self.ticker)

    history_metadata = {"currency": "USD"}

    @property
    def quarterly_income_stmt(self):
        df = pd.read_csv(FIX / f"{self.ticker}_income.csv", index_col=0)
        df.columns = pd.to_datetime(df.columns)
        return df

    @property
    def info(self):
        return json.loads((FIX / f"{self.ticker}_info.json").read_text())

    @property
    def calendar(self):
        raw = json.loads((FIX / f"{self.ticker}_calendar.json").read_text())
        return {k: [date.fromisoformat(d) for d in v] for k, v in raw.items()}


@pytest.fixture
def fake_yf(monkeypatch):
    monkeypatch.setattr("ilovestock.providers.yahoo.yf.Ticker", FakeTicker)


@pytest.fixture
def hzo_daily(fake_yf):
    from ilovestock.providers.yahoo import YahooProvider

    return YahooProvider().history("HZO")


@pytest.fixture
def bench_close(fake_yf):
    from ilovestock.providers.yahoo import YahooProvider

    return YahooProvider().history("^GSPC")["Close"]


def fake_get_stock(ticker: str) -> dict:
    path = FIX / f"{ticker}_finviz.json"
    if not path.exists():
        raise RuntimeError(f"no Finviz page for {ticker}")
    return json.loads(path.read_text())


@pytest.fixture
def fake_finviz(monkeypatch):
    monkeypatch.setattr("ilovestock.providers.finviz.finviz.get_stock", fake_get_stock)
