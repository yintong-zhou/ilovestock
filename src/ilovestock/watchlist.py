"""Web app watchlist: stocks the user might buy.

A plain list, one ticker per line, so the terminal reads the same file:
`ilovestock analyze --watchlist ~/.config/ilovestock/watchlist.txt`.
"""

import os
import threading
from pathlib import Path

from ilovestock import inputs
from ilovestock.config import CONFIG_PATH

WATCHLIST_PATH = CONFIG_PATH.parent / "watchlist.txt"
MAX = inputs.MAX_TICKERS  # one analysis run covers the whole list
HEADER = "# ilovestock watchlist: one ticker per line"
_lock = threading.Lock()  # web routes run in a thread pool: one read-modify-write at a time


class WatchlistError(ValueError):
    pass


def read(path: Path | None = None) -> list[str]:
    """Tickers in the order they were added. A hand-edited bad line raises ValueError."""
    path = path or WATCHLIST_PATH
    return inputs.merge(inputs.read_watchlist(path)) if path.exists() else []


def _write(tickers: list[str], path: Path) -> list[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join([HEADER, *tickers]) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # a crash mid-write never leaves a half file
    return tickers


def add(ticker: str, path: Path | None = None) -> list[str]:
    path = path or WATCHLIST_PATH
    t = inputs.normalize(ticker)
    with _lock:
        tickers = read(path)
        if t in tickers:
            return tickers
        if len(tickers) >= MAX:
            raise WatchlistError(f"Watchlist full: max {MAX} tickers")
        return _write([*tickers, t], path)


def remove(ticker: str, path: Path | None = None) -> list[str]:
    path = path or WATCHLIST_PATH
    with _lock:
        return _write([t for t in read(path) if t != ticker.strip().upper()], path)
