"""Fundamentals-first screener: loose Finviz pre-filter, then the exact rules of `analyze`."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from ilovestock import inputs
from ilovestock.analysis import fundamental_checks
from ilovestock.config import Config
from ilovestock.models import Quality, Status
from ilovestock.providers import finviz
from ilovestock.providers.base import MarketDataProvider
from ilovestock.quality import quality, ranks, scores

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


@dataclass
class ScreenHit:
    ticker: str
    market_cap: str | None  # e.g. "1,240M (small)"
    quality: Quality
    score: float  # 0-100 within the stocks that passed
    roic_rank: int | None
    margin_rank: int | None


@dataclass
class ScreenResult:
    candidates: int  # from the Finviz pre-filter
    passed: int  # every fundamental and earnings criterion PASS
    errors: list[str]  # tickers skipped for data errors
    hits: list[ScreenHit]  # best `max_results` by quality score


def screen(
    provider: MarketDataProvider,
    cfg: Config,
    today: date,
    max_results: int = DEFAULT_RESULTS,
    progress: Callable[[str], None] | None = None,
) -> ScreenResult:
    try:
        tickers = finviz.screener_tickers(screener_url(cfg), MAX_CANDIDATES)
    except finviz.TooManyResults as e:
        yoy = '; growth_basis = "yoy" also filters growth on Finviz'
        raise finviz.FinvizError(
            f"{e.total} candidates from Finviz: max {MAX_CANDIDATES}. "
            "Tighten the fundamental thresholds in the config"
            + (yoy if cfg.growth_basis == "qoq" else "")
        ) from e
    passed: list[tuple[str, str | None, Quality]] = []
    errors = []
    for t in tickers:
        if progress:
            progress(t)
        try:
            daily = provider.history(t)
            fund = provider.fundamentals(t)
            fund_results, earn = fundamental_checks(fund, daily, cfg, today)
        except Exception:  # unofficial sources: skip the ticker, keep the search going
            errors.append(t)
            continue
        if all(c.status == Status.PASS for c in [*fund_results, earn]):
            cap = next((c.value for c in fund_results if c.name == "Market cap"), None)
            passed.append((t, cap, quality(fund)))
    qs = [q for _, _, q in passed]
    roic_ranks, margin_ranks = (
        ranks([q.roic_pct for q in qs]),
        ranks([q.margin_change_pt for q in qs]),
    )
    hits = [
        ScreenHit(t, cap, q, s, rr, mr)
        for (t, cap, q), s, rr, mr in zip(passed, scores(qs), roic_ranks, margin_ranks, strict=True)
    ]
    hits.sort(
        key=lambda h: (-h.score, h.quality.roic_pct is None, -(h.quality.roic_pct or 0), h.ticker)
    )
    return ScreenResult(len(tickers), len(passed), errors, hits[:max_results])
