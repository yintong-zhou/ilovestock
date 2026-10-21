"""Daily disk cache in front of any MarketDataProvider (yfinance is rate-limited)."""

import dataclasses
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

from ilovestock.models import Fundamentals
from ilovestock.providers.base import MarketDataProvider
from ilovestock.providers.yahoo import MARKET_CLOSE_HOUR, MARKET_TZ

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "ilovestock"


def session_tag(now: pd.Timestamp) -> str:
    """New York date, with '-open' before the close: prices cached intraday lack today's bar,
    so they are refetched once the session closes."""
    return f"{now:%Y-%m-%d}" + ("-open" if now.hour < MARKET_CLOSE_HOUR else "")


def _replace(path: Path, write) -> None:
    """Write next to the target, then swap: readers never see a half-written file."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    write(tmp)
    os.replace(tmp, path)


class CachedProvider:
    """Files are keyed by day: data is re-downloaded once per day.

    ponytail: old files are never pruned; add cleanup if the folder grows too much.
    """

    def __init__(self, inner: MarketDataProvider, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.inner = inner
        self.dir = cache_dir

    def _path(self, ticker: str, kind: str, ext: str, tag: str | None = None) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        return self.dir / f"{tag or f'{date.today():%Y-%m-%d}'}_{ticker}_{kind}.{ext}"

    def history(self, ticker: str) -> pd.DataFrame:
        path = self._path(ticker, "history", "csv", session_tag(pd.Timestamp.now(tz=MARKET_TZ)))
        if path.exists():
            return pd.read_csv(path, index_col=0, parse_dates=True)
        df = self.inner.history(ticker)
        _replace(path, df.to_csv)
        return df

    def fundamentals(self, ticker: str) -> Fundamentals:
        path = self._path(ticker, "fundamentals", "json")
        if path.exists():
            try:
                raw = json.loads(path.read_text())
                for k in ("next_earnings", "last_earnings", "fetched"):
                    if raw.get(k):
                        raw[k] = date.fromisoformat(raw[k])
                return Fundamentals(**raw)
            except (ValueError, KeyError, TypeError):  # corrupt or older format: refetch
                pass
        f = self.inner.fundamentals(ticker)
        _replace(path, lambda p: p.write_text(json.dumps(dataclasses.asdict(f), default=str)))
        return f
