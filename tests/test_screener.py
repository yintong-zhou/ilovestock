"""Fundamentals-first screener: Finviz pre-filter, exact check, quality ranking (offline)."""

from dataclasses import replace
from pathlib import Path

from ilovestock.config import load
from ilovestock.screener import finviz_filters, screener_url

DEFAULT = load(Path("does-not-exist.toml"))


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
