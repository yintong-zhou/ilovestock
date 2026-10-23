"""Fundamental criteria with the method thresholds. Missing data -> N/D, never PASS."""

from datetime import timedelta

import pandas as pd

from ilovestock.config import Config
from ilovestock.models import CriterionResult, Fundamentals, Status

LAG = {"qoq": 1, "yoy": 4}  # quarters back: previous quarter vs same quarter last year


def growth_pct(series: list[float | None], basis: str) -> tuple[float | None, str]:
    """(growth %, note). Base <= 0 makes growth undefined -> None."""
    lag = LAG[basis]
    if len(series) <= lag or series[0] is None or series[lag] is None:
        return None, f"needs {lag + 1} quarters"
    cur, base = series[0], series[lag]
    if base <= 0:
        return None, f"base {base:g} <= 0: growth undefined"
    return (cur - base) / base * 100, ""


def _above(name: str, value: float | None, minimum: float, note: str = "") -> CriterionResult:
    if value is None:
        return CriterionResult(name, Status.ND, None, f"> {minimum:g}%", note or "missing data")
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


def _note(f: Fundamentals, field: str, extra: str = "") -> str:
    """Data source for a present value, or why it is missing."""
    src = f.sources.get(field)
    text = f"source: {src}" if src else "; ".join(x for x in ("missing data", f.note) if x)
    return f"{text}; {extra}" if extra else text


def _growth(f: Fundamentals, field: str, cfg: Config) -> tuple[float | None, str]:
    """YoY: Finviz value first. QoQ (or Finviz missing): computed from Yahoo quarters."""
    finviz_value = getattr(f, f"{field}_growth_yoy_pct")
    if cfg.growth_basis == "yoy" and finviz_value is not None:
        return finviz_value, "source: Finviz"
    value, why = growth_pct(getattr(f, field), cfg.growth_basis)
    return value, "source: Yahoo" if value is not None else why


def fundamental(f: Fundamentals, prices: pd.DataFrame, cfg: Config) -> list[CriterionResult]:
    basis = cfg.growth_basis.upper()
    sales, sales_note = _growth(f, "sales", cfg)
    eps, eps_note = _growth(f, "eps", cfg)
    results = [
        _above(f"Sales growth {basis}", sales, cfg.sales_growth_min, sales_note),
        _above(f"EPS growth {basis}", eps, cfg.eps_growth_min, eps_note),
        _above("ROE", f.roe_pct, cfg.roe_min, _note(f, "roe_pct")),
    ]

    max_own = cfg.institutional_own_max
    note = _note(f, "inst_own_pct")
    if f.inst_own_pct is None:
        results.append(
            CriterionResult("Institutional own %", Status.ND, None, f"< {max_own:g}%", note)
        )
    else:
        status = Status.PASS if f.inst_own_pct < max_own else Status.FAIL
        value = round(f.inst_own_pct, 2)
        results.append(
            CriterionResult("Institutional own %", status, value, f"< {max_own:g}%", note)
        )

    results.append(
        _above("Institutional transactions", f.inst_trans_pct, 0, _note(f, "inst_trans_pct"))
    )

    dy, note = f.dividend_yield_pct, "source: Finviz"
    if dy is None:  # Finviz "-" means none or missing: use the actual dividend history
        dy, note = dividend_yield_pct(prices), "source: Yahoo dividend history"
    if dy is None:
        results.append(CriterionResult("Dividend yield", Status.ND, None, "= 0%", "missing data"))
    else:
        status = Status.PASS if dy == 0 else Status.FAIL
        results.append(CriterionResult("Dividend yield", status, round(dy, 2), "= 0%", note))

    if f.market_cap is None:
        results.append(
            CriterionResult(
                "Market cap", Status.ND, None, "micro/small/mid", _note(f, "market_cap")
            )
        )
    else:
        band = market_cap_band(f.market_cap, cfg)
        ok = band in ("micro", "small", "mid")
        risk = {"nano": "very risky", "large": "reduced upside", "giant": "reduced upside"}
        results.append(
            CriterionResult(
                "Market cap",
                Status.PASS if ok else Status.FAIL,
                f"{f.market_cap / 1e6:,.0f}M ({band})",
                "micro/small/mid",
                _note(f, "market_cap", risk.get(band, "")),
            )
        )
    return results
