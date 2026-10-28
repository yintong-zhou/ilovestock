"""PDF of saved analyses (offline): summary, one section per ticker, Latin-1 fallback."""

import re
import zlib
from datetime import datetime

from ilovestock import pdf

CRITERIA = [
    {"name": "ROE", "status": "PASS", "value": 20.0, "threshold": "> 15%", "note": ""},
    {"name": "Next earnings", "status": "N/D", "value": None, "threshold": "> 10 days", "note": ""},
    {"name": "Donchian 10w", "status": "FAIL", "value": 30.1, "threshold": "> 31.00", "note": None},
]
ROW = {
    "id": "a1",
    "analyzed_at": "2026-10-23T14:05:00",
    "data_date": "2026-10-22",
    "ticker": "HZO",
    "verdict": "NO-BUY",
    "price": 30.5,
    "entry": 31.0,
    "stop": 28.0,
    "target": 37.0,
    "shares": 33,
    "reasons": ["Donchian 10w: FAIL"],
    "criteria": CRITERIA,
    "note": "breakout → ≥ 31 🚀",
    "edited_at": None,
}


def text(data: bytes) -> str:
    """Every page's text: the content streams are zlib-compressed."""
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S)
    out = []
    for s in streams:
        try:
            out.append(zlib.decompress(s).decode("latin-1"))
        except zlib.error:
            continue  # font or other binary object
    return "\n".join(out)


def test_split_like_the_web():
    # same split as web/src/format.ts groups(): fundamentals end at "Next earnings"
    assert pdf.split(CRITERIA) == (CRITERIA[:2], CRITERIA[2:])
    assert pdf.split(CRITERIA[2:]) == ([], CRITERIA[2:])


def test_render_summary_sections_and_disclaimer():
    data = pdf.render([ROW], "Watchlist", datetime(2026, 10, 23, 15, 0))
    assert data.startswith(b"%PDF")
    assert data.count(b"/Subtype /Image") == 1  # the logo, embedded once for every page
    t = text(data)
    for s in ("Watchlist", "2026-10-23 15:00", "not financial advice", "HZO", "NO-BUY", "1/2",
              "0/1", "Donchian 10w", "> 31.00", "N/D", "Donchian 10w: FAIL", "37.00"):  # fmt: skip
        assert s in t, s
    assert "breakout -> >= 31 ?" in t  # outside Latin-1: ASCII stand-ins, then "?"
