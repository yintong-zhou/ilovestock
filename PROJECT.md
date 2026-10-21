# ilovestock — Python CLI: buy/no-buy verdict + trade plan for US stocks

Educational screening tool, not financial advice. Every output (terminal and files) must say so.

## Agent rules
- Direct user instructions override this file.
- Verify before reporting done: `pytest -m "not slow"`, `ruff check .`, `ruff format --check .`.
- Without asking: read, edit in scope, run the commands above.
- Ask first: git push; dependencies outside Stack; `slow` tests (they hit live Finviz); implementing an open decision (D1-D11) that has no Proposal.
- Open decision with a Proposal: implement the Proposal as config default, note it in the PR.
- Hard limits:
  - Technical indicator parameters are fixed constants, never options (the course lists per-case tuning as a mistake).
  - Reject `risk_pct` > 2. Discard a trade with R:R < 2.
  - Missing data → `N/D`. Never turn it into `PASS`.
  - Finviz field keys: read the library source or a real response. Do not guess.
  - No network in default tests or CI: use recorded fixtures.

## Goal
- Per US ticker (NASDAQ, NYSE, AMEX; benchmark S&P 500): apply course fundamental + technical rules → verdict BUY / NO-BUY + trade plan (entry, stop, take profit, shares).
- Output: terminal table + MD/CSV/JSON export.
- Users: author (personal use), then retail investors following the method (open source).
- Why: by hand the method needs ~7 fundamental filters, 4 indicators on mixed timeframes, earnings distance and position sizing. The Finviz screener lacks Donchian 10w and ADX 18d; charts don't compute stop or shares.

## Scope
**In (v1):**
- US market only.
- Buy / no-buy on stocks not owned.
- Trade plan: entry, stop, take profit, shares.
- Inputs: CLI tickers, watchlist file, Finviz screener import (combinable).
- Output: terminal table + MD/CSV/JSON.
- Capital and risk params: config file as base, CLI options override.

**Out (for now):**
- Backtesting.
- Broker order execution.
- Alerts and notifications.
- Non-US markets (Italy, Europe).
- Phase 2 (planned, not v1): portfolio management and hold/sell on open positions: trailing stop, cut exposure before earnings, 20% sector cap, 1-month pause after -10% portfolio or 7 consecutive losses, scale in/out.

## Features
1. Fundamental analysis with course thresholds.
2. Technical analysis, 4 confirmations.
3. Earnings check: no entry near next earnings.
4. Trade plan: technical stop, target in R multiples, position sizing.
5. Per-criterion verdict: value, threshold, status (PASS / FAIL / N/D).
6. Multiple inputs: tickers, watchlist, Finviz import.
7. Exportable reports (MD, CSV, JSON) + colored terminal table.

## Stack (proposal, to confirm)
- Python 3.11+ (`tomllib` for config; `finviz` needs ≥3.10)
- Typer + Rich (author's choice)
- pandas + numpy
- yfinance
- `finviz` (PyPI, github.com/mariostoev/finviz, MIT, unofficial; pin the version)
- pytest, ruff, GitHub Actions

## Data sources
| Data | Source | Notes |
|---|---|---|
| Daily adjusted prices, S&P 500 (^GSPC) | yfinance | Unofficial, rate-limited: needs cache |
| Quarterly Sales and EPS, ROE, market cap, dividend | yfinance | Usually only 4-5 quarters |
| Next earnings date | yfinance, cross-check with Finviz | Check data quality |
| Institutional ownership and transactions | Finviz (`finviz` lib) | Not in yfinance. Field keys unverified |
| Candidate tickers | Finviz `Screener.init_from_url` | Course filters set on the site, URL copied |

**`finviz` library (README):**
- `Screener(filters=[...], table="Overview", order="price")`; `Screener.init_from_url(url)`; `to_dataframe()` (needs pandas), `to_csv()`, `to_sqlite()`; `request_method="async"`.
- Tables: Overview, Valuation, Financial (ROA, ROE, ROI, margins), Ownership (insider, institutional), Performance, Technical.
- `finviz.get_stock("TICKER")`: 90+ data points.
- v2.0 fixed scraping broken by Finviz site changes.
- Authors warn: use may violate Finviz ToS; quotes delayed 15 min (NASDAQ), 20 min (NYSE, AMEX); not for live trading.
- To verify in code: exact keys for institutional ownership/transactions, EPS Q/Q, Sales Q/Q, ROE, dividend, earnings date (README doesn't list them).
- Finviz "qtr over qtr" fields are YoY (Finviz help page), not sequential.

**Existing prototype:** `screener_3q_usa.py` (indicators + basic checks, no Finviz). Indicators tested on synthetic data only; the yfinance part never ran on real data. Starting point, not verified code.

## Layout
```
src/
  cli.py                 Typer commands
  config.py              TOML + CLI override
  models.py              dataclasses: CriterionResult(name, status, value, threshold, note), TradePlan, TickerAnalysis
  providers/base.py      Protocol MarketDataProvider
  providers/yahoo.py     prices, financials, calendar
  providers/finviz.py    adapter over finviz lib: ticker import + institutional data
  providers/cache.py     disk cache (Parquet/JSON)
  indicators/            sma.py donchian.py dmi.py relative_strength.py
  rules/fundamental.py   fundamental criteria
  rules/technical.py     4 technical confirmations
  rules/earnings.py
  rules/trade_plan.py    entry, stop, target
  rules/sizing.py
  rules/verdict.py
  report/                terminal.py (Rich) markdown.py csv_.py json_.py
tests/
pyproject.toml  README.md  LICENSE (TBD)
```
- Every provider implements the same interface so yfinance can be swapped without touching rules.
- Indicators and rules are pure functions on DataFrames (testable offline).
- Criterion status: `PASS`, `FAIL`, `N/D`.

## CLI
```
ilovestock analyze [TICKER ...] [options]
ilovestock config init     # write config with course defaults
ilovestock config show     # effective config (file + overrides)
ilovestock config path
```
| Option | Meaning |
|---|---|
| `TICKER ...` | one or more tickers (e.g. `HZO NIO`) |
| `--watchlist FILE` | one ticker per line (txt/csv) |
| `--finviz-url URL` | import tickers from a Finviz screener URL copied from the site |
| `--capital N` | equity portfolio capital |
| `--risk-pct N` | max loss per trade, % of capital |
| `--max-position-pct N` | max weight per stock |
| `--r-multiple N` | take-profit multiple of R |
| `--growth-basis qoq\|yoy` | growth calculation basis (see D2) |
| `--export md,csv,json` | report formats |
| `--out-dir DIR` | report directory |
| `--detail` | per-criterion detail per ticker |

- Inputs combine: final list = union of tickers, deduplicated.
- Precedence: CLI option > config file > course default.
- Terminal: summary table (ticker, verdict, entry, stop, target, shares, failed criteria); `--detail` adds a panel per ticker.
- Files: `reports/YYYY-MM-DD_HHMM/{report.md,results.csv,results.json}`, each with data date, sources, disclaimer.

`~/.config/ilovestock/config.toml`:
```toml
[portfolio]
capital = 20000          # equity portfolio capital
risk_pct = 1.0           # max loss per trade (%); above 2 → reject
max_position_pct = 10    # max weight per stock (%)

[plan]
r_multiple = 3           # take profit; below 2 → trade discarded
entry_mode = "breakout"  # breakout | pullback | restart

[fundamental]
growth_basis = "yoy"     # yoy | qoq (see D2)
sales_growth_min = 20
eps_growth_min = 15
roe_min = 15
institutional_own_max = 80
```

## Business rules (course)
**Fundamental:**
| Criterion | Threshold |
|---|---|
| Sales growth | > 20% |
| EPS growth | > 15% |
| ROE | > 15% |
| Institutional ownership | < 80% |
| Institutional transactions | > 0% |
| Dividend yield | = 0 |
| Market cap | micro/small/mid ok; nano very risky; large/giant reduced upside |
| Earnings | never buy near earnings: PASS only if next earnings date is > 10 days away |

**Technical, fixed parameters:**
| Indicator | Timeframe | Params | Condition |
|---|---|---|---|
| Relative strength vs S&P 500 | weekly | SMA 52 on RS | RS > SMA |
| Donchian channel | weekly | 10 weeks | price > upper band (max of the 10 previous weeks) |
| Directional Movement | daily | 18 days, Wilder smoothing | ADX rising and below both +DI and -DI |
| SMA | daily | 200 | price > SMA |

**Trade plan:**
1. Entry: course has 3 points (breakout, pullback, restart after pullback). v1 computes the level for `entry_mode`.
2. Stop: below the most important previous low. Technical, not monetary.
3. Take profit = entry + `r_multiple` × (entry − stop). Min 2R (ideal 3-5R); below 2R discard.
4. Shares = `floor(max_loss / (entry − stop))`, `max_loss = capital × risk_pct`.
5. Exposure cap: position value ≤ `max_position_pct` of capital. If the cap binds, reduce shares and report which constraint won.
6. `risk_pct` bands: < 0.5% very conservative, 0.5-1% moderate, 1-2% aggressive, > 2% rejected (course: destroys the account).
7. Informational, non-blocking: initial trailing stop below the lower Donchian band 10w (8w for a faster exit); scale-out hint (½ at 1R + ½ above 3R).

**Verdict:**
- BUY: all fundamental criteria PASS, earnings not imminent, 4 technical confirmations PASS, R:R ≥ 2, shares ≥ 1.
- NO-BUY otherwise, listing FAIL and N/D criteria.

## Tests
- No network in CI.
- Indicators: compare with an independent implementation (dev dependency pandas-ta or TA-Lib) on fixed price series.
- Providers: recorded fixtures; missing-data cases.
- Finviz adapter: recorded responses + a contract test against the live site, marked `slow`, not run in CI (detects page-structure changes).
- Sizing, course examples:
  - max_loss 100, entry 50, stop 45 → 20 shares
  - max_loss 100, entry 50, stop 49 → 100 shares
  - capital 20,000 with 10% cap → max 2,000 value → 40 shares at 50; effective risk 40 instead of 100
- Verdict: one case per criterion that can block a buy.

## Open-source checklist
- README: install, command examples, output screenshot.
- Disclaimer "not financial advice" in README and every report.
- LICENSE, CONTRIBUTING, CI with lint + tests.
- Data-limits section (unofficial sources, financials coverage).

## Milestones
No deadlines (spare-time development). Ordered by dependency.
| Milestone | Content | Done when |
|---|---|---|
| M0 Setup | Repo, `pyproject.toml`, layout, lint, empty CI, `ilovestock --help` | CI runs, CLI starts |
| M1 Data | yfinance provider with cache; data models | Prices, financials, calendar for a ticker download and reload from cache |
| M2 Indicators | SMA, Donchian, DMI/ADX, relative strength | Tests green vs reference implementation |
| M3 Rules | Fundamental, technical, earnings, verdict aggregation | `analyze TICKER` prints per-criterion result |
| M4 Trade plan | Entry, stop, take profit, sizing, cap, validations | Course examples give 20 / 100 / 40 shares |
| M5 Input + config | Watchlist, Finviz import (adapter over `finviz`), TOML, CLI override | 3 inputs combine; parameter precedence tested |
| M6 Report | Rich table, MD/CSV/JSON export | 3 files carry date, sources, disclaimer |
| M7 Release | README, license, docs, first public release | `pip install` works from a clean repo |
| Phase 2 | Portfolio, hold/sell, sector cap, pauses | Plan after v1 |

## Open decisions
**Before M3-M4:**
- D1 ROE: the course text says "ROE > 15% Q/Q" but the screener table says "ROE > 15%". Level or change? **Decided: level (ROE > 15%).**
- D2 Q/Q definition: course = vs previous quarter; Finviz fields are YoY, so Finviz data is YoY; `qoq` needs yfinance quarterly financials. **Decided (2026-10-20): default `yoy` from Finviz, option `qoq` from yfinance.**
- D3 Missing institutional data (ticker lacks it or the library fails). Proposal: criterion `N/D`, verdict NO-BUY reason "missing data", option `--allow-missing` to skip knowingly. **Decided: as proposed; with `--allow-missing` the verdict is `BUY*` (incomplete data), never a plain BUY.**
- D4 Market cap thresholds: course names the bands (nano, micro, small, mid, large, giant) without numbers in the course material read. Proposal: start from Finviz bands, make them configurable.
- D5 Stop algorithm for "most important previous low". Proposal: low of the consolidation or last pivot low over N weeks.
- D6 Default entry mode. Proposal: `breakout`; `pullback`, `restart` as options.
- D7 Consolidation/breakout check (correction < 50% / < 38%, volumes): blocking or informational in v1? **Decided: informational only (shown in the trade plan).**
- D8 Intermediate "watchlist" state (fundamentals pass, technicals not yet). v1 keeps BUY / NO-BUY (plus `BUY*` from D3) until decided.

**Before publishing:**
- D9 License. **Decided: GPL-3.0.** Project name is decided: `ilovestock`. `finviz` is MIT, no constraint.
- D10 Finviz ToS: library authors warn use may violate them. **Decided (2026-10-20): Finviz is the main source for fundamentals and a required dependency; yfinance is the per-field fallback and the price source. Warning in README and CLI output.**
- D11 Web/graphical UI: not excluded, but chosen output is terminal + reports. Default: no GUI in v1. **Decided (2026-10-20): local web app (`ilovestock serve`, 127.0.0.1 only, PIN set in the terminal) on the same core as the CLI.**

## Risks
- yfinance is unofficial: blocking or format changes. Mitigation: disk cache, swappable provider, second price provider later.
- `finviz` scrapes HTML: site changes break data (v2.0 exists for that reason). Mitigation: pinned version, periodic contract test, clear error and `N/D` instead of wrong values.
- Finviz quotes delayed 15-20 min: method uses end-of-day data; recheck entry and stop on live price before trading.
- Yahoo financials: missing or non-official quarters. Mitigation: show `N/D`; verify with SEC EDGAR later.
- A BUY verdict can read as a recommendation: disclaimer in every output.
