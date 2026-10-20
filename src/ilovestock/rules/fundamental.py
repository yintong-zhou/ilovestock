"""Fundamental criteria with course thresholds. Missing data -> N/D, never PASS."""

from datetime import timedelta

import pandas as pd

from ilovestock.config import Config
from ilovestock.models import CriterionResult, Fundamentals, Status

LAG = {"qoq": 1, "yoy": 4}  # quarters back: previous quarter vs same quarter last year


def growth_pct(series: list[float | None], basis: str) -> tuple[float | None, str]:
    """(growth %, note). Base <= 0 makes growth undefined -> None."""
    lag = LAG[basis]
    if len(series) <= lag or series[0] is None or series[lag] is None:
        return None, f"servono {lag + 1} trimestri"
    cur, base = series[0], series[lag]
    if base <= 0:
        return None, f"base {base:g} <= 0: crescita non definita"
    return (cur - base) / base * 100, ""


def _above(name: str, value: float | None, minimum: float, note: str = "") -> CriterionResult:
    if value is None:
        return CriterionResult(name, Status.ND, None, f"> {minimum:g}%", note or "dato mancante")
    status = Status.PASS if value > minimum else Status.FAIL
    return CriterionResult(name, status, round(value, 2), f"> {minimum:g}%", note)


def market_cap_band(cap: float, cfg: Config) -> str:
    m = cap / 1e6
    for band, upper in (
        ("nano", cfg.nano_max),
        ("micro", cfg.micro_max),
        ("small", cfg.small_max),
        ("mid", cfg.mid_max),
        ("large", cfg.large_max),
    ):
        if m < upper:
            return band
    return "giant"


def dividend_yield_pct(prices: pd.DataFrame) -> float | None:
    """Dividends paid in the last 365 days / last close."""
    if "Dividends" not in prices or prices["Dividends"].isna().all():
        return None
    last_year = prices.index[-1] - timedelta(days=365)
    paid = prices.loc[prices.index > last_year, "Dividends"].sum()
    return paid / prices["Close"].iloc[-1] * 100


def fundamental(f: Fundamentals, prices: pd.DataFrame, cfg: Config) -> list[CriterionResult]:
    basis = cfg.growth_basis.upper()
    sales, sales_note = growth_pct(f.sales, cfg.growth_basis)
    eps, eps_note = growth_pct(f.eps, cfg.growth_basis)
    results = [
        _above(f"Crescita vendite {basis}", sales, cfg.sales_growth_min, sales_note),
        _above(f"Crescita EPS {basis}", eps, cfg.eps_growth_min, eps_note),
        _above("ROE", f.roe_pct, cfg.roe_min),
    ]

    max_own = cfg.institutional_own_max
    if f.inst_own_pct is None:
        note = f.inst_note or "dato mancante"
        results.append(CriterionResult("Istituzionali %", Status.ND, None, f"< {max_own:g}%", note))
    else:
        status = Status.PASS if f.inst_own_pct < max_own else Status.FAIL
        results.append(
            CriterionResult("Istituzionali %", status, f.inst_own_pct, f"< {max_own:g}%")
        )

    results.append(_above("Transazioni istituzionali", f.inst_trans_pct, 0, f.inst_note))

    dy = dividend_yield_pct(prices)
    if dy is None:
        results.append(CriterionResult("Dividend yield", Status.ND, None, "= 0%", "dato mancante"))
    else:
        status = Status.PASS if dy == 0 else Status.FAIL
        results.append(CriterionResult("Dividend yield", status, round(dy, 2), "= 0%"))

    if f.market_cap is None:
        results.append(CriterionResult("Market cap", Status.ND, None, "micro/small/mid"))
    else:
        band = market_cap_band(f.market_cap, cfg)
        ok = band in ("micro", "small", "mid")
        note = {"nano": "molto rischiosa", "large": "upside ridotto", "giant": "upside ridotto"}
        results.append(
            CriterionResult(
                "Market cap",
                Status.PASS if ok else Status.FAIL,
                f"{f.market_cap / 1e6:,.0f}M ({band})",
                "micro/small/mid",
                note.get(band, ""),
            )
        )
    return results
