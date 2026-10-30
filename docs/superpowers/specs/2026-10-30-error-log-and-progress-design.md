# Error log and progress: design

## Why

A screen failed and the user could not tell what went wrong. Today:

- `screener.screen` puts a failing ticker in `errors` and drops the reason;
  `FinvizProvider.fundamentals` turns exceptions into a `note` string; the API turns failures into
  HTTP errors. Nothing is written anywhere.
- The desktop app hides the server's output (it shows it only when the server stops).
- While a screen or an analysis runs (minutes), the web page says only "Searching…" /
  "Analyzing…" and the terminal only the current ticker. The user cannot tell what the app is
  doing or how much is left.

## Goals

1. **Error log.** Every warning, error and critical event is written to one CSV file, from the CLI
   and from the web/desktop server. Nothing below WARNING.
2. **Log page.** A "Log" entry in the web sidebar (so also in the desktop app) to read the log
   without opening the file.
3. **Progress.** During a screen and an analysis: a progress bar with a percentage and a line of
   text saying which phase is running, in the browser, the desktop app (same page) and the
   terminal.

Non-goals: INFO/DEBUG logging, log filters, a "clear log" button, logging from the frontend,
progress for other operations (PDF, history). Added only if asked.

## Error log

- **File:** `ilovestock-log.csv` next to the config (`CONFIG_PATH.parent`, like `history.csv`).
- **Columns:** `time` (ISO, seconds), `level` (WARNING / ERROR / CRITICAL), `where` (logger name,
  e.g. `ilovestock.screener`, `yfinance`, `uvicorn.error`), `ticker` (empty when none), `message`,
  `details` (traceback, empty when none).
- **Excel:** same conventions as `history.csv`: comma separator, UTF-8 with BOM on a new file,
  a leading `'` on text cells that Excel would run as a formula (`history.FORMULA`). The user is
  fine with the comma separator.
- **Size:** at about 1 MB the file becomes `ilovestock-log.1.csv` (one backup, the older one is
  dropped) and a new file starts with the header.
- **Language:** log messages in English (all ilovestock text is English).
- **Wiring:** stdlib `logging`. The root logger gets one CSV handler at level WARNING, so
  third-party warnings (yfinance "possibly delisted", uvicorn "Exception in ASGI application")
  land in the same file. Set up once in the console entry point (`ilovestock` script and
  `python -m ilovestock`), so tests that call `app` or `create_app` never touch the real file.
  `serve` lets uvicorn's loggers propagate to the root (no uvicorn log config of its own).
- **stderr:** `serve` also keeps a stderr handler (WARNING): its terminal shows errors as before,
  and the desktop app's "server stopped" box still shows the reason (e.g. a port uvicorn cannot
  bind). `analyze` and `screen` write the CSV only, so warnings never break the progress bar;
  they print the log path at the end instead.
- **What our code logs** (with the ticker when there is one):
  - `FinvizProvider.fundamentals`: a Yahoo or Finviz fetch error (WARNING, traceback).
  - `screener.screen`: a skipped ticker, with the reason: the fundamentals note, or the exception
    with its traceback (WARNING).
  - `analysis.analyze`: data error (WARNING) and analysis error (ERROR), with traceback.
  - CLI and API boundaries: a screen or an analysis that fails as a whole (Finviz screener error,
    benchmark unavailable, Finviz URL import), with traceback (ERROR). User input errors
    (bad ticker, bad config value) are shown, not logged.
- **Terminal:** when a run had data errors or failed, the CLI prints where the log is.

## Log page

- Sidebar entry "Log" (route `#log`), before Settings.
- Shows the log file path, then a table, newest first: time, level (colored), where, ticker,
  message. Clicking a row shows `details`. Empty log: "No problems logged."
- "Download CSV" button: the file as it is on disk, to open in Excel.
- The Screener's "Skipped for data errors: X, Y" message links to the Log page.
- API: `GET /api/log` → `{path, rows}`; `GET /api/log/csv` → the file. Both behind the PIN
  session. Only the current file is read, not the `.1` backup.

## Progress

- **Core:** the existing `progress` callbacks of `screener.screen` and `analysis.analyze_many`
  become `progress(text, done, total)`. `total == 0` means "not known yet" (indeterminate bar).
  The core decides the phases and the text; interfaces only display them.
- **Screen phases:**
  1. Reading the Finviz screener: the total is unknown until the first nano cap, so the bar is
     indeterminate; text like "Reading the Finviz screener: 45 rows, 32 candidates".
  2. Checking each candidate: "Checking fundamentals: ABC (12 of 87)", percentage from the count.
  3. Ranking (instant).
- **Analysis phases:**
  1. Importing tickers from a Finviz URL, when given (API/CLI layer, indeterminate).
  2. Loading the S&P 500 benchmark.
  3. "Analyzing HZO (3 of 10)", percentage from the count.
- **Terminal:** a Rich progress bar (spinner, text, bar, percentage, elapsed time) in place of the
  current status line; it disappears when the run ends.
- **Web/desktop:** the long POST requests stay as they are. The server keeps the latest progress
  of the running screen and analysis in memory; `GET /api/progress` returns
  `{screen, analyze}` (each `{text, done, total}` or null). While a run is busy the page polls it
  about once a second and shows the bar and the text. The screen keeps running when the user
  leaves the Screener page (as today), and the bar is there again on return.
- **Analysis page on return:** the analysis's busy state stays local to the page (not moved to
  `App`). The bar polls while the page is busy, and on mount it polls once: if the server reports
  an analysis running, the bar shows it until it ends. The button stays as today.
- **Watchlist refreshes** (single-ticker `POST /api/analyze`) also write the analyze slot. A run
  clears the slot at the end only if the slot still holds its own progress, so a short refresh
  never wipes a long analysis for more than one step.

## Builder's calls

- Exact wording of progress texts and log messages.
- Bar styling (brand colors from `brand-guidelines.md`), icon for the Log entry.
- One progress slot per kind on the server: two analyses started at once from two tabs share the
  slot (acceptable for a single-user local app).
