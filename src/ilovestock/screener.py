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
from ilovestock.rules.fundamental import market_cap_band

MAX_ROWS = 1000  # rows read before the first nano, large/giant included: ~70 page requests at most
SCREEN_PERIOD = "1y"  # its rules read prices only for the dividends paid in the last 365 days
DEFAULT_RESULTS = 20
MAX_RESULTS = inputs.MAX_TICKERS  # the list goes to `analyze`, which takes at most this many
SCREENER_URL = "https://finviz.com/screener.ashx?v=111&f="
BY_CAP_DESC = "&o=-marketcap"

# Finviz screener buckets (verified on a real page: tests/fixtures/finviz_screener_default.html).
# The pre-filter takes the loosest bucket that cannot drop a stock the exact rules would keep.
# Not filtered on Finviz: dividends (its filter uses the forward estimate, the rule the trailing
# year) and market cap (one option only, a custom range is Elite-only): see `candidates`.
GROWTH_OVER = (5, 10, 15, 20, 25, 30)
ROE_OVER = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50)
INST_OWN_UNDER = (10, 20, 30, 40, 50, 60, 70, 80, 90)
ALLOWED_BANDS = ("micro", "small", "mid")  # same as the Market cap rule
LARGE_BANDS = ("large", "giant")  # opt-in: the screen then skips the Market cap rule


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
    filters.append("sh_insttrans_pos")
    return filters


def screener_url(cfg: Config) -> str:
    return SCREENER_URL + ",".join(finviz_filters(cfg)) + BY_CAP_DESC


def candidates(cfg: Config, include_large: bool = False) -> list[str]:
    """Pre-filter tickers in the micro/small/mid bands of the config, read by market cap descending:
    large and giant are skipped unless `include_large`, the first nano ends the list (no more
    pages are fetched).

    A row with no Finviz market cap is skipped, like any other missing filtered value.
    """
    bands = ALLOWED_BANDS + LARGE_BANDS if include_large else ALLOWED_BANDS
    # each candidate costs Finviz + Yahoo requests, a few seconds: the config caps them
    key = "max_candidates_large" if include_large else "max_candidates"
    limit = int(getattr(cfg, key))
    tickers = []
    for i, (t, cap) in enumerate(finviz.screener_rows(screener_url(cfg)), 1):
        if i > MAX_ROWS:
            raise finviz.FinvizError(
                f"more than {MAX_ROWS} Finviz rows above the nano caps. "
                "Tighten the fundamental thresholds in the config"
            )
        if cap is None:
            continue
        band = market_cap_band(cap, cfg)
        if band == "nano":
            break
        if band in bands:
            tickers.append(t)
        if len(tickers) > limit:
            yoy = '; growth_basis = "yoy" also filters growth on Finviz'
            raise finviz.FinvizError(
                f"more than {limit} {'/'.join(bands)} candidates from Finviz. "
                f"Tighten the fundamental thresholds or raise {key} in the config (Settings)"
                + (yoy if cfg.growth_basis == "qoq" else "")
            )
    return tickers


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
    candidates: int  # Finviz pre-filter: micro/small/mid, plus large/giant with include_large
    passed: int  # every fundamental and earnings criterion PASS
    errors: list[str]  # tickers skipped for data errors
    hits: list[ScreenHit]  # best `max_results` by quality score


def screen(
    provider: MarketDataProvider,
    cfg: Config,
    today: date,
    max_results: int = DEFAULT_RESULTS,
    progress: Callable[[str], None] | None = None,
    include_large: bool = False,
) -> ScreenResult:
    """With `include_large`, large and giant caps are searched and the Market cap rule is skipped:
    `analyze` still fails them on it (user's decision)."""
    tickers = candidates(cfg, include_large)
    passed: list[tuple[str, str | None, Quality]] = []
    errors = []
    for t in tickers:
        if progress:
            progress(t)
        try:
            fund = provider.fundamentals(t)
            if fund.note:  # a source failed (e.g. Finviz 429): a fetch error, not a failed rule
                errors.append(t)
                continue
            daily = provider.history(t, SCREEN_PERIOD)
            fund_results, earn = fundamental_checks(fund, daily, cfg, today)
            q = quality(fund)
        except Exception:  # unofficial sources: skip the ticker, keep the search going
            errors.append(t)
            continue
        checked = [c for c in fund_results if not (include_large and c.name == "Market cap")]
        if all(c.status == Status.PASS for c in [*checked, earn]):
            cap = next((c.value for c in fund_results if c.name == "Market cap"), None)
            passed.append((t, cap, q))
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
