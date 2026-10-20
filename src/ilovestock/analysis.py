"""One ticker end to end: data -> criteria -> trade plan -> verdict. Shared by CLI and API."""

from datetime import date

import pandas as pd

from ilovestock.config import Config
from ilovestock.models import TickerAnalysis, Verdict
from ilovestock.providers.base import MarketDataProvider
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

    fund_results = fundamental(fund, daily, cfg)
    tech_results = technical(daily, bench_close)
    earn = earnings(fund.next_earnings, today, fund.sources.get("next_earnings", ""))
    plan = trade_plan(daily, cfg)
    v, reasons = verdict(fund_results, tech_results, earn, plan, allow_missing)
    return TickerAnalysis(
        ticker=ticker,
        verdict=v,
        reasons=reasons,
        fundamental=fund_results,
        technical=tech_results,
        earnings=earn,
        plan=plan,
        data_date=daily.index[-1].date(),
    )
