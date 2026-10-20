"""Report files: Markdown, CSV, JSON. Every file carries data date, sources and disclaimer."""

import csv
import dataclasses
import io
import json
from datetime import datetime
from pathlib import Path

from ilovestock.config import Config
from ilovestock.models import DISCLAIMER, TickerAnalysis
from ilovestock.report import plan_lines

FORMATS = {"md": "report.md", "csv": "results.csv", "json": "results.json"}
SOURCES = [
    "Fundamentals: Finviz (finviz lib, unofficial scraping), Yahoo Finance as per-field fallback",
    "Prices, dividend history, quarterly financials, S&P 500 (^GSPC): Yahoo Finance (yfinance),"
    " end of day",
]
NOTICE = f"{DISCLAIMER} Recheck entry and stop on the live price before trading."


def parse_formats(text: str) -> list[str]:
    """'md,csv' -> ['md', 'csv']. Unknown format -> ValueError."""
    formats = [f.strip().lower() for f in text.split(",") if f.strip()]
    unknown = [f for f in formats if f not in FORMATS]
    if unknown or not formats:
        raise ValueError(f"unknown export format {unknown or text!r}: use {', '.join(FORMATS)}")
    return list(dict.fromkeys(formats))


def data_date(results: list[TickerAnalysis]) -> str:
    dates = [r.data_date for r in results if r.data_date]
    return str(max(dates)) if dates else "N/D"


def to_json(results: list[TickerAnalysis], cfg: Config, now: datetime) -> str:
    doc = {
        "disclaimer": NOTICE,
        "generated_at": now.isoformat(timespec="seconds"),
        "data_date": data_date(results),
        "sources": SOURCES,
        "config": dataclasses.asdict(cfg),
        "results": [dataclasses.asdict(r) for r in results],
    }
    return json.dumps(doc, indent=2, default=str, ensure_ascii=False)


def to_csv(results: list[TickerAnalysis], now: datetime) -> str:
    """One row per ticker. Header lines start with '#' (pandas: read_csv(comment='#'))."""
    criteria = list(
        dict.fromkeys(
            c.name for r in results for c in [*r.fundamental, *r.technical, r.earnings] if c
        )
    )
    buf = io.StringIO()
    buf.write(f"# {NOTICE}\n")
    buf.write(f"# generated_at: {now:%Y-%m-%d %H:%M}; data_date: {data_date(results)}\n")
    buf.write(f"# sources: {' | '.join(SOURCES)}\n")
    w = csv.writer(buf, lineterminator="\n")
    plan_cols = ["entry", "stop", "target", "shares", "binding", "position_value", "effective_risk"]
    w.writerow(
        ["ticker", "verdict", "data_date", *plan_cols, "plan_discarded", "reasons"]
        + [f"{name} {part}" for name in criteria for part in ("status", "value")]
    )
    for r in results:
        p = r.plan
        by_name = {c.name: c for c in [*r.fundamental, *r.technical, r.earnings] if c}
        cells = []
        for name in criteria:
            c = by_name.get(name)
            cells += [c.status if c else "", "" if c is None or c.value is None else c.value]
        w.writerow(
            [r.ticker, r.verdict, r.data_date or ""]
            + [getattr(p, col) if p else "" for col in plan_cols]
            + [(p.discarded or "") if p else "", "; ".join(r.reasons)]
            + cells
        )
    return buf.getvalue()


def _md(text) -> str:
    return "N/D" if text is None else str(text).replace("|", "\\|").replace("\n", "<br>")


def to_markdown(results: list[TickerAnalysis], cfg: Config, now: datetime) -> str:
    out = [
        "# ilovestock report",
        "",
        f"> [!WARNING]\n> {NOTICE}",
        "",
        f"- Generated: {now:%Y-%m-%d %H:%M}",
        f"- Data as of: {data_date(results)}",
        *[f"- Source: {s}" for s in SOURCES],
        f"- Portfolio: capital {cfg.capital:,.0f}, risk {cfg.risk_pct:g}% per trade, "
        f"max position {cfg.max_position_pct:g}%, take profit {cfg.r_multiple:g}R, "
        f"entry {cfg.entry_mode}, growth {cfg.growth_basis}",
        "",
        "## Summary",
        "",
        "| Ticker | Verdict | Entry | Stop | Target | Shares | FAIL / N/D criteria |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        p = r.plan
        cols = [p.entry, p.stop, p.target, p.shares] if p else [None] * 4
        out.append(
            "| "
            + " | ".join(_md(x) for x in [r.ticker, r.verdict, *cols, "<br>".join(r.reasons)])
            + " |"
        )
    for r in results:
        out += ["", f"## {r.ticker}: {r.verdict} (data as of {r.data_date or 'N/D'})", ""]
        if r.error:
            out.append(f"Data error: {_md(r.error)}")
            continue
        for title, items in (
            ("Fundamental", [*r.fundamental, r.earnings]),
            ("Technical", r.technical),
        ):
            out += [
                f"### {title}",
                "",
                "| Criterion | Value | Threshold | Status | Note |",
                "|---|---|---|---|---|",
            ]
            out += [
                f"| {_md(c.name)} | {_md(c.value)} | {_md(c.threshold)} | {c.status} | "
                f"{_md(c.note)} |"
                for c in items
                if c
            ]
            out.append("")
        if r.plan:
            out += ["### Trade plan", "", *[f"- {line}" for line in plan_lines(r.plan)]]
    out += ["", "---", "", f"*{NOTICE}*", ""]
    return "\n".join(out)


def write_reports(
    results: list[TickerAnalysis], formats: list[str], out_dir: Path, cfg: Config, now: datetime
) -> list[Path]:
    """Write reports/YYYY-MM-DD_HHMM/{report.md,results.csv,results.json}; return the paths."""
    run_dir = out_dir / f"{now:%Y-%m-%d_%H%M}"
    run_dir.mkdir(parents=True, exist_ok=True)
    render = {
        "md": lambda: to_markdown(results, cfg, now),
        "csv": lambda: to_csv(results, now),
        "json": lambda: to_json(results, cfg, now),
    }
    paths = []
    for fmt in formats:
        path = run_dir / FORMATS[fmt]
        path.write_text(render[fmt](), encoding="utf-8")
        paths.append(path)
    return paths
