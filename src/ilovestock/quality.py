"""Quality of growth: ROIC and 1-year operating margin change, scored by rank within a group."""

from statistics import mean

from ilovestock.models import Fundamentals, Quality


def margin_change(
    sales: list[float | None], operating_income: list[float | None]
) -> tuple[float | None, float | None, float | None]:
    """(latest margin %, same quarter a year earlier %, change in points); quarters newest first."""
    if len(sales) < 5 or len(operating_income) < 5:
        return None, None, None
    pairs = [(sales[i], operating_income[i]) for i in (0, 4)]
    if any(s is None or op is None or s <= 0 for s, op in pairs):
        return None, None, None
    now, ago = (round(op / s * 100, 2) for s, op in pairs)
    return now, ago, round(now - ago, 2)


def quality(f: Fundamentals) -> Quality:
    return Quality(f.roic_pct, *margin_change(f.sales, f.operating_income))


def ranks(values: list[float | None]) -> list[int | None]:
    """Competition ranking, 1 = highest; ties share a rank; None stays None."""
    return [None if v is None else 1 + sum(o is not None and o > v for o in values) for v in values]


def _percentiles(values: list[float | None]) -> list[float]:
    n = len(values)
    return [
        0.0 if r is None else 100.0 if n == 1 else 100 * (n - r) / (n - 1) for r in ranks(values)
    ]


def scores(items: list[Quality]) -> list[float]:
    """Mean of the ROIC and margin-change percentiles, 0-100 (100 = best of the group)."""
    roic = _percentiles([q.roic_pct for q in items])
    margin = _percentiles([q.margin_change_pt for q in items])
    return [round(mean(pair), 1) for pair in zip(roic, margin, strict=True)]
