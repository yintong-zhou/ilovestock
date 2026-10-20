"""Record live Yahoo/Finviz responses as offline test fixtures.

Hits the network: run only on purpose, then commit the files in tests/fixtures/.
Usage: python execution/record_fixtures.py [TICKER] [FINVIZ_SCREENER_URL]
"""

import json
import sys
from pathlib import Path

import finviz
import requests
import yfinance as yf

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def record_yahoo(ticker: str) -> None:
    t = yf.Ticker(ticker)
    t.history(period="2y", auto_adjust=True).to_csv(OUT / f"{ticker}_history.csv")
    if ticker.startswith("^"):
        return
    t.quarterly_income_stmt.to_csv(OUT / f"{ticker}_income.csv")
    info = {k: t.info.get(k) for k in ("returnOnEquity", "marketCap", "heldPercentInstitutions")}
    (OUT / f"{ticker}_info.json").write_text(json.dumps(info, indent=2))
    cal = {k: [str(d) for d in v] for k, v in t.calendar.items() if k == "Earnings Date"}
    (OUT / f"{ticker}_calendar.json").write_text(json.dumps(cal, indent=2))


def record_finviz(ticker: str, screener_url: str) -> None:
    stock = finviz.get_stock(ticker)
    (OUT / f"{ticker}_finviz.json").write_text(json.dumps(stock, indent=2))
    for i, r in enumerate((1, 21), start=1):
        resp = requests.get(screener_url, params={"r": r}, headers={"User-Agent": UA}, timeout=30)
        resp.raise_for_status()
        (OUT / f"finviz_screener_p{i}.html").write_text(resp.text, encoding="utf-8")


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "HZO"
    url = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "https://finviz.com/screener.ashx?v=111&f=cap_small,fa_salesqoq_o20,geo_usa"
    )
    OUT.mkdir(parents=True, exist_ok=True)
    record_yahoo(ticker)
    record_yahoo("^GSPC")
    record_finviz(ticker, url)
    print(f"Fixtures written to {OUT}")
