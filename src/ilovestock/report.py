"""Terminal output (Rich): summary table, optional per-ticker detail, disclaimer."""

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from ilovestock.models import (
    DISCLAIMER,
    CriterionResult,
    Status,
    TickerAnalysis,
    TradePlan,
    Verdict,
)

STATUS_STYLE = {Status.PASS: "green", Status.FAIL: "red", Status.ND: "yellow"}


def _fmt(v: float | None) -> str:
    return "N/D" if v is None else f"{v:,.2f}"


VERDICT_STYLE = {
    Verdict.BUY: "bold green",
    Verdict.BUY_INCOMPLETE: "bold yellow",
    Verdict.NO_BUY: "red",
}


def summary(results: list[TickerAnalysis]) -> Table:
    t = Table(title="ilovestock: verdicts")
    for col in ("Ticker", "Verdict", "Entry", "Stop", "Target", "Shares", "FAIL / N/D criteria"):
        t.add_column(col)
    for r in results:
        p = r.plan
        style = VERDICT_STYLE[r.verdict]
        t.add_row(
            r.ticker,
            f"[{style}]{r.verdict}[/]",
            _fmt(p.entry if p else None),
            _fmt(p.stop if p else None),
            _fmt(p.target if p else None),
            str(p.shares) if p else "N/D",
            escape("\n".join(r.reasons)),
        )
    return t


def _criteria_table(title: str, items: list[CriterionResult]) -> Table:
    t = Table(title=title, title_justify="left")
    for col in ("Criterion", "Value", "Threshold", "Status", "Note"):
        t.add_column(col)
    for c in items:
        value = "N/D" if c.value is None else str(c.value)
        status = f"[{STATUS_STYLE[c.status]}]{c.status}[/]"
        t.add_row(c.name, escape(value), c.threshold, status, escape(c.note))
    return t


def plan_lines(p: TradePlan) -> list[str]:
    """Trade plan as plain text lines (shared by terminal and file reports)."""
    lines = [
        f"Entry {p.entry:.2f}  Stop {p.stop:.2f}  Target {_fmt(p.target)}",
        f"Shares {p.shares} (constraint: {p.binding or 'N/D'}), value {p.position_value:,.2f}",
        f"Max loss {p.max_loss:,.2f}, effective risk {p.effective_risk:,.2f}"
        f" (profile {p.risk_band})",
        f"Initial trailing stop: {_fmt(p.trailing_stop_10w)} (10w), "
        f"{_fmt(p.trailing_stop_8w)} (8w, faster exit)",
        *p.info,
    ]
    if p.discarded:
        lines.append(f"Discarded: {p.discarded}")
    return lines


def detail(r: TickerAnalysis) -> Panel:
    if r.error:
        return Panel(escape(r.error), title=r.ticker, border_style="red")
    parts: list = [
        _criteria_table("Fundamental", [*r.fundamental, r.earnings]),
        _criteria_table("Technical", r.technical),
    ]
    if r.plan:
        lines = [escape(line) for line in plan_lines(r.plan)]
        if r.plan.discarded:
            lines[-1] = f"[red]{lines[-1]}[/]"
        parts.append(Panel("\n".join(lines), title="Trade plan"))
    style = VERDICT_STYLE[r.verdict]
    return Panel(
        Group(*parts),
        title=f"{r.ticker}: {r.verdict}  (data as of {r.data_date})",
        border_style=style,
    )


def print_report(results: list[TickerAnalysis], show_detail: bool, console: Console) -> None:
    console.print(summary(results))
    if show_detail:
        for r in results:
            console.print(detail(r))
    console.print(f"[bold yellow]{DISCLAIMER}[/] Recheck entry and stop on the live price.")
