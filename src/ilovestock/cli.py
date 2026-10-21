"""CLI: thin layer over the core. No business rules here."""

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ilovestock import config as cfgmod
from ilovestock import export, history, inputs
from ilovestock.analysis import analyze_many
from ilovestock.models import DISCLAIMER
from ilovestock.providers import finviz
from ilovestock.providers.base import BENCHMARK
from ilovestock.providers.cache import CachedProvider
from ilovestock.providers.yahoo import YahooProvider
from ilovestock.report import print_report

app = typer.Typer(help=f"BUY / NO-BUY verdict + trade plan for US stocks. {DISCLAIMER}")
config_app = typer.Typer(help="Manage the config file.")
app.add_typer(config_app, name="config")
pin_app = typer.Typer(help="Web app PIN.")
app.add_typer(pin_app, name="pin")
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
        bool, typer.Option(help="N/D fundamentals do not block: verdict BUY* (incomplete data)")
    ] = False,
    detail: Annotated[bool, typer.Option(help="Per-criterion detail")] = False,
    export_formats: Annotated[
        str | None, typer.Option("--export", help="Report files, e.g. md,csv,json")
    ] = None,
    out_dir: Annotated[Path, typer.Option(help="Report directory")] = Path("reports"),
    config_file: Annotated[Path | None, typer.Option("--config", help="File config")] = None,
    max_tickers: Annotated[
        int, typer.Option(help="Refuse larger runs (each ticker hits Finviz and Yahoo)", min=1)
    ] = inputs.MAX_TICKERS,
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
            screened = finviz.screener_tickers(finviz_url, max_tickers)
        except Exception as e:
            _fail(f"Finviz import failed: {e}")
    all_tickers = inputs.merge(cli_tickers, wl, screened)
    if not all_tickers:
        _fail("no tickers: pass TICKER, --watchlist or --finviz-url")
    if len(all_tickers) > max_tickers:
        _fail(f"{len(all_tickers)} tickers: max {max_tickers} (raise it with --max-tickers)")

    provider = CachedProvider(finviz.FinvizProvider(YahooProvider()))
    console.print(f"[dim]{finviz.WARNING}[/]")
    with console.status("Analyzing...") as status:
        try:
            results = analyze_many(
                all_tickers,
                provider,
                cfg,
                date.today(),
                allow_missing,
                lambda t: status.update(f"Analyzing {t}..."),
            )
        except Exception as e:
            _fail(f"benchmark {BENCHMARK} not available: {e}")
    print_report(results, detail, console)
    if saved := history.append(results, datetime.now()):
        console.print(f"[dim]History: {saved} analyses added to {history.HISTORY_PATH}[/]")
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


@app.command()
def serve(port: Annotated[int, typer.Option(help="Local port")] = 8000) -> None:
    """Start the local web app on http://127.0.0.1:PORT (this computer only)."""
    import uvicorn

    from ilovestock.api.app import create_app
    from ilovestock.api.pin import PinError, PinStore

    # The PIN is set here, never over HTTP: no other local process can claim the app first.
    store = PinStore()
    while not store.configured():
        pin = typer.prompt(
            "Set the web app PIN (4 to 8 digits)", hide_input=True, confirmation_prompt=True
        )
        try:
            store.set(pin)
        except PinError as e:
            console.print(f"[red]{e}[/]")

    # 127.0.0.1 only: the app has a PIN, not real authentication.
    console.print(f"ilovestock web app: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


@pin_app.command("reset")
def pin_reset(
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation")] = False,
) -> None:
    """Delete the web PIN: `ilovestock serve` asks for a new one at the next start."""
    from ilovestock.api.pin import PinStore

    store = PinStore()
    if not store.configured():
        console.print("No PIN set.")
        return
    if not yes and not typer.confirm("Delete the web app PIN?"):
        raise typer.Exit(1)
    store.reset()
    console.print("PIN deleted. Restart `ilovestock serve` to set a new one.")
