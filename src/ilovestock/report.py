"""Terminal output (Rich): summary table, optional per-ticker detail, disclaimer."""

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from ilovestock.models import DISCLAIMER, CriterionResult, Status, TickerAnalysis, Verdict

STATUS_STYLE = {Status.PASS: "green", Status.FAIL: "red", Status.ND: "yellow"}


def _fmt(v: float | None) -> str:
    return "N/D" if v is None else f"{v:,.2f}"


def summary(results: list[TickerAnalysis]) -> Table:
    t = Table(title="ilovestock: verdetti")
    for col in ("Ticker", "Verdetto", "Entry", "Stop", "Target", "Azioni", "Criteri FAIL / N/D"):
        t.add_column(col)
    for r in results:
        p = r.plan
        style = "bold green" if r.verdict == Verdict.BUY else "red"
        t.add_row(
            r.ticker,
            f"[{style}]{r.verdict}[/]",
            _fmt(p.entry if p else None),
            _fmt(p.stop if p else None),
            _fmt(p.target if p else None),
            str(p.shares) if p else "N/D",
            "\n".join(r.reasons),
        )
    return t


def _criteria_table(title: str, items: list[CriterionResult]) -> Table:
    t = Table(title=title, title_justify="left")
    for col in ("Criterio", "Valore", "Soglia", "Stato", "Note"):
        t.add_column(col)
    for c in items:
        value = "N/D" if c.value is None else str(c.value)
        status = f"[{STATUS_STYLE[c.status]}]{c.status}[/]"
        t.add_row(c.name, value, c.threshold, status, c.note)
    return t


def detail(r: TickerAnalysis) -> Panel:
    if r.error:
        return Panel(r.error, title=r.ticker, border_style="red")
    parts: list = [
        _criteria_table("Fondamentali", [*r.fundamental, r.earnings]),
        _criteria_table("Tecnici", r.technical),
    ]
    p = r.plan
    if p:
        lines = [
            f"Entry {p.entry:.2f}  Stop {p.stop:.2f}  Target {_fmt(p.target)}",
            f"Azioni {p.shares} (vincolo: {p.binding or 'N/D'}), valore {p.position_value:,.2f}",
            f"Perdita max {p.max_loss:,.2f}, rischio effettivo {p.effective_risk:,.2f}"
            f" (profilo {p.risk_band})",
            f"Trailing stop iniziale: {p.trailing_stop_10w:.2f} (10w), "
            f"{p.trailing_stop_8w:.2f} (8w, uscita più rapida)",
            *p.info,
        ]
        if p.discarded:
            lines.append(f"[red]Scartato: {p.discarded}[/]")
        parts.append(Panel("\n".join(lines), title="Piano di trade"))
    style = "green" if r.verdict == Verdict.BUY else "red"
    return Panel(
        Group(*parts), title=f"{r.ticker}: {r.verdict}  (dati al {r.data_date})", border_style=style
    )


def print_report(results: list[TickerAnalysis], show_detail: bool, console: Console) -> None:
    console.print(summary(results))
    if show_detail:
        for r in results:
            console.print(detail(r))
    console.print(f"[bold yellow]{DISCLAIMER}[/] Ricontrolla entry e stop sul prezzo live.")
