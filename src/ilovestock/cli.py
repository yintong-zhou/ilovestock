"""CLI: thin layer over the core. No business rules here."""

import logging
import socket
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ilovestock import config as cfgmod
from ilovestock import errorlog, export, history, inputs, screener
from ilovestock.analysis import Progress as ProgressFn
from ilovestock.analysis import analyze_many
from ilovestock.models import DISCLAIMER
from ilovestock.providers import finviz
from ilovestock.providers.base import BENCHMARK
from ilovestock.providers.cache import CachedProvider
from ilovestock.providers.yahoo import YahooProvider
from ilovestock.report import print_report, screen_table

app = typer.Typer(help=f"BUY / NO-BUY verdict + trade plan for US stocks. {DISCLAIMER}")
config_app = typer.Typer(help="Manage the config file.")
app.add_typer(config_app, name="config")
pin_app = typer.Typer(help="Web app PIN.")
app.add_typer(pin_app, name="pin")
console = Console()
logger = logging.getLogger(__name__)


def main() -> None:
    """Console entry point. The log is set up here, not in `app`: tests never write the real one."""
    errorlog.setup()
    app()


class GrowthBasis(StrEnum):
    qoq = "qoq"
    yoy = "yoy"


class EntryMode(StrEnum):
    breakout = "breakout"
    pullback = "pullback"
    restart = "restart"


def _fail(msg: str, logged: bool = False) -> None:
    """With `logged` (inside an `except`), the message and the exception go to the error log."""
    if logged:
        logger.error(msg, exc_info=True)
    console.print(f"[red]Error:[/] {msg}")
    if logged:
        console.print(f"Details: {escape(str(errorlog.LOG_PATH))}")
    raise typer.Exit(1)


@contextmanager
def _progress(first: str) -> Iterator[ProgressFn]:
    """Bar, percentage and phase text of a long run; gone when it ends. Total 0: pulsing bar."""
    columns = SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn()
    with Progress(*columns, TimeElapsedColumn(), console=console, transient=True) as bar:
        task = bar.add_task(first, total=None)
        yield lambda text, done, total: bar.update(
            task, description=escape(text), completed=done, total=total or None
        )


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
    """Analyze one or more tickers with the fundamental and technical rules."""
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
            with _progress("Importing tickers from Finviz"):
                screened = finviz.screener_tickers(finviz_url, max_tickers)
        except Exception as e:
            _fail(f"Finviz import failed: {e}", logged=True)
    all_tickers = inputs.merge(cli_tickers, wl, screened)
    if not all_tickers:
        _fail("no tickers: pass TICKER, --watchlist or --finviz-url")
    if len(all_tickers) > max_tickers:
        _fail(f"{len(all_tickers)} tickers: max {max_tickers} (raise it with --max-tickers)")

    provider = CachedProvider(finviz.FinvizProvider(YahooProvider()))
    console.print(f"[dim]{finviz.WARNING}[/]")
    with _progress("Analyzing") as progress:
        try:
            today = date.today()
            results = analyze_many(all_tickers, provider, cfg, today, allow_missing, progress)
        except Exception as e:
            _fail(f"benchmark {BENCHMARK} not available: {e}", logged=True)
    print_report(results, detail, console)
    if any(r.error for r in results):
        console.print(f"[dim]Data errors: details in {escape(str(errorlog.LOG_PATH))}[/]")
    if saved := history.append(results, datetime.now()):
        noun = "analysis" if saved == 1 else "analyses"
        console.print(f"[dim]History: {saved} {noun} added to {history.HISTORY_PATH}[/]")
    if formats:
        for path in export.write_reports(results, formats, out_dir, cfg, datetime.now()):
            console.print(f"Report written: {path}")


@app.command()
def screen(
    max_results: Annotated[
        int,
        typer.Option("--max", min=1, max=screener.MAX_RESULTS, help="Max stocks in the list"),
    ] = screener.DEFAULT_RESULTS,
    out: Annotated[
        Path | None, typer.Option(help="Watchlist file (default: reports/screen-DATE.txt)")
    ] = None,
    config_file: Annotated[Path | None, typer.Option("--config", help="Config file")] = None,
    include_large: Annotated[
        bool,
        typer.Option(
            help="Also search large and giant caps: the Market cap rule is skipped, "
            "analyze still fails them on it"
        ),
    ] = False,
) -> None:
    """Find US-listed stocks that pass every fundamental rule, ranked by quality (ROIC and
    operating margin change). Only stocks with complete Finviz data are searched."""
    try:
        cfg = cfgmod.load(config_file)
    except cfgmod.ConfigError as e:
        _fail(str(e))
    today = date.today()
    provider = CachedProvider(finviz.FinvizProvider(YahooProvider()))
    console.print(f"[dim]{finviz.WARNING}[/]")
    console.print("[dim]Only stocks with complete Finviz data are searched.[/]")
    with _progress("Searching Finviz") as progress:
        try:
            result = screener.screen(provider, cfg, today, max_results, progress, include_large)
        except finviz.FinvizError as e:
            _fail(str(e), logged=True)
        except Exception as e:
            _fail(f"Finviz screener failed: {e}", logged=True)
    console.print(
        f"{result.candidates} candidates from Finviz, {result.passed} pass every fundamental"
        f" rule{' except Market cap' if include_large else ''},"
        f" showing {len(result.hits)} by quality score"
    )
    if result.errors:
        console.print(
            f"[dim]Skipped for data errors: {', '.join(result.errors)}."
            f" Details: {escape(str(errorlog.LOG_PATH))}[/]"
        )
    if not result.hits:
        console.print("No stock passes every fundamental rule.")
    else:
        console.print(screen_table(result))
        path = out or Path("reports") / f"screen-{today:%Y-%m-%d}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# ilovestock screen {today}: top {len(result.hits)} of {result.passed}"
            f" by quality score. {DISCLAIMER}"
        )
        path.write_text("\n".join([header, *(h.ticker for h in result.hits)]) + "\n", "utf-8")
        console.print(f"Watchlist saved: {escape(str(path))}")
        console.print(f"Next: ilovestock analyze --watchlist {escape(str(path))}")
    console.print(f"[bold yellow]{DISCLAIMER}[/]")


@config_app.command("init")
def config_init(
    force: Annotated[bool, typer.Option(help="Overwrite an existing file")] = False,
) -> None:
    """Write the config file with built-in defaults."""
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


ASK_PIN = "ilovestock: set PIN"  # read by desktop/main.js


def free_port(start: int = 3000) -> int:
    """First port from `start` up that 127.0.0.1 can bind."""
    for port in range(start, 65536):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise OSError(f"no free port from {start}")


@app.command()
def serve(
    port: Annotated[
        int | None, typer.Option(help="Local port (default: first free from 3000)")
    ] = None,
) -> None:
    """Start the local web app on http://127.0.0.1:PORT (this computer only)."""
    import uvicorn

    from ilovestock.api.app import create_app
    from ilovestock.api.pin import PinError, PinStore

    # The PIN is set here, never over HTTP: no other local process can claim the app first.
    store = PinStore()
    while not store.configured():
        if sys.stdin.isatty():
            pin = typer.prompt(
                "Set the web app PIN (4 to 8 digits)", hide_input=True, confirmation_prompt=True
            )
        else:
            # No terminal: the desktop window answers this line with the PIN on stdin.
            print(ASK_PIN, flush=True)
            pin = sys.stdin.readline().strip()
            if not pin:
                _fail("No PIN set. Run `ilovestock serve` in a terminal once to set it.")
        try:
            store.set(pin)
        except PinError as e:
            console.print(f"[red]{e}[/]")

    # Errors also go to stderr: this terminal shows them, and the desktop app shows them when the
    # server stops. uvicorn's own loggers reach the root logger (log_config=None): the CSV too.
    stderr = logging.StreamHandler()
    stderr.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(stderr)

    # 127.0.0.1 only: the app has a PIN, not real authentication.
    port = port or free_port()
    console.print(f"ilovestock web app: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning", log_config=None)


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
