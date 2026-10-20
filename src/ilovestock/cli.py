"""CLI: thin layer over the core. No business rules here."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ilovestock import config as cfgmod
from ilovestock import inputs
from ilovestock.analysis import analyze as analyze_ticker
from ilovestock.models import DISCLAIMER
from ilovestock.providers import finviz
from ilovestock.providers.base import BENCHMARK
from ilovestock.providers.cache import CachedProvider
from ilovestock.providers.yahoo import YahooProvider
from ilovestock.report import print_report

app = typer.Typer(help=f"Verdetto BUY / NO-BUY + piano di trade per azioni USA. {DISCLAIMER}")
config_app = typer.Typer(help="Gestione del file di configurazione.")
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
    console.print(f"[red]Errore:[/] {msg}")
    raise typer.Exit(1)


@app.command()
def analyze(
    tickers: Annotated[list[str] | None, typer.Argument(help="Ticker, es. HZO NIO")] = None,
    watchlist: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="Un ticker per riga")
    ] = None,
    finviz_url: Annotated[str | None, typer.Option(help="URL screener Finviz")] = None,
    capital: Annotated[float | None, typer.Option(help="Capitale azionario")] = None,
    risk_pct: Annotated[float | None, typer.Option(help="Perdita max per trade, %")] = None,
    max_position_pct: Annotated[float | None, typer.Option(help="Peso max per titolo, %")] = None,
    r_multiple: Annotated[float | None, typer.Option(help="Take profit in multipli di R")] = None,
    growth_basis: Annotated[GrowthBasis | None, typer.Option(help="Base crescita")] = None,
    entry_mode: Annotated[EntryMode | None, typer.Option(help="Punto di ingresso")] = None,
    allow_missing: Annotated[
        bool, typer.Option(help="Dati fondamentali N/D non bloccano il BUY (restano N/D)")
    ] = False,
    detail: Annotated[bool, typer.Option(help="Dettaglio per criterio")] = False,
    config_file: Annotated[Path | None, typer.Option("--config", help="File config")] = None,
) -> None:
    """Analizza uno o più ticker con le regole del corso."""
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
    except (cfgmod.ConfigError, ValueError) as e:
        _fail(str(e))

    screened: list[str] = []
    if finviz_url:
        try:
            screened = finviz.screener_tickers(finviz_url)
        except Exception as e:
            _fail(f"import Finviz fallito: {e}")
    all_tickers = inputs.merge(cli_tickers, wl, screened)
    if not all_tickers:
        _fail("nessun ticker: passa TICKER, --watchlist o --finviz-url")

    provider = CachedProvider(YahooProvider())
    try:
        bench = provider.history(BENCHMARK)["Close"]
    except Exception as e:
        _fail(f"benchmark {BENCHMARK} non disponibile: {e}")

    console.print(f"[dim]{finviz.WARNING}[/]")
    results = []
    with console.status("Analisi in corso...") as status:
        for t in all_tickers:
            status.update(f"Analisi {t}...")
            results.append(
                analyze_ticker(
                    t, provider, bench, finviz.institutional, cfg, date.today(), allow_missing
                )
            )
    print_report(results, detail, console)


@config_app.command("init")
def config_init(
    force: Annotated[bool, typer.Option(help="Sovrascrive un file esistente")] = False,
) -> None:
    """Scrive il file di config con i default del corso."""
    path = cfgmod.CONFIG_PATH
    if path.exists() and not force:
        _fail(f"{path} esiste già (usa --force per sovrascrivere)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cfgmod.TEMPLATE, encoding="utf-8")
    console.print(f"Config scritto in {path}")


@config_app.command("show")
def config_show() -> None:
    """Config effettivo (default + file)."""
    try:
        console.print(cfgmod.dump(cfgmod.load()), markup=False, highlight=False)
    except cfgmod.ConfigError as e:
        _fail(str(e))


@config_app.command("path")
def config_path() -> None:
    """Percorso del file di config."""
    console.print(str(cfgmod.CONFIG_PATH))
