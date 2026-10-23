# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`ilovestock` applies the method of the course "Investire in azioni nel lungo termine" to US stocks:
a BUY / NO-BUY verdict with a trade plan, and a fundamentals-first screener. It has one Python core
and two thin interfaces: a Typer CLI and a local web app (FastAPI + React). It is an educational
tool, not financial advice, and every output must say so.

Read `AGENT.md` (agent rules, 3-layer architecture, autonomy) and `PROJECT.md` (business rules,
open decisions D1-D11) before changing behavior. The "Layout" section of `PROJECT.md` is
outdated: the README's "Project layout" matches the code.

## Commands

The backend runs from the repo root and the frontend from `web/`. On Windows Git Bash, call the venv
tools with `.exe` (`.venv/Scripts/pytest.exe`, `.venv/Scripts/ruff.exe`, `.venv/Scripts/python.exe`).

```bash
pip install -e ".[dev]"                         # dev deps include TA-Lib (indicator reference) and httpx
pytest -m "not slow"                            # default suite: offline, recorded fixtures
pytest tests/test_screener.py::test_screen_ranks_and_cuts   # a single test
pytest -m slow                                  # hits live Finviz/Yahoo: ask the user first
ruff check .
ruff format --check .                           # also formats Python code blocks inside .md files

cd web && npm ci && npm run lint && npm run build   # tsc + vite build into src/ilovestock/static/
ilovestock serve                                 # API + built UI on 127.0.0.1:3000 (first free port)
cd web && npm run dev                            # :5173, /api proxied to :3000

python execution/record_fixtures.py [TICKER] [FINVIZ_URL]   # re-record fixtures (network)
python execution/record_fixtures.py --screen                # default screener page fixture
```

CI (`.github/workflows/ci.yml`) runs ruff, ruff format and `pytest -m "not slow"` on Python 3.11
and 3.13, plus web lint and build. Run all of them before reporting work as done.

Packaging: the built UI (`src/ilovestock/static/`, git-ignored) ships as package data, so build
the frontend before `pip install .` or `python -m build`. Publishing to PyPI is not a goal: the
user decided against it, so installation is from the repository.

## Architecture

**Data flow.** `CLI / API → analysis.analyze_many / screener.screen → providers → rules → verdict`.
`cli.py` and `api/app.py` contain no business rules. They build the provider stack and call the core:

```
CachedProvider(FinvizProvider(YahooProvider()))
```

- `providers/base.py`: `MarketDataProvider` protocol (`history(ticker, period)`,
  `fundamentals(ticker)`), `HISTORY_PERIOD = "2y"`.
- `providers/finviz.py`:
  - **Fundamentals:** Finviz first, per field, with Yahoo as the fallback. Each value records its
    source in `Fundamentals.sources`. A failed fetch from either source sets `Fundamentals.note`.
  - **Note semantics:** a non-empty `note` means "fetch error". `CachedProvider` does not cache
    that snapshot and the screener lists the ticker under `errors`, not as failing the rules.
  - **Page cache:** the `finviz` lib caches quote pages forever in `finviz.main_func.STOCK_PAGE`.
    The provider pops the entry after each call.
- `providers/cache.py`:
  - One file per day in `~/.cache/ilovestock/`.
  - Price files are tagged with the New York session (`-open` before the close, so they are
    refetched after it). Each history period has its own file.
- `providers/yahoo.py`: prices (USD only; today's partial bar dropped), quarterly statements,
  calendar.

**Rules.** `rules/` (fundamental, technical, earnings, trade_plan, verdict) and `indicators.py` are
pure functions over dataclasses from `models.py` and pandas frames. Each criterion yields a
`CriterionResult` with status `PASS` / `FAIL` / `N/D`. `analysis.fundamental_checks` is shared by
`analyze` and `screen`, so both judge fundamentals the same way. Per-ticker errors stay with their
ticker (`TickerAnalysis.error`); only a benchmark (^GSPC) failure aborts a batch.

**Screener** (`screener.py`, design in `docs/superpowers/specs/2026-10-22-fundamental-screener-design.md`):

1. Build a Finviz screener URL from the config thresholds. For each threshold, take the loosest
   bucket that cannot drop a stock the exact rules would keep. Dividends and market cap are not
   filtered on Finviz.
2. Request the rows sorted by market cap descending (`o=-marketcap`) through
   `finviz.screener_rows`. Pages overlap by 5 rows (`r` = 1, 16, 31…). Each page must start at the
   requested row, be sorted, and have as many parsed rows as tickers; otherwise
   `FinvizError`, never a silent partial list.
3. `candidates()` skips large/giant caps and stops at the first nano. It uses the same bands as the
   Market cap rule. Limits: `MAX_CANDIDATES` (100) and `MAX_ROWS` (1000). With `include_large`
   (`--include-large`, web checkbox) large/giant are kept and the screen skips only the Market cap
   rule; `analyze` still fails them on it (user's decision).
4. For each candidate, fetch fundamentals first, then one year of prices (`SCREEN_PERIOD`), and
   apply the exact rules. The stocks that pass are ranked by `quality.py`: ROIC and 1-year
   operating margin change, each turned into a rank percentile; N/D is worst. Quality is
   informational and never changes a verdict.

**Config and files.**

- Precedence: course defaults < `~/.config/ilovestock/config.toml` < CLI options (`config.py`).
- Next to the config: `history.csv` (every analysis, shared by CLI and web), `watchlist.txt` (web
  watchlist, one ticker per line, readable by `analyze --watchlist`) and `web_pin.json`
  (hashed PIN).
- Reports go to `reports/`.

**Web.**

- **API contract:** `api/app.py` exposes `/api/*` behind a PIN session (`api/pin.py`) and
  TrustedHost (127.0.0.1/localhost only). Its Pydantic models define the API ↔ frontend contract,
  which `web/src/types.ts` mirrors.
- **Routing:** `web/src/App.tsx` uses hash routes (`#page/arg`).
- **Shared state in App:** App owns the state that must survive page changes. That covers
  `lastRun`, `lastScreen`, `screening`, `screenError`, and a `locks` counter that drops results
  landing after Lock.
- **Frontend scope:** the frontend displays and collects input. It never re-implements rules.
- **Brand:** fonts and colors come from `brand-guidelines.md`.

## Hard rules

- Indicator parameters (SMA 200d, Donchian 10w, DMI/ADX 18d, RS SMA 52w) are fixed constants,
  never options.
- Missing data → `N/D`, never `PASS`. Reject `risk_pct` > 2; discard trades with R:R < 2.
- Finviz field keys and screener filter codes come from a real response or the lib source, never
  guessed. `test_finviz_accepts_every_generated_filter` checks codes against a recorded page.
- Default tests never touch the network. `tests/conftest.py` blocks `requests` outside `slow`
  tests. Use the `fake_yf` / `fake_finviz` fixtures and recorded files in `tests/fixtures/`. The
  recorded screener pages are sorted by ticker, so sorted-by-cap pages are built in tests
  (`cap_page` in `test_providers.py`).
- Every live Finviz/Yahoo request (manual checks, fixture recording, `pytest -m slow`) needs the
  user's OK first. Ask before `git push`, new dependencies, and creating files in `directives/`.
- The server binds to `127.0.0.1` only; the PIN is a local lock, not authentication.

## Gotchas

- On Windows, Rich output to a cp1252 stdout raises `UnicodeEncodeError`: run with
  `PYTHONIOENCODING=utf-8`.
- For manual runs without touching real config, cache or history:
  - point `USERPROFILE` (or `HOME`) at a temp directory;
  - for the server, use `create_app(pin_path=..., config_path=..., history_path=..., provider=...)`
    with `PinStore(path).set("1234")`.
- After adding a field to `Fundamentals`, today's cached JSON still loads because new fields have
  defaults, but those fields stay empty until the next day's fetch.
- Session handoffs live in `docs/handoff/`; the latest one says where work stopped.
