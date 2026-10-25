"""Fundamentals-first screener: Finviz pre-filter, exact check, quality ranking (offline)."""

import itertools
import re
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from ilovestock.config import load
from ilovestock.models import Fundamentals
from ilovestock.providers import finviz
from ilovestock.providers.base import DataError
from ilovestock.screener import finviz_filters, screen, screener_url
from tests.conftest import FIX
from tests.test_rules import good_fundamentals, prices

DEFAULT = load(Path("does-not-exist.toml"))
CFG = DEFAULT
YOY = replace(DEFAULT, growth_basis="yoy")  # the only basis Finviz can filter growth on
TODAY = date(2026, 10, 22)


# --- Finviz pre-filter ---
def test_filters_yoy_config():
    assert finviz_filters(YOY) == [
        "fa_salesqoq_o20",
        "fa_epsqoq_o15",
        "fa_roe_o15",
        "sh_instown_u80",
        "sh_insttrans_pos",
    ]  # no dividend filter (Finviz uses the forward estimate) and no cap filter (see screen)


def test_filters_take_the_loosest_bucket():
    cfg = replace(YOY, sales_growth_min=22, eps_growth_min=12, roe_min=3, institutional_own_max=85)
    f = finviz_filters(cfg)
    assert "fa_salesqoq_o20" in f and "fa_epsqoq_o10" in f and "sh_instown_u90" in f
    assert not any(x.startswith("fa_roe") for x in f)
    assert not any(
        x.startswith("sh_instown")
        for x in finviz_filters(replace(DEFAULT, institutional_own_max=95))
    )


def test_filters_qoq_leaves_growth_out():
    f = finviz_filters(DEFAULT)  # default qoq: Finviz has only year-on-year growth
    assert not any(x.startswith(("fa_salesqoq", "fa_epsqoq")) for x in f)


def test_screener_url_has_no_country_filter():
    url = screener_url(YOY)
    assert url.startswith("https://finviz.com/screener.ashx?v=111&f=fa_salesqoq_o20,")
    assert "geo_" not in url and url.endswith("&o=-marketcap")


def applied_filters(html: str) -> set[str]:
    m = re.search(r'screener-split-applied-filters"><span> <b>Filters:</b> (.*?)</span>', html)
    return set(m.group(1).replace("<!-- -->", " ").split())


def test_finviz_accepts_every_generated_filter():
    # Finviz silently ignores unknown codes: a code missing from the applied list is wrong
    html = (FIX / "finviz_screener_default.html").read_text(encoding="utf-8")
    shown = {":".join(code.rsplit("_", 1)) for code in finviz_filters(YOY)}  # YOY: every code
    assert shown <= applied_filters(html)


# --- exact check and ranking ---
class FakeProvider:
    def __init__(self, data: dict[str, Fundamentals | Exception]):
        self.data = data
        self.history_calls = []

    def _get(self, t):
        v = self.data[t]
        if isinstance(v, Exception):
            raise v
        return v

    def history(self, t, period="2y"):
        self.history_calls.append((t, period))
        self._get(t)
        return prices()

    def fundamentals(self, t):
        return self._get(t)


def run(monkeypatch, data, **kw):
    monkeypatch.setattr(finviz, "screener_rows", lambda url: [(t, 1e9) for t in data])
    return screen(FakeProvider(data), kw.pop("cfg", CFG), TODAY, **kw)


def test_candidates_are_micro_to_mid_by_cap(monkeypatch):
    def rows(url):  # Finviz order: market cap descending
        yield from [("GNT", 300e9), ("LRG", 10e9), ("MID", 9.99e9)]
        yield from [("NOC", None), ("MIC", 50e6), ("NNO", 49.9e6)]  # 50M exactly is micro
        raise AssertionError("read past the first nano")

    monkeypatch.setattr(finviz, "screener_rows", rows)
    r = screen(FakeProvider({t: good_fundamentals() for t in ("MID", "MIC")}), CFG, TODAY)
    assert r.candidates == 2 and sorted(h.ticker for h in r.hits) == ["MIC", "MID"]


def test_include_large_skips_only_the_market_cap_rule(monkeypatch):
    def rows(url):
        yield from [("GNT", 300e9), ("LRG", 10e9), ("MID", 9.99e9), ("NNO", 49.9e6)]
        raise AssertionError("read past the first nano")

    monkeypatch.setattr(finviz, "screener_rows", rows)
    data = {
        "GNT": good_fundamentals(market_cap=300e9),
        "LRG": good_fundamentals(market_cap=10e9, roe_pct=10.0),  # fails ROE: still out
        "MID": good_fundamentals(market_cap=9.99e9),
    }
    r = screen(FakeProvider(data), CFG, TODAY, include_large=True)
    assert (r.candidates, sorted(h.ticker for h in r.hits)) == (3, ["GNT", "MID"])
    assert next(h for h in r.hits if h.ticker == "GNT").market_cap == "300,000M (giant)"


def test_candidates_bound_the_rows_read(monkeypatch):
    # large/giant rows are fetched but skipped: they need their own cap on Finviz requests
    giants = ((f"G{i}", 1e12 - i) for i in itertools.count())
    monkeypatch.setattr(finviz, "screener_rows", lambda url: giants)
    with pytest.raises(finviz.FinvizError, match="more than 1000 Finviz rows"):
        screen(FakeProvider({}), CFG, TODAY)
    assert next(giants)[0] == "G1001"  # stopped right after the limit


def test_screen_reads_fundamentals_first_and_one_year_of_prices(monkeypatch):
    # a failed fundamentals fetch costs no price download; the screen's rules need 1 year at most
    p = FakeProvider({"A": good_fundamentals(), "B": good_fundamentals(note="Finviz error: 429")})
    monkeypatch.setattr(finviz, "screener_rows", lambda url: [("A", 1e9), ("B", 1e9)])
    r = screen(p, CFG, TODAY)
    assert (r.errors, [h.ticker for h in r.hits]) == (["B"], ["A"])
    assert p.history_calls == [("A", "1y")]


def test_screen_keeps_only_all_pass_and_counts(monkeypatch):
    r = run(
        monkeypatch,
        {
            "A": good_fundamentals(roic_pct=20.0),
            "B": good_fundamentals(roe_pct=10.0),
            "C": DataError("x"),
        },
    )
    assert (r.candidates, r.passed, r.errors, [h.ticker for h in r.hits]) == (3, 1, ["C"], ["A"])
    assert r.hits[0].market_cap == "1,000M (small)"


def test_screen_nd_never_passes(monkeypatch):
    assert run(monkeypatch, {"A": good_fundamentals(inst_own_pct=None)}).passed == 0


def test_screen_ranks_and_cuts(monkeypatch):
    # no operating income for anyone: margin N/D, only ROIC decides
    data = {t: good_fundamentals(roic_pct=v) for t, v in (("A", 30.0), ("B", 10.0), ("C", 20.0))}
    r = run(monkeypatch, data, max_results=2)
    assert r.passed == 3 and [h.ticker for h in r.hits] == ["A", "C"]
    assert (r.hits[0].roic_rank, r.hits[0].margin_rank) == (1, None)


def test_screen_max_above_passed_shows_all(monkeypatch):
    data = {t: good_fundamentals() for t in ("A", "B", "C")}
    assert len(run(monkeypatch, data, max_results=20).hits) == 3


def test_screen_ignores_post_earnings(monkeypatch):
    f = good_fundamentals(last_earnings=TODAY - timedelta(days=1), last_earnings_amc=True)
    assert run(monkeypatch, {"A": f}).passed == 1


def test_screen_too_many_candidates(monkeypatch):
    rows = [(f"T{i}", 1e9) for i in range(101)]
    monkeypatch.setattr(finviz, "screener_rows", lambda url: iter(rows))
    with pytest.raises(finviz.FinvizError, match="more than 100 micro/small/mid candidates"):
        screen(FakeProvider({}), CFG, TODAY)
    with pytest.raises(finviz.FinvizError, match="yoy"):
        screen(FakeProvider({}), replace(CFG, growth_basis="qoq"), TODAY)
    # with large/giant the cap is 200: 101 candidates are searched (data errors here)
    assert screen(FakeProvider({}), CFG, TODAY, include_large=True).candidates == 101
    rows += [(f"U{i}", 1e9) for i in range(100)]
    with pytest.raises(finviz.FinvizError, match="more than 200 micro/small/mid/large/giant"):
        screen(FakeProvider({}), CFG, TODAY, include_large=True)
    # both caps come from the config (Settings)
    with pytest.raises(finviz.FinvizError, match="more than 50 .* raise max_candidates in"):
        screen(FakeProvider({}), replace(CFG, max_candidates=50), TODAY)


def test_screen_reports_finviz_fetch_failure_as_error(monkeypatch):
    # e.g. HTTP 429 on the quote page: a fetch failure, not a stock that failed the rules
    f = good_fundamentals(inst_trans_pct=None, note="Finviz error: 429")
    r = run(monkeypatch, {"A": f, "B": good_fundamentals()})
    assert (r.errors, r.passed, [h.ticker for h in r.hits]) == (["A"], 1, ["B"])


def test_screen_malformed_quality_data_skips_only_that_ticker(monkeypatch):
    bad = good_fundamentals(operating_income=["?"] * 5)
    r = run(monkeypatch, {"A": bad, "B": good_fundamentals()})
    assert (r.errors, [h.ticker for h in r.hits]) == (["A"], ["B"])
