"""Fundamentals-first screener: loose Finviz pre-filter, then the exact rules of `analyze`."""

from ilovestock import inputs
from ilovestock.config import Config

MAX_CANDIDATES = 100  # each candidate costs Finviz + Yahoo requests: ~5 minutes at most
DEFAULT_RESULTS = 20
MAX_RESULTS = inputs.MAX_TICKERS  # the list goes to `analyze`, which takes at most this many
SCREENER_URL = "https://finviz.com/screener.ashx?v=111&f="

# Finviz screener buckets (verified on a real page: tests/fixtures/finviz_screener_default.html).
# The pre-filter takes the loosest bucket that cannot drop a stock the exact rules would keep.
GROWTH_OVER = (5, 10, 15, 20, 25, 30)
ROE_OVER = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50)
INST_OWN_UNDER = (10, 20, 30, 40, 50, 60, 70, 80, 90)
CAP_OVER = {50: "microover", 300: "smallover", 2000: "midover", 10000: "largeover"}  # $M


def _over(levels, minimum: float) -> int | None:
    """Highest 'over X' bucket that still includes every value above `minimum`."""
    return max((x for x in levels if x <= minimum), default=None)


def finviz_filters(cfg: Config) -> list[str]:
    filters = []
    if cfg.growth_basis == "yoy":  # Finviz has only the year-on-year comparison
        for key, minimum in (("salesqoq", cfg.sales_growth_min), ("epsqoq", cfg.eps_growth_min)):
            if (x := _over(GROWTH_OVER, minimum)) is not None:
                filters.append(f"fa_{key}_o{x}")
    if (x := _over(ROE_OVER, cfg.roe_min)) is not None:
        filters.append(f"fa_roe_o{x}")
    own = min((x for x in INST_OWN_UNDER if x >= cfg.institutional_own_max), default=None)
    if own is not None:
        filters.append(f"sh_instown_u{own}")
    filters += ["sh_insttrans_pos", "fa_div_none"]
    if (x := _over(CAP_OVER, cfg.nano_max)) is not None:
        filters.append(f"cap_{CAP_OVER[x]}")
    return filters


def screener_url(cfg: Config) -> str:
    return SCREENER_URL + ",".join(finviz_filters(cfg))
