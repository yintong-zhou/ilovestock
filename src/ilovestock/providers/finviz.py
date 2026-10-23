"""Finviz: main source for fundamentals (via the `finviz` lib) and screener ticker import.

Finviz has no price history, so prices come from the fallback provider (Yahoo). Each
fundamental field falls back to Yahoo when Finviz lacks it; the source is recorded per field.
Unofficial scraping: Finviz ToS may forbid it, quotes are delayed 15-20 min.
"""

import dataclasses
import math
import re
from collections.abc import Iterator
from datetime import date, datetime

import finviz
import pandas as pd
import requests

from ilovestock.models import Fundamentals
from ilovestock.providers.base import HISTORY_PERIOD, MarketDataProvider

WARNING = (
    "Finviz: unofficial source (scraping), use may violate Finviz ToS; quotes delayed 15-20 min."
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PAGE_SIZE = 20
OVERLAP = 5  # rows read twice per page: a stock rising up to 5 places between requests is seen
SUFFIX = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}

# Keys and formats verified on real get_stock() responses (tests/fixtures/*_finviz.json).
# Finviz "Q/Q" growth fields are YoY (same quarter last year), per Finviz help.
KEYS = {
    "sales_growth_yoy_pct": "Sales Q/Q",  # "-6.98%"
    "eps_growth_yoy_pct": "EPS Q/Q",  # "127.37%"
    "roe_pct": "ROE",  # "0.42%"
    "inst_own_pct": "Inst Own",  # "82.64%"
    "inst_trans_pct": "Inst Trans",  # "-1.02%"
    "roic_pct": "ROIC",  # "72.08%"
}
MARKET_CAP = "Market Cap"  # "1.15B"
DIVIDEND = "Dividend TTM"  # "1.06 (0.31%)"; "-" when none or missing
EARNINGS = "Earnings"  # "Nov 02 AMC": no year; the last report until the next is announced


class FinvizError(Exception):
    pass


class TooManyResults(FinvizError):
    def __init__(self, message: str, total: int):
        super().__init__(message)
        self.total = total


def _pct(value: str | None) -> float | None:
    """'82.64%' -> 82.64; '-', missing or non-finite -> None."""
    if not value:
        return None
    try:
        f = float(value.strip().rstrip("%"))
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def _money(value: str | None) -> float | None:
    """'1.15B' -> 1.15e9."""
    m = re.fullmatch(r"([\d.]+)([KMBT])", (value or "").strip())
    return float(m.group(1)) * SUFFIX[m.group(2)] if m else None


def _dividend_yield(value: str | None) -> float | None:
    """'1.06 (0.31%)' -> 0.31. '-' -> None: Finviz does not tell 'none' from 'missing'."""
    m = re.search(r"\(([\d.]+)%\)", value or "")
    return float(m.group(1)) if m else None


def _earnings_date(value: str | None, today: date) -> date | None:
    """'Nov 02 AMC' -> the occurrence nearest to today, in any year (past = last report)."""
    m = re.match(r"([A-Z][a-z]{2}) (\d{1,2})", (value or "").strip())
    if not m:
        return None
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(datetime.strptime(f"{m[1]} {m[2]} {year}", "%b %d %Y").date())
        except ValueError:  # Feb 29 in a non-leap year
            pass
    return min(candidates, key=lambda c: abs((c - today).days), default=None)


def parse_snapshot(data: dict, today: date) -> dict:
    """get_stock() dict -> Fundamentals field values (None when missing)."""
    values = {field: _pct(data.get(key)) for field, key in KEYS.items()}
    values["market_cap"] = _money(data.get(MARKET_CAP))
    values["dividend_yield_pct"] = _dividend_yield(data.get(DIVIDEND))
    raw = data.get(EARNINGS) or ""
    d = _earnings_date(raw, today)
    past = d is not None and d < today
    values["next_earnings"] = None if past else d
    values["last_earnings"] = d if past else None
    # no BMO/AMC: assume after the close, the later (safer) reaction day
    values["last_earnings_amc"] = ("BMO" not in raw) if past else None
    return values


class FinvizProvider:
    """Fundamentals from Finviz, per-field fallback to `fallback`; prices from `fallback`."""

    def __init__(self, fallback: MarketDataProvider, today: date | None = None):
        self.fallback = fallback
        self._today = today

    @property
    def today(self) -> date:
        """Read per call: `serve` keeps one provider alive across days."""
        return self._today or date.today()

    def history(self, ticker: str, period: str = HISTORY_PERIOD) -> pd.DataFrame:
        return self.fallback.history(ticker, period)

    def fundamentals(self, ticker: str) -> Fundamentals:
        notes = []  # a non-empty note keeps the snapshot out of the cache and the screener
        try:
            base = self.fallback.fundamentals(ticker)
        except Exception as e:
            base = Fundamentals(sales=[], eps=[], roe_pct=None, market_cap=None, next_earnings=None)
            notes.append(f"Yahoo error: {e}")
        sources = {
            k: "Yahoo"
            for k in ("roe_pct", "market_cap", "next_earnings", "inst_own_pct")
            if getattr(base, k) is not None
        }
        today = self.today
        try:
            fv = parse_snapshot(finviz.get_stock(ticker), today)
        except Exception as e:  # scraping: any site change surfaces here
            fv = {}
            notes.append(f"Finviz error: {e}")
        finally:  # the lib caches pages forever: drop it so the next call refetches
            finviz.main_func.STOCK_PAGE.pop(ticker, None)
        found = {k: v for k, v in fv.items() if v is not None}
        sources.update(dict.fromkeys(found, "Finviz"))
        note = "; ".join(notes)
        return dataclasses.replace(base, **found, sources=sources, note=note, fetched=today)


def parse_screener_page(html: str) -> tuple[list[str], int]:
    """Tickers on one screener page and the total result count."""
    total = re.search(r"#\d+ / (\d+) Total", html)
    tickers = dict.fromkeys(re.findall(r'href="/quote\?t=([A-Z0-9.\-]+)&', html))
    if tickers and not total:  # a total of 0 would silently stop the reading at page 1
        raise FinvizError("screener page changed: result count not found")
    return list(tickers), int(total.group(1)) if total else 0


def parse_screener_rows(html: str) -> list[tuple[str, float | None]]:
    """(ticker, market cap $) per row of an overview (v=111) page; '-' cap -> None."""
    cells = re.findall(
        r'data-row-key="([A-Z0-9.\-]+)".*?data-column-id="marketCap"[^>]*>([^<]*)<', html, re.S
    )
    return [(t, _money(cap)) for t, cap in cells]


def first_row_number(html: str) -> int | None:
    """Position of a screener page's first row (the 'No.' column)."""
    m = re.search(r'data-column-id="row"[^>]*>(\d+)<', html)
    return int(m.group(1)) if m else None


def screener_rows(url: str) -> Iterator[tuple[str, float | None]]:
    """Rows of one of our screener URLs, sorted by market cap descending, each ticker once.

    Pages are fetched only as the caller reads them. Caps move between two requests, so pages
    overlap by OVERLAP rows and the order is checked within a page (one snapshot), not across.
    """
    seen: set[str] = set()
    row, total = 1, 1
    while row <= total:
        resp = requests.get(url, params={"r": row}, headers={"User-Agent": UA}, timeout=30)
        resp.raise_for_status()
        rows = parse_screener_rows(resp.text)
        tickers, total = parse_screener_page(resp.text)
        if not rows:  # page 1 with no match, or any page we cannot read: never a silent end
            raise FinvizError("no rows: no stock matches the filters, or the Finviz page changed")
        if len(rows) != len(tickers):  # a row the parser missed would be silently dropped
            raise FinvizError("screener page changed: rows not recognized")
        if (first := first_row_number(resp.text)) != row:  # the overlap needs r as asked
            raise FinvizError(f"screener page changed: page starts at row {first}, not {row}")
        caps = [c for _, c in rows if c is not None]
        if caps != sorted(caps, reverse=True):  # stopping at the first nano needs this order
            raise FinvizError("Finviz rows not sorted by market cap: page changed")
        for t, cap in rows:
            if t not in seen:
                seen.add(t)
                yield t, cap
        row += PAGE_SIZE - OVERLAP


def screener_tickers(url: str, max_results: int | None = None) -> list[str]:
    """All tickers from a Finviz screener URL copied from the site.

    The `finviz` lib 2.0.0 Screener no longer parses the current site (row count markup
    changed), so we read the ticker links directly. Contract test: tests/test_providers.py (slow).
    With max_results, a larger screener is refused after the first page, not fully downloaded.
    """
    if not url.startswith("https://finviz.com/screener"):
        raise FinvizError("invalid URL: must start with https://finviz.com/screener")
    tickers: list[str] = []
    total, row = None, 1
    while total is None or row <= total:
        resp = requests.get(url, params={"r": row}, headers={"User-Agent": UA}, timeout=30)
        resp.raise_for_status()
        page, total = parse_screener_page(resp.text)
        if max_results is not None and total > max_results:
            raise TooManyResults(
                f"screener has {total} results: max {max_results}, narrow the filters", total
            )
        if not page:
            break
        tickers += page
        row += PAGE_SIZE
    if not tickers:
        raise FinvizError("no tickers found: filters with no results or page changed")
    return list(dict.fromkeys(tickers))
