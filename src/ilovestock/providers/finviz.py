"""Finviz: main source for fundamentals (via the `finviz` lib) and screener ticker import.

Finviz has no price history, so prices come from the fallback provider (Yahoo). Each
fundamental field falls back to Yahoo when Finviz lacks it; the source is recorded per field.
Unofficial scraping: Finviz ToS may forbid it, quotes are delayed 15-20 min.
"""

import dataclasses
import re
from datetime import date, datetime

import finviz
import pandas as pd
import requests

from ilovestock.models import Fundamentals
from ilovestock.providers.base import MarketDataProvider

WARNING = (
    "Finviz: unofficial source (scraping), use may violate Finviz ToS; quotes delayed 15-20 min."
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PAGE_SIZE = 20
SUFFIX = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}

# Keys and formats verified on real get_stock() responses (tests/fixtures/*_finviz.json).
# Finviz "Q/Q" growth fields are YoY (same quarter last year), per Finviz help.
KEYS = {
    "sales_growth_yoy_pct": "Sales Q/Q",  # "-6.98%"
    "eps_growth_yoy_pct": "EPS Q/Q",  # "127.37%"
    "roe_pct": "ROE",  # "0.42%"
    "inst_own_pct": "Inst Own",  # "82.64%"
    "inst_trans_pct": "Inst Trans",  # "-1.02%"
}
MARKET_CAP = "Market Cap"  # "1.15B"
DIVIDEND = "Dividend TTM"  # "1.06 (0.31%)"; "-" when none or missing
EARNINGS = "Earnings"  # "Nov 02 AMC": no year; may be the last report, not the next


class FinvizError(Exception):
    pass


def _pct(value: str | None) -> float | None:
    """'82.64%' -> 82.64; '-' or missing -> None."""
    if not value:
        return None
    try:
        return float(value.strip().rstrip("%"))
    except ValueError:
        return None


def _money(value: str | None) -> float | None:
    """'1.15B' -> 1.15e9."""
    m = re.fullmatch(r"([\d.]+)([KMBT])", (value or "").strip())
    return float(m.group(1)) * SUFFIX[m.group(2)] if m else None


def _dividend_yield(value: str | None) -> float | None:
    """'1.06 (0.31%)' -> 0.31. '-' -> None: Finviz does not tell 'none' from 'missing'."""
    m = re.search(r"\(([\d.]+)%\)", value or "")
    return float(m.group(1)) if m else None


def _earnings_date(value: str | None, today: date) -> date | None:
    """'Nov 02 AMC' -> the occurrence nearest to today, in any year.

    Already past means it is the last report, not the next one -> None.
    """
    m = re.match(r"([A-Z][a-z]{2}) (\d{1,2})", (value or "").strip())
    if not m:
        return None
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(datetime.strptime(f"{m[1]} {m[2]} {year}", "%b %d %Y").date())
        except ValueError:  # Feb 29 in a non-leap year
            pass
    d = min(candidates, key=lambda c: abs((c - today).days), default=None)
    return d if d and d >= today else None


def parse_snapshot(data: dict, today: date) -> dict:
    """get_stock() dict -> Fundamentals field values (None when missing)."""
    values = {field: _pct(data.get(key)) for field, key in KEYS.items()}
    values["market_cap"] = _money(data.get(MARKET_CAP))
    values["dividend_yield_pct"] = _dividend_yield(data.get(DIVIDEND))
    values["next_earnings"] = _earnings_date(data.get(EARNINGS), today)
    return values


class FinvizProvider:
    """Fundamentals from Finviz, per-field fallback to `fallback`; prices from `fallback`."""

    def __init__(self, fallback: MarketDataProvider, today: date | None = None):
        self.fallback = fallback
        self.today = today or date.today()

    def history(self, ticker: str) -> pd.DataFrame:
        return self.fallback.history(ticker)

    def fundamentals(self, ticker: str) -> Fundamentals:
        try:
            base = self.fallback.fundamentals(ticker)
        except Exception:
            base = Fundamentals(sales=[], eps=[], roe_pct=None, market_cap=None, next_earnings=None)
        sources = {
            k: "Yahoo"
            for k in ("roe_pct", "market_cap", "next_earnings", "inst_own_pct")
            if getattr(base, k) is not None
        }
        try:
            fv = parse_snapshot(finviz.get_stock(ticker), self.today)
            note = ""
        except Exception as e:  # scraping: any site change surfaces here
            fv, note = {}, f"Finviz error: {e}"
        found = {k: v for k, v in fv.items() if v is not None}
        sources.update(dict.fromkeys(found, "Finviz"))
        return dataclasses.replace(base, **found, sources=sources, note=note)


def parse_screener_page(html: str) -> tuple[list[str], int]:
    """Tickers on one screener page and the total result count."""
    total = re.search(r"#\d+ / (\d+) Total", html)
    tickers = dict.fromkeys(re.findall(r'href="/quote\?t=([A-Z0-9.\-]+)&', html))
    return list(tickers), int(total.group(1)) if total else 0


def screener_tickers(url: str) -> list[str]:
    """All tickers from a Finviz screener URL copied from the site.

    The `finviz` lib 2.0.0 Screener no longer parses the current site (row count markup
    changed), so we read the ticker links directly. Contract test: tests/test_providers.py (slow).
    """
    if not url.startswith("https://finviz.com/screener"):
        raise FinvizError("invalid URL: must start with https://finviz.com/screener")
    tickers: list[str] = []
    total, row = None, 1
    while total is None or row <= total:
        resp = requests.get(url, params={"r": row}, headers={"User-Agent": UA}, timeout=30)
        resp.raise_for_status()
        page, total = parse_screener_page(resp.text)
        if not page:
            break
        tickers += page
        row += PAGE_SIZE
    if not tickers:
        raise FinvizError("no tickers found: filters with no results or page changed")
    return list(dict.fromkeys(tickers))
