<div align="center">

<img src="web/public/logo.png" alt="iLoveStock logo" width="120">

# iLoveStock

**Rule-based BUY / NO-BUY screening and trade plans for US stocks**

[![CI](https://github.com/yintong-zhou/ilovestock/actions/workflows/ci.yml/badge.svg)](https://github.com/yintong-zhou/ilovestock/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-0B3D62)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-1F6F8B)](https://github.com/yintong-zhou/ilovestock/blob/main/LICENSE)

[Overview](#overview) • [Getting started](#getting-started) • [Usage](#usage) • [How the verdict works](#how-the-verdict-works) • [Data and limits](#data-and-limits) • [Development](#development)

</div>

> [!WARNING]
> ilovestock is an **educational screening tool, not financial advice**. A BUY verdict means "every rule of the method passed on the data available", not "you should buy". Data comes from unofficial sources and can be wrong, late or missing. Always recheck entry and stop on the live price before trading.

## Overview

Applying a stock-picking method by hand is slow: about seven fundamental filters, four technical indicators on mixed timeframes, the distance to the next earnings report and position sizing, for every ticker. Common screeners lack some of the indicators (Donchian 10 weeks, ADX 18 days), and charting tools don't compute stops or share counts.

ilovestock does that work for you. It combines fundamental analysis, to judge whether a company is worth owning, with technical analysis, to judge whether now is a moment of possible growth. For each US ticker (NASDAQ, NYSE, AMEX), it:

1. Downloads prices and financials, with a daily disk cache.
2. Checks each fundamental, earnings and technical criterion against fixed thresholds.
3. Builds a trade plan: entry, technical stop, take profit in R multiples, number of shares.
4. Returns **BUY** only if everything passes. Otherwise it returns **NO-BUY** and lists the criteria that failed or had no data. Prices quoted in a currency other than USD are rejected.

Example: `ilovestock analyze AAPL --detail` (data as of 2026-10-20):

![ilovestock analyze AAPL --detail: NO-BUY verdict with per-criterion detail and trade plan](https://raw.githubusercontent.com/yintong-zhou/ilovestock/main/docs/img/analyze-aapl.svg)

### Features

- **Per-criterion results.** Each criterion reports its value, threshold and status: `PASS`, `FAIL` or `N/D`. Missing data is always `N/D` and never counts as a pass.
- **Fundamental analysis.** Sales and EPS growth, ROE, institutional ownership and transactions, dividend yield, market cap band.
- **Earnings check.** No entry when the next earnings report is 10 days away or less, nor before the market has reacted to the last one.
- **Technical confirmations.** Relative strength vs the S&P 500, Donchian breakout on the weekly close after a consolidation, with volume, DMI/ADX and SMA 200, all with fixed parameters.
- **Trade plan.** Entry, technical stop, take profit in R multiples, and position sizing capped by maximum exposure.
- **Report files.** Markdown, CSV and JSON export, each with data date, sources and disclaimer. In the web app, History and Watchlist download as PDF.
- **Fundamentals-first screener.** Finds the US-listed stocks that pass every fundamental rule and ranks them by quality, ready for the full analysis.
- **Flexible input.** Tickers on the command line, a watchlist file and a Finviz screener URL can be combined; duplicates are removed.
- **Layered config.** Built-in defaults, then a TOML file, then CLI options.

## Getting started

### Prerequisites

- Python 3.11 or later
- Node.js, to build the web UI

### Installation

ilovestock is not published on PyPI: install it from the repository.

```bash
git clone https://github.com/yintong-zhou/ilovestock.git
cd ilovestock
cd web && npm ci && npm run build && cd ..   # builds the web UI into the package
pip install .
```

To work on the code, see [Development](#development).

> [!CAUTION]
> Fundamentals come from Finviz through scraping, and that may violate Finviz's terms of service. Finviz quotes are also delayed 15–20 minutes. Use ilovestock only if you accept that.

Check that the CLI works:

```bash
ilovestock --help
```

## Usage

### Find candidates (fundamentals first)

```bash
ilovestock screen            # top 20
ilovestock screen --max 10   # 1 to 50
ilovestock screen --include-large   # also large and giant caps
```

The screener builds a Finviz screener query from your config thresholds, then checks every candidate with the same fundamental and earnings rules as `analyze`. A stock is listed only if every one of those criteria is `PASS`. The stocks that pass are ranked by a **quality score**, because sales growth alone says nothing about profit:

- **ROIC**: operating profit per dollar invested in the business (Finviz).
- **Operating margin change**: operating margin of the last quarter minus the same quarter a year earlier, in points (Yahoo). A falling margin means costs grow faster than sales.

Each stock gets a rank on both measures within the stocks that passed. Each rank becomes a percentile, 0–100 (100 = best, 0 = worst of the group), and the score is the average of the two percentiles. The score never changes a verdict: `analyze --detail` shows ROIC and margin change as an informative `Quality` row.

The list is saved as a watchlist (default `reports/screen-YYYY-MM-DD.txt`, change it with `--out`) and the command prints the next step:

```bash
ilovestock analyze --watchlist reports/screen-2026-10-22.txt
```

- Only stocks with complete Finviz data are searched: a stock with a missing Finviz value on a filtered field (or no Finviz market cap) never reaches the candidates, even if Yahoo has it.
- Dividends and market cap are not filtered on Finviz: its dividend filter uses the forward estimate (the rule uses the last 12 months) and its market cap filter takes a single band. Finviz rows come sorted by market cap instead: large and giant caps are skipped, and the list ends at the first nano cap, with the same bands as the rule.
- `--include-large` (web: the "Include large and giant caps" box) also searches large and giant caps and skips the Market cap rule, so they can pass. The method is for micro to mid caps: `analyze` still fails them on Market cap, so their verdict stays NO-BUY.
- A search stops with more than `max_candidates` micro/small/mid candidates (default 100; `max_candidates_large`, default 200, with `--include-large`), or more than 1000 Finviz rows before the first nano cap: tighten the thresholds or raise the cap in the config (web: Settings). Each candidate takes a few seconds. An unreadable Finviz page (changed markup) stops the search with an error, never with a partial list.
- With `growth_basis = "qoq"` (the default), growth is not filtered on Finviz (it only has year-on-year), so more candidates come back and a search reaches `max_candidates` sooner. `growth_basis = "yoy"` also filters growth on Finviz.

### Analyze tickers

```bash
# One or more tickers
ilovestock analyze HZO NIO

# Per-criterion detail and the full trade plan for each ticker
ilovestock analyze HZO --detail

# Combine inputs: tickers + watchlist + Finviz screener
ilovestock analyze HZO --watchlist my_list.txt --finviz-url "https://finviz.com/screener.ashx?v=111&f=cap_small"

# Override risk parameters for this run only
ilovestock analyze HZO --capital 15000 --risk-pct 0.5 --r-multiple 4

# Save the results as report files
ilovestock analyze HZO NIO --export md,csv,json
```

A watchlist is a text or CSV file with one ticker per line. Lines starting with `#` and a `Ticker` / `Symbol` header are ignored.

| Option | Meaning |
|---|---|
| `TICKER ...` | One or more tickers |
| `--watchlist FILE` | One ticker per line (txt/csv) |
| `--finviz-url URL` | Import tickers from a Finviz screener URL copied from the site |
| `--capital N` | Equity portfolio capital |
| `--risk-pct N` | Max loss per trade, % of capital (above 2 is rejected) |
| `--max-position-pct N` | Max weight per stock, % of capital |
| `--r-multiple N` | Take profit as a multiple of R (below 2, the trade is discarded) |
| `--growth-basis qoq\|yoy` | Growth vs the previous quarter (Yahoo, default), or vs the same quarter last year (Finviz) |
| `--entry-mode breakout\|pullback\|restart` | Entry point used for the trade plan |
| `--allow-missing` | `N/D` fundamental criteria don't block: the verdict is **BUY\*** (incomplete data) instead of BUY, with the `N/D` criteria listed |
| `--max-tickers` | Refuse runs with more tickers than this (default 50, the web app's limit) |
| `--detail` | Per-criterion panel for each ticker |
| `--export md,csv,json` | Write report files (any combination of the three formats) |
| `--out-dir DIR` | Report directory (default `reports`) |
| `--config FILE` | Use a different config file |

### Report files

`--export` writes one folder per run, `reports/YYYY-MM-DD_HHMM/`:

| File | Content |
|---|---|
| `report.md` | Summary table, per-criterion tables and trade plan for each ticker |
| `results.csv` | One row per ticker: verdict, trade plan, status and value of each criterion. Header lines start with `#` (`pandas.read_csv(path, comment="#")`) |
| `results.json` | Everything above plus the effective config, for scripts |

Every file states the data date, the data sources and the disclaimer.

### History

Every analysis, from the terminal or the web app, adds one row per ticker to `~/.config/ilovestock/history.csv`: date, data date, verdict, price, entry, stop, target, shares, reasons, and every criterion with its status and value (as JSON, since criterion names can change). Tickers with a data error are not saved. The file opens in Excel.

In the web app, the **History** page lists the analyzed tickers and, for each one, every analysis with what changed from the previous one (verdict, criteria, price). There you can add a note, edit verdict, price and levels (the analysis is then marked *edited*), and delete one analysis or a ticker's whole history. To delete several tickers at once, tick them in the list (the box in the header ticks the page) and press **Delete selected**: only tickers shown by the active filter are deleted.

**Download PDF** on the History page (the tickers of the active filter, every page) and on the Watchlist page builds a PDF from the saved analyses, with no new download: a summary table, then one page per ticker with every criterion (value, threshold, status, note), the trade plan, the reasons and your note. Every page carries the disclaimer. Watchlist tickers never analyzed are left out. The PDF uses the standard Helvetica font, so characters outside Latin-1 become an ASCII stand-in (`→` becomes `->`) or `?`.

### Configuration

```bash
ilovestock config init    # write the config file with built-in defaults
ilovestock config show    # print the effective config (defaults + file)
ilovestock config path    # print the config file location
```

The config file is `~/.config/ilovestock/config.toml`. CLI options override the file, and the file overrides the built-in defaults:

```toml
[portfolio]
capital = 20000          # equity portfolio capital
risk_pct = 1.0           # max loss per trade (%); above 2 -> rejected
max_position_pct = 10    # max weight per stock (%); above 10 -> rejected

[plan]
r_multiple = 3           # take profit in R; below 2 -> trade discarded
entry_mode = "breakout"  # breakout | pullback | restart

[fundamental]
growth_basis = "qoq"     # qoq (Yahoo) | yoy (Finviz)
sales_growth_min = 20
eps_growth_min = 15
roe_min = 15
institutional_own_max = 80

[market_cap]             # band upper bounds, millions USD
nano_max = 50
micro_max = 300
small_max = 2000
mid_max = 10000
large_max = 200000

[screener]               # Finviz candidates checked one by one, a few seconds each; 1 to 500
max_candidates = 100
max_candidates_large = 200  # with large and giant caps (--include-large)
```

> [!IMPORTANT]
> Technical indicator parameters are fixed constants on purpose: they are not in the config and have no options. The method treats tuning them case by case as a mistake.

## Web app

A local web app on the same core, for this computer only.

```bash
cd web && npm install && npm run build && cd ..   # once, and after frontend changes
ilovestock serve                                   # http://127.0.0.1:3000 (or 3001, 3002… if busy)
```

- **PIN.** The first `ilovestock serve` asks you to set a PIN (4 to 8 digits) in the terminal, never in the browser: no other program on this computer can claim the app first. It is stored hashed in `~/.config/ilovestock/web_pin.json`, never in clear. After 5 wrong attempts, the next ones wait 30 seconds. Forgot it? Run `ilovestock pin reset`, then `ilovestock serve` again.
- **Pages.** Dashboard (the latest saved analysis of every ticker: verdict counts, the criteria that blocked a BUY, the 10 most recent tickers), Portfolio (planned for phase 2), Screener (same search as `ilovestock screen`, with "Analyze these" to fill in the Analysis page and a watchlist download: see [Find candidates](#find-candidates-fundamentals-first)), Analysis (same rules and trade plan as the CLI), History (every saved analysis, with notes, edits and deletion: see [History](#history); the ticker list shows 25 or 50 tickers per page and filters on "all fundamentals PASS" and "all technical PASS"), Watchlist (below), Settings (PIN and the same config file as the CLI).
- **Watchlist.** Stocks you might buy. Add one from a result on the Analysis page or from its History page. Each row shows the latest saved analysis; **Refresh** runs the analysis again and saves it in History. The method uses end-of-day data, so during the session Refresh gives the same result as the last close. The list is `~/.config/ilovestock/watchlist.txt`, one ticker per line (max 50), so the terminal reads it too: `ilovestock analyze --watchlist ~/.config/ilovestock/watchlist.txt`.

> [!IMPORTANT]
> The server listens on `127.0.0.1` only. The PIN is a lock for this computer, not real authentication: do not expose the app on a network.

### Desktop app (Windows)

The same app in its own window, for people who don't use the terminal. It comes as one file, **Installa iLoveStock.exe**, with Python included. Double-click it: it installs for the current user (no administrator rights), puts **iLoveStock** on the desktop and in the Start menu, and opens the app. The window starts the server and stops it when you close it.

- **Windows warning.** The installer is not signed, so Windows shows "Windows protected your PC" ("PC protetto da Windows"). Click **More info**, then **Run anyway**.
- **First start.** The app asks you to choose a PIN (4 to 8 digits) in its own window, then to enter it to unlock, as at every start.
- **Forgot the PIN?** Menu **iLoveStock > Reset PIN…**, then choose a new one. History, watchlist and settings are kept.
- **Uninstall.** Windows Settings > Apps > iLoveStock. Your files in `~/.config/ilovestock` stay.

Build the installer on Windows with Node.js and Python 3.12 (the `py` launcher). It downloads Python 3.12.10 from python.org and the dependencies from PyPI:

```bash
cd desktop && npm install && npm run dist   # desktop/dist/Installa iLoveStock.exe
```

From the repo, `npm start` in `desktop/` opens the same window on the installed `ilovestock` (if the venv is not active: `ILOVESTOCK_BIN=../.venv/Scripts/ilovestock.exe npm start`).

## How the verdict works

**BUY** requires all of the following. Anything else is **NO-BUY**, with the reasons listed. The only exception is `--allow-missing`: if every criterion with data passes and some fundamentals are `N/D`, the verdict is **BUY\*** (incomplete data), never a plain BUY.

### Fundamental

| Criterion | Threshold |
|---|---|
| Sales growth | > 20% |
| EPS growth | > 15% (`N/D` if the comparison quarter is ≤ 0) |
| ROE | > 15% |
| Institutional ownership | < 80% |
| Institutional transactions | > 0% |
| Dividend yield (last 12 months) | = 0 |
| Market cap | micro, small or mid |
| Next earnings | more than 10 days away |

### Technical (fixed parameters)

| Indicator | Timeframe | Condition |
|---|---|---|
| Relative strength vs S&P 500 | weekly | RS above its 52-week SMA |
| Donchian channel, 10 weeks | weekly | Weekly close above the highest high of the 10 previous weeks |
| Consolidation, 10 weeks | weekly | The 10 weeks before the breakout corrected less than 50% (high to low) |
| Breakout volume | weekly | Breakout week volume above the 10-week average |
| DMI, 18 days, Wilder smoothing | daily | ADX rising and below both +DI and −DI |
| SMA 200 | daily | Price above the SMA |
| After last earnings | daily | At least 1 session of reaction after the report, 5 if the reaction moved the price 5% or more |

Weekly criteria use completed weeks only: a breakout counts once the week has closed. During the week they show the last completed week.

### Trade plan

- **Entry**: `breakout` buys at the last close. `pullback` uses the upper Donchian band. `restart` uses the last completed week's high.
- **Stop**: the lowest low of the previous 10 weeks. It is a technical stop, not a monetary one.
- **Take profit**: `entry + r_multiple × (entry − stop)`. If `r_multiple` is below 2, the trade is discarded.
- **Shares**: `floor(capital × risk_pct / (entry − stop))`, reduced if the position would exceed `max_position_pct`. The output says which of the two limits set the share count.
- **Shares** are also capped by the method's limit: `max_position_pct` above 10 is rejected.
- **For information only**: initial trailing stops (Donchian 10 and 8 weeks) and a scale-out hint (½ at 1R, ½ at the target).

## Data and limits

| Data | Source |
|---|---|
| Sales and EPS growth YoY (for `--growth-basis yoy`), ROE, market cap, dividend yield, next earnings date, institutional ownership and transactions | Finviz via `finviz`; Yahoo Finance as fallback for each missing field |
| Daily adjusted prices, dividend history, S&P 500 (`^GSPC`) | Yahoo Finance via `yfinance` (Finviz has no price history) |
| Quarterly sales and EPS (growth with the default `qoq` basis) | Yahoo Finance via `yfinance` |
| Candidate tickers | Finviz screener URL |

Each criterion's note shows where its value came from (`source: Finviz` or `source: Yahoo`).

> [!NOTE]
> - Neither source is official. Either can block requests or change its format without notice. Prices and fundamentals are cached for one day in `~/.cache/ilovestock`.
> - The default growth basis is `qoq`, the method's definition: the last quarter vs the previous one, computed from Yahoo quarters (usually only 4–5 are available). It shows the latest change, but it moves with seasonal businesses (e.g. retail around the holidays). Finviz "Sales Q/Q" and "EPS Q/Q" actually compare with the same quarter last year: they are used with `--growth-basis yoy`.
> - Finviz shows the earnings date without a year, and keeps the last report date until the next one is announced. A past date is used as the last report (for the wait after earnings) and Yahoo's date is used as the next one.
> - Finviz shows `-` for both "no dividend" and "missing". In that case the dividend yield is computed from Yahoo's dividend history.
> - The `finviz` 2.0.0 screener no longer parses the current Finviz site, so ilovestock reads ticker links from the screener pages itself.
> - The method uses end-of-day data. Recheck prices before acting.

## Development

```bash
git clone https://github.com/yintong-zhou/ilovestock.git
cd ilovestock
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest -m "not slow"     # offline tests on recorded fixtures
ruff check .
ruff format --check .
```

Frontend (React + Vite + Tailwind, in `web/`):

```bash
ilovestock serve          # API on :3000
cd web && npm run dev     # http://localhost:5173, /api proxied to :3000
npm run lint
npm run build
```

- Default tests never touch the network. They run on real responses recorded in `tests/fixtures/`.
- Tests marked `slow` hit live Finviz to detect page changes. Run them on purpose with `pytest -m slow`.
- Indicators are checked against TA-Lib, which is a dev dependency.
- To re-record fixtures (this uses the network): `python execution/record_fixtures.py [TICKER] [FINVIZ_URL]`.
- Project rules and release steps: [CONTRIBUTING.md](https://github.com/yintong-zhou/ilovestock/blob/main/CONTRIBUTING.md).

Project layout:

```text
src/ilovestock/
  cli.py          Typer commands (thin layer, no business rules)
  analysis.py     one ticker end to end: data -> criteria -> plan -> verdict
  config.py       TOML defaults, file and CLI overrides
  indicators.py   SMA, Donchian, DMI/ADX, relative strength (pure functions)
  rules/          fundamental, technical, earnings, trade plan, verdict
  providers/      yfinance, Finviz adapter, disk cache
  report.py       Rich terminal output
  export.py       Markdown, CSV and JSON report files
  pdf.py          PDF of saved analyses (History and Watchlist pages)
  api/            FastAPI app and PIN gate for the web app
tests/            offline tests and recorded fixtures
web/              React frontend
desktop/          Electron window around `ilovestock serve`
```

### Roadmap

- Phase 2: managing open positions (hold/sell, trailing stop, sector cap)
