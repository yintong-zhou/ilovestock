"""CLI: thin layer over the core. No business rules here."""

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ilovestock import config as cfgmod
from ilovestock import export, inputs
from ilovestock.analysis import analyze as analyze_ticker
from ilovestock.models import DISCLAIMER
from ilovestock.providers import finviz
from ilovestock.providers.base import BENCHMARK
from ilovestock.providers.cache import CachedProvider
from ilovestock.providers.yahoo import YahooProvider
from ilovestock.report import print_report

app = typer.Typer(help=f"BUY / NO-BUY verdict + trade plan for US stocks. {DISCLAIMER}")
config_app = typer.Typer(help="Manage the config file.")
app.add_typer(config_app, name="config")
console = Console()


class GrowthBasis(StrEnum):
    qoq = "qoq"
    yoy = "yoy"


class EntryMode(StrEnum):
    breakout = "breakout"
    pullback = "pullback"
    restart = "restart"


def _fail(msg: str) -> None:
    console.print(f"[red]Error:[/] {msg}")
    raise typer.Exit(1)


@app.command()
def analyze(
    tickers: Annotated[list[str] | None, typer.Argument(help="Tickers, e.g. HZO NIO")] = None,
    watchlist: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="One ticker per line")
    ] = None,
    finviz_url: Annotated[str | None, typer.Option(help="Finviz screener URL")] = None,
    capital: Annotated[float | None, typer.Option(help="Equity capital")] = None,
    risk_pct: Annotated[float | None, typer.Option(help="Max loss per trade, %")] = None,
    max_position_pct: Annotated[float | None, typer.Option(help="Max weight per stock, %")] = None,
    r_multiple: Annotated[float | None, typer.Option(help="Take profit as a multiple of R")] = None,
    growth_basis: Annotated[GrowthBasis | None, typer.Option(help="Growth basis")] = None,
    entry_mode: Annotated[EntryMode | None, typer.Option(help="Entry point")] = None,
    allow_missing: Annotated[
        bool, typer.Option(help="N/D fundamental data does not block BUY (still shown as N/D)")
    ] = False,
    detail: Annotated[bool, typer.Option(help="Per-criterion detail")] = False,
    export_formats: Annotated[
        str | None, typer.Option("--export", help="Report files, e.g. md,csv,json")
    ] = None,
    out_dir: Annotated[Path, typer.Option(help="Report directory")] = Path("reports"),
    config_file: Annotated[Path | None, typer.Option("--config", help="File config")] = None,
) -> None:
    """Analyze one or more tickers with the course rules."""
    try:
        cfg = cfgmod.load(
            config_file,
            {
                "capital": capital,
                "risk_pct": risk_pct,
                "max_position_pct": max_position_pct,
                "r_multiple": r_multiple,
                "growth_basis": growth_basis and growth_basis.value,
                "entry_mode": entry_mode and entry_mode.value,
            },
        )
        cli_tickers = [inputs.normalize(t) for t in tickers or []]
        wl = inputs.read_watchlist(watchlist) if watchlist else []
        formats = export.parse_formats(export_formats) if export_formats else []
    except (cfgmod.ConfigError, ValueError) as e:
        _fail(str(e))

    screened: list[str] = []
    if finviz_url:
        try:
            screened = finviz.screener_tickers(finviz_url)
        except Exception as e:
            _fail(f"Finviz import failed: {e}")
    all_tickers = inputs.merge(cli_tickers, wl, screened)
    if not all_tickers:
        _fail("no tickers: pass TICKER, --watchlist or --finviz-url")

    provider = CachedProvider(finviz.FinvizProvider(YahooProvider()))
    try:
        bench = provider.history(BENCHMARK)["Close"]
    except Exception as e:
        _fail(f"benchmark {BENCHMARK} not available: {e}")

    console.print(f"[dim]{finviz.WARNING}[/]")
    results = []
    with console.status("Analyzing...") as status:
        for t in all_tickers:
            status.update(f"Analyzing {t}...")
            results.append(analyze_ticker(t, provider, bench, cfg, date.today(), allow_missing))
    print_report(results, detail, console)
    if formats:
        for path in export.write_reports(results, formats, out_dir, cfg, datetime.now()):
            console.print(f"Report written: {path}")


@config_app.command("init")
def config_init(
    force: Annotated[bool, typer.Option(help="Overwrite an existing file")] = False,
) -> None:
    """Write the config file with course defaults."""
    path = cfgmod.CONFIG_PATH
    if path.exists() and not force:
        _fail(f"{path} already exists (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cfgmod.TEMPLATE, encoding="utf-8")
    console.print(f"Config written to {path}")


@config_app.command("show")
def config_show() -> None:
    """Effective config (defaults + file)."""
    try:
        console.print(cfgmod.dump(cfgmod.load()), markup=False, highlight=False)
    except cfgmod.ConfigError as e:
        _fail(str(e))


@config_app.command("path")
def config_path() -> None:
    """Config file path."""
    console.print(str(cfgmod.CONFIG_PATH))
