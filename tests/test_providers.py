from datetime import date

import pandas as pd
import pytest

from ilovestock.providers import finviz
from ilovestock.providers.cache import CachedProvider
from ilovestock.providers.yahoo import YahooProvider
from tests.conftest import FIX


def test_yahoo_history_shape(fake_yf):
    df = YahooProvider().history("HZO")
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume", "Dividends"]
    assert df.index.tz is None and df.index.is_monotonic_increasing
    assert len(df) > 400


def test_yahoo_fundamentals(fake_yf):
    f = YahooProvider().fundamentals("HZO")
    assert f.sales[0] == 611258000.0 and len(f.sales) == 5
    assert f.eps[:2] == [0.66, -0.12]
    assert f.roe_pct == pytest.approx(0.497)
    assert f.next_earnings == date(2026, 11, 12)


def test_yahoo_missing_data(monkeypatch):
    class Empty:
        def __init__(self, _):
            pass

        def history(self, **_):
            return pd.DataFrame()

        quarterly_income_stmt = pd.DataFrame()
        info: dict = {}
        calendar: dict = {}

    monkeypatch.setattr("ilovestock.providers.yahoo.yf.Ticker", Empty)
    f = YahooProvider().fundamentals("XXX")
    assert f.sales == [] and f.roe_pct is None and f.market_cap is None
    assert f.next_earnings is None
    with pytest.raises(Exception, match="nessun prezzo"):
        YahooProvider().history("XXX")


def test_cache_roundtrip(fake_yf, tmp_path):
    class Counting(YahooProvider):
        calls = 0

        def history(self, t):
            Counting.calls += 1
            return super().history(t)

        def fundamentals(self, t):
            Counting.calls += 1
            return super().fundamentals(t)

    p = CachedProvider(Counting(), tmp_path)
    h1, f1 = p.history("HZO"), p.fundamentals("HZO")
    h2, f2 = p.history("HZO"), p.fundamentals("HZO")
    assert Counting.calls == 2
    pd.testing.assert_frame_equal(h1, h2, check_freq=False)
    assert f1 == f2


def test_finviz_pct():
    assert finviz._pct("82.64%") == 82.64
    assert finviz._pct("-1.02%") == -1.02
    assert finviz._pct("-") is None and finviz._pct(None) is None


def test_finviz_institutional_keys_on_recorded_response(monkeypatch):
    import json

    import finviz as lib

    data = json.loads((FIX / "HZO_finviz.json").read_text())
    monkeypatch.setattr(lib, "get_stock", lambda t: data)
    assert finviz.institutional("HZO") == (82.64, -1.02, "")


def test_finviz_failure_is_missing_not_guess(monkeypatch):
    import finviz as lib

    def boom(_):
        raise RuntimeError("page changed")

    monkeypatch.setattr(lib, "get_stock", boom)
    own, trans, note = finviz.institutional("HZO")
    assert own is None and trans is None and "page changed" in note


def test_parse_screener_page():
    html = (FIX / "finviz_screener_p1.html").read_text(encoding="utf-8")
    tickers, total = finviz.parse_screener_page(html)
    assert total == 261
    assert len(tickers) == 20 and tickers[0] == "AADX"


def test_screener_paginates(monkeypatch):
    pages = {
        1: (FIX / "finviz_screener_p1.html").read_text(encoding="utf-8"),
        21: (FIX / "finviz_screener_p2.html").read_text(encoding="utf-8"),
    }

    class Resp:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    def get(url, params, **_):
        return Resp(pages.get(params["r"], "<html></html>"))

    monkeypatch.setattr(finviz.requests, "get", get)
    tickers = finviz.screener_tickers("https://finviz.com/screener.ashx?v=111&f=cap_small")
    assert len(tickers) == 40 and tickers[20] == "ARDX"


def test_screener_rejects_other_hosts():
    with pytest.raises(finviz.FinvizError):
        finviz.screener_tickers("https://evil.example.com/screener")


@pytest.mark.slow
def test_finviz_live_contract():
    """Detects Finviz page-structure changes. Hits the live site: run only on request."""
    assert finviz.institutional("AAPL")[0] is not None
    assert len(finviz.screener_tickers("https://finviz.com/screener.ashx?v=111&f=idx_dji")) == 30
