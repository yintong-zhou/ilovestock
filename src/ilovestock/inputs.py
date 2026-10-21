"""Ticker inputs: CLI args, watchlist file, Finviz screener. Final list = ordered union."""

import re
from pathlib import Path

TICKER_RE = re.compile(r"^[A-Z0-9.\-^]{1,10}$")
HEADERS = {"TICKER", "SYMBOL"}
MAX_TICKERS = 50  # one run: bounds Finviz/Yahoo requests, cache and history growth


def normalize(ticker: str) -> str:
    t = ticker.strip().upper()
    if not TICKER_RE.match(t):
        raise ValueError(f"invalid ticker: {ticker!r}")
    return t


def read_watchlist(path: Path) -> list[str]:
    """One ticker per line (txt) or first column (csv). Blank lines, # comments, header skipped."""
    tickers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cell = line.split("#")[0].split(",")[0].strip().strip('"')
        if cell and cell.upper() not in HEADERS:
            tickers.append(normalize(cell))
    return tickers


def merge(*lists: list[str]) -> list[str]:
    return list(dict.fromkeys(t for lst in lists for t in lst))
