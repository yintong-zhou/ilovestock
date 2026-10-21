import json
from datetime import date

import pandas as pd
import pytest

from ilovestock.providers import finviz
from ilovestock.providers.cache import CachedProvider, session_tag
from ilovestock.providers.yahoo import YahooProvider, drop_partial_bar
from tests.conftest import FIX, FakeTicker, raw_history


def test_yahoo_history_shape(fake_yf):
    df = YahooProvider().history("HZO")
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume", "Dividends"]
    assert df.index.tz is None and df.index.is_monotonic_increasing
    assert len(df) > 400


@pytest.mark.parametrize(
    "now,kept",
    [
        ("2026-10-19 10:00", False),  # session open: last bar is partial
        ("2026-10-19 16:30", True),  # after the close
        ("2026-10-20 10:00", True),  # last bar is from a previous day
    ],
)
def test_drop_partial_bar(fake_yf, now, kept):
    df = YahooProvider().history("HZO")
    out = drop_partial_bar(df, pd.Timestamp(now, tz="America/New_York"))
    assert (out.index[-1] == df.index[-1]) == kept and len(out) == len(df) - (not kept)


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
    with pytest.raises(Exception, match="no prices"):
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


TODAY = date(2026, 10, 20)  # day the fixtures were recorded


def test_finviz_value_parsers():
    assert finviz._money("1.15B") == pytest.approx(1.15e9)
    assert finviz._money("4982.82B") == pytest.approx(4.98282e12)
    assert finviz._money("-") is None
    assert finviz._dividend_yield("1.06 (0.31%)") == 0.31
    assert finviz._dividend_yield("-") is None


@pytest.mark.parametrize(
    "raw,today,expected",
    [
        ("Nov 02 AMC", date(2026, 10, 20), date(2026, 11, 2)),
        ("Jul 23 BMO", date(2026, 10, 20), None),  # already reported: not the next one
        ("Jan 25 AMC", date(2026, 12, 20), date(2027, 1, 25)),  # year rollover
        ("Dec 20 AMC", date(2026, 1, 5), None),  # last report seen in January: not next December
        ("Feb 29 BMO", date(2027, 2, 1), date(2028, 2, 29)),  # leap day, no crash
        ("-", date(2026, 10, 20), None),
    ],
)
def test_finviz_earnings_date(raw, today, expected):
    assert finviz._earnings_date(raw, today) == expected


def test_finviz_snapshot_on_recorded_responses():
    hzo = finviz.parse_snapshot(json.loads((FIX / "HZO_finviz.json").read_text()), TODAY)
    assert hzo == {
        "sales_growth_yoy_pct": -6.98,
        "eps_growth_yoy_pct": 127.37,
        "roe_pct": 0.42,
        "inst_own_pct": 82.64,
        "inst_trans_pct": -1.02,
        "market_cap": pytest.approx(1.15e9),
        "dividend_yield_pct": None,  # "-": no dividend or missing -> fallback
        "next_earnings": None,  # "Jul 23": last report
    }
    aapl = finviz.parse_snapshot(json.loads((FIX / "AAPL_finviz.json").read_text()), TODAY)
    assert aapl["dividend_yield_pct"] == 0.31 and aapl["next_earnings"] == date(2026, 11, 2)


def test_finviz_provider_merges_with_yahoo_fallback(fake_yf, fake_finviz):
    f = finviz.FinvizProvider(YahooProvider(), TODAY).fundamentals("HZO")
    assert f.roe_pct == 0.42 and f.sources["roe_pct"] == "Finviz"
    assert f.inst_own_pct == 82.64 and f.sources["inst_own_pct"] == "Finviz"
    assert f.next_earnings == date(2026, 11, 12) and f.sources["next_earnings"] == "Yahoo"
    assert f.sales[0] == 611258000.0  # Yahoo quarters kept for qoq
    assert f.note == ""


def test_finviz_failure_falls_back_never_guesses(fake_yf, monkeypatch):
    def boom(_):
        raise RuntimeError("page changed")

    monkeypatch.setattr(finviz.finviz, "get_stock", boom)
    f = finviz.FinvizProvider(YahooProvider(), TODAY).fundamentals("HZO")
    assert f.roe_pct == pytest.approx(0.497) and f.sources["roe_pct"] == "Yahoo"
    assert f.inst_own_pct == pytest.approx(84.632003) and f.sources["inst_own_pct"] == "Yahoo"
    assert f.inst_trans_pct is None and f.sales_growth_yoy_pct is None
    assert "page changed" in f.note


def test_cache_keeps_finviz_fields(fake_yf, fake_finviz, tmp_path):
    p = CachedProvider(finviz.FinvizProvider(YahooProvider(), TODAY), tmp_path)
    assert p.fundamentals("HZO") == p.fundamentals("HZO")


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
    assert finviz.parse_snapshot(finviz.finviz.get_stock("AAPL"), date.today())["inst_own_pct"]
    assert len(finviz.screener_tickers("https://finviz.com/screener.ashx?v=111&f=idx_dji")) == 30


def test_yahoo_rejects_non_usd(monkeypatch):
    class Euro(FakeTicker):
        history_metadata = {"currency": "EUR"}

    monkeypatch.setattr("ilovestock.providers.yahoo.yf.Ticker", Euro)
    with pytest.raises(Exception, match="EUR, not USD"):
        YahooProvider().history("HZO")


def test_yahoo_drops_incomplete_rows(monkeypatch):
    class Gap(FakeTicker):
        def history(self, **_):
            df = raw_history(self.ticker)
            df.iloc[-1, df.columns.get_loc("Close")] = float("nan")
            return df

    monkeypatch.setattr("ilovestock.providers.yahoo.yf.Ticker", Gap)
    full = len(raw_history("HZO"))
    df = YahooProvider().history("HZO")
    assert len(df) <= full - 1 and not df["Close"].isna().any()


@pytest.mark.parametrize(
    "now,tag",
    [
        ("2026-10-20 10:00", "2026-10-20-open"),  # intraday: no bar for today yet
        ("2026-10-20 16:30", "2026-10-20"),  # after the close: a new file, today's bar included
    ],
)
def test_cache_session_tag(now, tag):
    assert session_tag(pd.Timestamp(now, tz="America/New_York")) == tag
