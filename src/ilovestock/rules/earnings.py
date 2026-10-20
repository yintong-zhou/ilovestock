"""Never buy near earnings: PASS only if the next earnings date is more than 10 days away."""

from datetime import date

from ilovestock.models import CriterionResult, Status

MIN_DAYS_TO_EARNINGS = 10


def earnings(next_earnings: date | None, today: date, source: str = "") -> CriterionResult:
    threshold = f"> {MIN_DAYS_TO_EARNINGS} days"
    if next_earnings is None or next_earnings < today:
        return CriterionResult("Next earnings", Status.ND, None, threshold, "date not available")
    days = (next_earnings - today).days
    status = Status.PASS if days > MIN_DAYS_TO_EARNINGS else Status.FAIL
    note = f"source: {source}" if source else ""
    return CriterionResult("Next earnings", status, f"{next_earnings} ({days} d)", threshold, note)
