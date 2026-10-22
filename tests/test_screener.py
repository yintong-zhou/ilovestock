"""Fundamentals-first screener: Finviz pre-filter, exact check, quality ranking (offline)."""

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
TODAY = date(2026, 10, 22)


# --- Finviz pre-filter ---
def test_filters_default_config():
    assert finviz_filters(DEFAULT) == [
        "fa_salesqoq_o20",
        "fa_epsqoq_o15",
        "fa_roe_o15",
        "sh_instown_u80",
        "sh_insttrans_pos",
        "fa_div_none",
        "cap_microover",
    ]


def test_filters_take_the_loosest_bucket():
    cfg = replace(
        DEFAULT, sales_growth_min=22, eps_growth_min=12, roe_min=3, institutional_own_max=85
    )
    f = finviz_filters(cfg)
    assert "fa_salesqoq_o20" in f and "fa_epsqoq_o10" in f and "sh_instown_u90" in f
    assert not any(x.startswith("fa_roe") for x in f)
    assert not any(
        x.startswith("sh_instown")
        for x in finviz_filters(replace(DEFAULT, institutional_own_max=95))
    )


def test_filters_qoq_leaves_growth_out():
    f = finviz_filters(replace(DEFAULT, growth_basis="qoq"))
    assert not any(x.startswith(("fa_salesqoq", "fa_epsqoq")) for x in f)


def test_screener_url_has_no_country_filter():
    url = screener_url(DEFAULT)
    assert url.startswith("https://finviz.com/screener.ashx?v=111&f=fa_salesqoq_o20,")
    assert "geo_" not in url


def applied_filters(html: str) -> set[str]:
    m = re.search(r'screener-split-applied-filters"><span> <b>Filters:</b> (.*?)</span>', html)
    return set(m.group(1).replace("<!-- -->", " ").split())


def test_finviz_accepts_every_generated_filter():
    # Finviz silently ignores unknown codes: a code missing from the applied list is wrong
    html = (FIX / "finviz_screener_default.html").read_text(encoding="utf-8")
    shown = {":".join(code.rsplit("_", 1)) for code in finviz_filters(DEFAULT)}
    assert shown <= applied_filters(html)


# --- exact check and ranking ---
class FakeProvider:
    def __init__(self, data: dict[str, Fundamentals | Exception]):
        self.data = data

    def _get(self, t):
        v = self.data[t]
        if isinstance(v, Exception):
            raise v
        return v

    def history(self, t):
        self._get(t)
        return prices()

    def fundamentals(self, t):
        return self._get(t)


def run(monkeypatch, data, **kw):
    monkeypatch.setattr(finviz, "screener_tickers", lambda url, limit=None: list(data))
    return screen(FakeProvider(data), kw.pop("cfg", CFG), TODAY, **kw)


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
    def boom(url, limit=None):
        raise finviz.TooManyResults("x", total=150)

    monkeypatch.setattr(finviz, "screener_tickers", boom)
    with pytest.raises(finviz.FinvizError, match="150 candidates from Finviz: max 100"):
        screen(FakeProvider({}), CFG, TODAY)
    with pytest.raises(finviz.FinvizError, match="yoy"):
        screen(FakeProvider({}), replace(CFG, growth_basis="qoq"), TODAY)
