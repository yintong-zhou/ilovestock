"""Terminal output (Rich): summary table, optional per-ticker detail, disclaimer."""

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from ilovestock.models import (
    DISCLAIMER,
    CriterionResult,
    Quality,
    Status,
    TickerAnalysis,
    TradePlan,
    Verdict,
)
from ilovestock.screener import ScreenResult

STATUS_STYLE = {Status.PASS: "green", Status.FAIL: "red", Status.ND: "yellow"}
QUALITY_NOTE = "informative, does not change the verdict"


def _fmt(v: float | None) -> str:
    return "N/D" if v is None else f"{v:,.2f}"


def _roic(q: Quality) -> str:
    return "N/D" if q.roic_pct is None else f"{q.roic_pct:.1f}%"


def _margin_change(q: Quality) -> str:
    return "N/D" if q.margin_change_pt is None else f"{q.margin_change_pt:+.1f} pt"


def quality_text(q: Quality) -> str:
    return f"ROIC {_roic(q)}, op. margin {_margin_change(q)}"


def _rank(r: int | None) -> str:
    return "N/D" if r is None else f"#{r}"


def screen_table(result: ScreenResult) -> Table:
    # ASCII headers: a Windows pipe (cp1252) mangles symbols like the delta sign
    t = Table(title="ilovestock: screen")
    for col in ("#", "Ticker", "Market cap", "ROIC", "Op. margin chg (1y)", "Score", "Ranks"):
        t.add_column(col, justify="right" if col in ("#", "ROIC", "Score") else "left")
    for i, h in enumerate(result.hits, 1):
        t.add_row(
            str(i),
            h.ticker,
            h.market_cap or "N/D",
            _roic(h.quality),
            _margin_change(h.quality),
            f"{h.score:.0f}",
            f"ROIC {_rank(h.roic_rank)}, margin {_rank(h.margin_rank)} of {result.passed}",
        )
    return t


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
    fundamental = _criteria_table("Fundamental", [*r.fundamental, r.earnings])
    if r.quality:  # a shown row only: kept out of the criteria, so the verdict never sees it
        fundamental.add_row("Quality", quality_text(r.quality), "-", "[cyan]INFO[/]", QUALITY_NOTE)
    parts: list = [fundamental, _criteria_table("Technical", r.technical)]
    if r.plan:
        lines = [escape(line) for line in plan_lines(r.plan)]
        if r.plan.discarded:
            lines[-1] = f"[red]{lines[-1]}[/]"
        parts.append(Panel("\n".join(lines), title="Trade plan"))
    style = VERDICT_STYLE[r.verdict]
    return Panel(
        Group(*parts),
        title=f"{r.ticker}: {r.verdict}  (prices as of {r.data_date}, "
        f"fundamentals as of {r.fundamentals_date or 'N/D'})",
        border_style=style,
    )


def print_report(results: list[TickerAnalysis], show_detail: bool, console: Console) -> None:
    console.print(summary(results))
    if show_detail:
        for r in results:
            console.print(detail(r))
    console.print(f"[bold yellow]{DISCLAIMER}[/] Recheck entry and stop on the live price.")
