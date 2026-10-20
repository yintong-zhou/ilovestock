"""Finviz adapter: institutional data (via the `finviz` lib) and screener ticker import.

Optional dependency (`pip install ilovestock[finviz]`). Unofficial scraping: Finviz ToS may
forbid it, quotes are delayed 15-20 min. On any failure we return None -> N/D, never a guess.
"""

import re

import requests

WARNING = (
    "Finviz: fonte non ufficiale (scraping), l'uso può violare i ToS di Finviz; "
    "quotazioni ritardate 15-20 min."
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PAGE_SIZE = 20

# Keys verified on a real get_stock() response (tests/fixtures/HZO_finviz.json).
INST_OWN = "Inst Own"
INST_TRANS = "Inst Trans"


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


def institutional(ticker: str) -> tuple[float | None, float | None, str]:
    """(inst_own_pct, inst_trans_pct, note). Note explains why values are missing."""
    try:
        import finviz
    except ImportError:
        return None, None, "finviz non installato (pip install ilovestock[finviz])"
    try:
        data = finviz.get_stock(ticker)
    except Exception as e:  # scraping: any site change surfaces here
        return None, None, f"errore Finviz: {e}"
    return _pct(data.get(INST_OWN)), _pct(data.get(INST_TRANS)), ""


def parse_screener_page(html: str) -> tuple[list[str], int]:
    """Tickers on one screener page and the total result count."""
    total = re.search(r"#\d+ / (\d+) Total", html)
    tickers = dict.fromkeys(re.findall(r'href="/quote\?t=([A-Z0-9.\-]+)&', html))
    return list(tickers), int(total.group(1)) if total else 0


def screener_tickers(url: str) -> list[str]:
    """All tickers from a Finviz screener URL copied from the site.

    The `finviz` lib 2.0.0 Screener no longer parses the current site (row count markup
    changed), so we read the ticker links directly. Contract test: tests/test_finviz.py (slow).
    """
    if not url.startswith("https://finviz.com/screener"):
        raise FinvizError("URL non valido: deve iniziare con https://finviz.com/screener")
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
        raise FinvizError("nessun ticker trovato: filtri senza risultati o pagina cambiata")
    return list(dict.fromkeys(tickers))
