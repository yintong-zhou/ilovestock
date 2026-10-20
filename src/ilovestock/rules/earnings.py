"""Never buy near earnings: PASS only if the next earnings date is more than 10 days away."""

from datetime import date

from ilovestock.models import CriterionResult, Status

MIN_DAYS_TO_EARNINGS = 10


def earnings(next_earnings: date | None, today: date) -> CriterionResult:
    threshold = f"> {MIN_DAYS_TO_EARNINGS} giorni"
    if next_earnings is None or next_earnings < today:
        return CriterionResult(
            "Prossimi earnings", Status.ND, None, threshold, "data non disponibile"
        )
    days = (next_earnings - today).days
    status = Status.PASS if days > MIN_DAYS_TO_EARNINGS else Status.FAIL
    return CriterionResult("Prossimi earnings", status, f"{next_earnings} ({days} gg)", threshold)
