"""BUY only if every criterion passes and the trade plan is valid; otherwise NO-BUY with reasons."""

from ilovestock.models import CriterionResult, Status, TradePlan, Verdict


def verdict(
    fundamental: list[CriterionResult],
    technical: list[CriterionResult],
    earnings: CriterionResult,
    plan: TradePlan | None,
    allow_missing: bool = False,
) -> tuple[Verdict, list[str]]:
    """allow_missing (D3): fundamental N/D does not block, but the verdict is BUY* (incomplete
    data), never a plain BUY. The N/D criteria are listed as reasons."""
    skipped = [f"{c.name}: {c.status}" for c in fundamental if c.status == Status.ND]
    reasons = [f"{c.name}: {c.status}" for c in fundamental if c.status == Status.FAIL]
    if not allow_missing:
        reasons += skipped
    reasons += [f"{c.name}: {c.status}" for c in [earnings, *technical] if c.status != Status.PASS]
    if plan is None:
        reasons.append("Trade plan: not enough history")
    elif plan.discarded:
        reasons.append(f"Trade plan discarded: {plan.discarded}")
    if reasons:
        return Verdict.NO_BUY, reasons
    return (Verdict.BUY_INCOMPLETE, skipped) if skipped else (Verdict.BUY, [])
