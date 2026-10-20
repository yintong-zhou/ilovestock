"""BUY only if every criterion passes and the trade plan is valid; otherwise NO-BUY with reasons."""

from ilovestock.models import CriterionResult, Status, TradePlan, Verdict


def verdict(
    fundamental: list[CriterionResult],
    technical: list[CriterionResult],
    earnings: CriterionResult,
    plan: TradePlan | None,
    allow_missing: bool = False,
) -> tuple[Verdict, list[str]]:
    """allow_missing (D3): fundamental N/D does not block. It is still shown as N/D, never PASS."""
    reasons = [
        f"{c.name}: {c.status}"
        for c in fundamental
        if c.status == Status.FAIL or (c.status == Status.ND and not allow_missing)
    ]
    reasons += [f"{c.name}: {c.status}" for c in [earnings, *technical] if c.status != Status.PASS]
    if plan is None:
        reasons.append("Trade plan: not enough history")
    elif plan.discarded:
        reasons.append(f"Trade plan discarded: {plan.discarded}")
    return (Verdict.NO_BUY if reasons else Verdict.BUY), reasons
