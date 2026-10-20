"""One ticker end to end: data -> criteria -> trade plan -> verdict. Shared by CLI and API."""

import dataclasses
from collections.abc import Callable
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

# (ticker) -> (inst_own_pct, inst_trans_pct, note)
InstitutionalSource = Callable[[str], tuple[float | None, float | None, str]]


def analyze(
    ticker: str,
    provider: MarketDataProvider,
    bench_close: pd.Series,
    institutional: InstitutionalSource,
    cfg: Config,
    today: date,
    allow_missing: bool = False,
) -> TickerAnalysis:
    try:
        daily = provider.history(ticker)
        fund = provider.fundamentals(ticker)
    except Exception as e:  # unofficial sources: report per ticker, keep going
        return TickerAnalysis(ticker, Verdict.NO_BUY, [f"Errore dati: {e}"], error=str(e))

    own, trans, note = institutional(ticker)
    fund = dataclasses.replace(fund, inst_own_pct=own, inst_trans_pct=trans, inst_note=note)

    fund_results = fundamental(fund, daily, cfg)
    tech_results = technical(daily, bench_close)
    earn = earnings(fund.next_earnings, today)
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
