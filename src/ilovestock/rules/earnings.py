"""Earnings: never buy close to the next report, and after a report wait for the reaction."""

from datetime import date

import pandas as pd

from ilovestock.models import CriterionResult, Status

MIN_DAYS_TO_EARNINGS = 10
# Method: "wait for the report, analyze the data, wait for the market's reaction" (no number).
# User's rule: 1 session of reaction, 5 when the reaction moved the price by 5% or more.
REACTION_SESSIONS = 1
BIG_REACTION_SESSIONS = 5
BIG_REACTION_PCT = 5


def earnings(next_earnings: date | None, today: date, source: str = "") -> CriterionResult:
    threshold = f"> {MIN_DAYS_TO_EARNINGS} days"
    if next_earnings is None or next_earnings < today:
        return CriterionResult("Next earnings", Status.ND, None, threshold, "date not available")
    days = (next_earnings - today).days
    status = Status.PASS if days > MIN_DAYS_TO_EARNINGS else Status.FAIL
    note = f"source: {source}" if source else ""
    return CriterionResult("Next earnings", status, f"{next_earnings} ({days} d)", threshold, note)


def post_earnings(
    last: date | None, after_close: bool | None, daily: pd.DataFrame, next_source: str = ""
) -> CriterionResult:
    name = "After last earnings"
    thr = f"{REACTION_SESSIONS} session, {BIG_REACTION_SESSIONS} if move >= {BIG_REACTION_PCT}%"
    if last is None:
        if next_source == "Finviz":  # Finviz shows the last report until the next is announced
            value, note = "no recent report", "next report already announced"
            return CriterionResult(name, Status.PASS, value, thr, f"source: Finviz; {note}")
        return CriterionResult(name, Status.ND, None, thr, "last report date not available")
    closes = daily["Close"]
    day = pd.Timestamp(last)
    reaction = closes[closes.index > day] if after_close else closes[closes.index >= day]
    timing = "after close" if after_close else "before open"
    if reaction.empty:
        return CriterionResult(
            name, Status.FAIL, f"{last} ({timing})", thr, "waiting for the reaction"
        )
    before = closes[closes.index < reaction.index[0]]
    if before.empty:
        return CriterionResult(name, Status.ND, None, thr, "no close before the report")
    move = (reaction.iloc[0] / before.iloc[-1] - 1) * 100
    need = BIG_REACTION_SESSIONS if abs(move) >= BIG_REACTION_PCT else REACTION_SESSIONS
    sessions = len(reaction)  # completed sessions since the report, reaction day included
    value = f"{last} ({timing}), move {move:+.1f}%, {sessions} sessions"
    return CriterionResult(name, Status.PASS if sessions >= need else Status.FAIL, value, thr,
                           f"source: Finviz; needs {need}")  # fmt: skip
