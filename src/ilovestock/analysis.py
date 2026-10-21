"""One ticker end to end: data -> criteria -> trade plan -> verdict. Shared by CLI and API."""

from collections.abc import Callable
from datetime import date

import pandas as pd

from ilovestock.config import Config
from ilovestock.models import TickerAnalysis, Verdict
from ilovestock.providers.base import BENCHMARK, MarketDataProvider
from ilovestock.rules.earnings import earnings
from ilovestock.rules.fundamental import fundamental
from ilovestock.rules.technical import technical
from ilovestock.rules.trade_plan import trade_plan
from ilovestock.rules.verdict import verdict


def analyze(
    ticker: str,
    provider: MarketDataProvider,
    bench_close: pd.Series,
    cfg: Config,
    today: date,
    allow_missing: bool = False,
) -> TickerAnalysis:
    try:
        daily = provider.history(ticker)
        fund = provider.fundamentals(ticker)
    except Exception as e:  # unofficial sources: report per ticker, keep going
        return TickerAnalysis(ticker, Verdict.NO_BUY, [f"Data error: {e}"], error=str(e))

    try:
        fund_results = fundamental(fund, daily, cfg)
        tech_results = technical(daily, bench_close)
        earn = earnings(fund.next_earnings, today, fund.sources.get("next_earnings", ""))
        plan = trade_plan(daily, cfg)
        v, reasons = verdict(fund_results, tech_results, earn, plan, allow_missing)
    except Exception as e:  # malformed data: this ticker fails, not the benchmark or the run
        msg = f"{type(e).__name__}: {e}"
        return TickerAnalysis(ticker, Verdict.NO_BUY, [f"Analysis error: {msg}"], error=msg)
    return TickerAnalysis(
        ticker=ticker,
        verdict=v,
        reasons=reasons,
        fundamental=fund_results,
        technical=tech_results,
        earnings=earn,
        plan=plan,
        data_date=daily.index[-1].date(),
        price=round(float(daily["Close"].iloc[-1]), 2),
    )


def analyze_many(
    tickers: list[str],
    provider: MarketDataProvider,
    cfg: Config,
    today: date,
    allow_missing: bool = False,
    progress: Callable[[str], None] | None = None,
) -> list[TickerAnalysis]:
    """Fetch the benchmark once, then analyze each ticker.

    Only a benchmark failure raises: each ticker's errors are reported in its result.
    """
    bench = provider.history(BENCHMARK)["Close"]
    results = []
    for t in tickers:
        if progress:
            progress(t)
        results.append(analyze(t, provider, bench, cfg, today, allow_missing))
    return results
