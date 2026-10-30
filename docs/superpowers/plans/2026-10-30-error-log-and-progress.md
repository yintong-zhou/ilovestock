# Error Log and Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A CSV error log (WARNING and above) readable from a new Log page, and a progress bar with
phase text for screens and analyses in the terminal, browser and desktop app.

**Architecture:** stdlib `logging` with one CSV handler on the root logger, set up only in the
console entry point. The core's existing `progress` callbacks become `(text, done, total)`; the CLI
draws them with Rich, the API keeps the latest one per run kind in memory for the page to poll.

**Tech Stack:** Python 3.11+ stdlib `logging`/`csv`, Rich (already installed via Typer), FastAPI,
React + Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-30-error-log-and-progress-design.md`

## Global Constraints

- All log messages, progress texts and page text in English.
- Log file `CONFIG_PATH.parent / "ilovestock-log.csv"`, backup `ilovestock-log.1.csv`, rotation at
  1,000,000 bytes, one backup.
- CSV columns, in order: `time, level, where, ticker, message, details`.
- Same Excel conventions as `history.py`: comma, `history.ENCODING` (BOM) on a new file,
  `history.FORMULA` guard with a leading `'` on text cells, stripped once on read.
- Only WARNING and above reach the file. User input errors are shown, never logged.
- Tests never write the real log: `errorlog.setup()` runs only in `cli.main`.
- No new dependencies. Commits only with the user's OK.

## Review Focus

1. The log file is locked (open in Excel on Windows) or unwritable: the run goes on, nothing
   raises. Test in Task 1.
2. A screen or analysis that fails mid-run leaves no stale progress: the slot is null afterwards.
   Test in Task 4.
3. No log file yet: `/api/log` returns no rows, the page says "No problems logged.", the CSV
   download reports 404. Test in Task 4.
4. Messages with commas, quotes, newlines or a leading `=`: written and read back unchanged.
   Test in Task 1.
5. A short Watchlist refresh finishing during a long analysis does not clear the long run's
   progress. Test in Task 4.

---

### Task 1: CSV error log module and entry point

**Files:**
- Create: `src/ilovestock/errorlog.py`
- Modify: `src/ilovestock/cli.py` (add `main`), `src/ilovestock/__main__.py`, `pyproject.toml`
  (`ilovestock = "ilovestock.cli:main"`)
- Test: `tests/test_errorlog.py`

**Interfaces:**
- Produces: `errorlog.LOG_PATH: Path`, `errorlog.FIELDS: list[str]`, `errorlog.MAX_BYTES = 1_000_000`,
  `class CsvLog(RotatingFileHandler)` with `__init__(self, path: Path, max_bytes: int = MAX_BYTES)`,
  `setup(path: Path | None = None) -> None`, `read(path: Path | None = None) -> list[dict[str, str]]`
  (newest first), `cli.main() -> None`. Callers pass the ticker as `extra={"ticker": t}`.

- [ ] **Step 1: Write the failing tests** (each builds a `CsvLog(tmp_path / "x-log.csv")` on a
  dedicated logger with `propagate = False`, removed at the end)
  - `test_writes_warning_and_above_only`: logger at WARNING; `info` then `warning("w")`,
    `error("e")`, `critical("c")` → `[r["level"] for r in read(p)] == ["CRITICAL", "ERROR", "WARNING"]`.
  - `test_row_fields`: `warning("Skipped: %s", "x", extra={"ticker": "ABC"})` inside an `except`
    with `exc_info=True` → row has `where == logger name`, `ticker == "ABC"`,
    `message == "Skipped: x"`, `"Traceback" in details`, `time` parses with
    `datetime.fromisoformat`.
  - `test_excel_format`: file starts with `b"\xef\xbb\xbf"`; first line is `",".join(FIELDS)`;
    a message `'=1+1, "q"\nline'` reads back exactly; the raw file contains `"'=1+1`.
  - `test_rotation_names_backup_csv`: `CsvLog(p, max_bytes=300)`, 10 warnings → files are
    `x-log.csv` and `x-log.1.csv`, both start with the BOM and the header.
  - `test_unwritable_log_does_not_raise`: path is an existing directory; `warning("w")` returns
    normally (set `logging.raiseExceptions = False` via monkeypatch to keep stderr quiet).
  - `test_read_missing_file`: `read(tmp_path / "none.csv") == []`.

- [ ] **Step 2: Run** `.venv/Scripts/pytest.exe tests/test_errorlog.py -v` → FAIL (no module).

- [ ] **Step 3: Implement `errorlog.py`.** `CsvLog`: `delay=True`, `backupCount=1`,
  `terminator = ""`, `namer` turning `…csv.1` into `….1.csv`, `_open` opens with `newline=""` and
  writes BOM + header on a new file (like `history.append`), `format` returns one csv row
  (time `datetime.fromtimestamp(record.created).isoformat(timespec="seconds")`, `levelname`,
  `name`, `getattr(record, "ticker", "")`, `getMessage()`, `formatException(exc_info)` or `""`,
  text cells guarded with `history.FORMULA`), `emit` closes the stream after each record (errors
  are rare; keeps rotation possible while the CLI and the server both log). `setup`:
  `logging.basicConfig(level=logging.WARNING, handlers=[CsvLog(path or LOG_PATH)])`.
  `read`: `csv.DictReader` with `history.ENCODING`, strip one leading `'`, reversed.
  `cli.main`: `errorlog.setup()` then `app()`; `__main__` calls `main()`.

- [ ] **Step 4: Run** the tests → PASS; `.venv/Scripts/pytest.exe -m "not slow"` → all pass.

### Task 2: Log what goes wrong

**Files:**
- Modify: `src/ilovestock/providers/finviz.py:121-144`, `src/ilovestock/screener.py:124-137`,
  `src/ilovestock/analysis.py:35-52`, `src/ilovestock/cli.py` (`_fail`, `analyze`, `screen`)
- Test: `tests/test_screener.py`, `tests/test_rules.py`, `tests/test_providers.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `errorlog.LOG_PATH` (Task 1).
- Produces: `cli._fail(msg: str, logged: bool = False)`: with `logged`, logs `msg` at ERROR with
  the current exception and prints `Details: <LOG_PATH>`.

Each module gets `logger = logging.getLogger(__name__)`.

- [ ] **Step 1: Write the failing tests** (pytest `caplog`)
  - screener: extend `test_screen_reads_fundamentals_first_and_one_year_of_prices` → a WARNING
    record with `ticker == "B"` and `"Finviz error: 429" in message`; new
    `test_screen_logs_the_exception`: provider raises `ValueError("boom")` for `C` → WARNING with
    `ticker == "C"` and `exc_info` set.
  - analysis (`tests/test_rules.py`, next to the `Broken` provider tests): data error → WARNING,
    analysis error → ERROR, both with `ticker == "HZO"` and `exc_info`.
  - finviz provider: `get_stock` raising → WARNING `"Finviz quote page failed"` with the ticker.
  - CLI: a `screen` run whose `screener.screen` raises `FinvizError` → exit 1, output contains
    `str(errorlog.LOG_PATH)` (patch `LOG_PATH` to `tmp_path`), an ERROR record is captured.

- [ ] **Step 2: Run** them → FAIL.

- [ ] **Step 3: Implement.**
  - Provider: in the two `except` blocks, `logger.warning("Yahoo fundamentals failed" /
    "Finviz quote page failed", exc_info=True, extra={"ticker": ticker})`.
  - Screener: note case `logger.warning("Skipped: %s", fund.note, extra=…)`; exception case
    `logger.warning("Skipped: data error", exc_info=True, extra=…)`.
  - Analysis: `"Data error"` WARNING, `"Analysis error"` ERROR, both `exc_info=True`.
  - CLI: `_fail(..., logged=True)` for the Finviz URL import, the benchmark and both screen
    failures; after the report, `analyze` prints `Data errors: details in <LOG_PATH>` when a result
    has `error`; `screen` appends `. Details: <LOG_PATH>` to the "Skipped for data errors" line.

- [ ] **Step 4: Run** the default suite → all pass.

### Task 3: Progress in the core and the terminal

**Files:**
- Modify: `src/ilovestock/analysis.py`, `src/ilovestock/screener.py`, `src/ilovestock/cli.py`
- Test: `tests/test_screener.py`, `tests/test_rules.py`

**Interfaces:**
- Produces: `analysis.Progress = Callable[[str, int, int], None]` (`text, done, total`,
  `total == 0` = not known yet); `screener.candidates(cfg, include_large=False, progress=None)`;
  `screen(..., progress: Progress | None)` and `analyze_many(..., progress: Progress | None)`
  keep their parameter positions.

- [ ] **Step 1: Write the failing tests**
  - `test_screen_reports_progress`: two candidates `A`, `B`; collected calls include
    `("Reading the Finviz screener: 1 rows, 1 candidates", 0, 0)`,
    `("Checking fundamentals: A (1 of 2)", 0, 2)`, `("Checking fundamentals: B (2 of 2)", 1, 2)`,
    and end with `("Ranking by quality", 2, 2)`.
  - `test_analyze_many_reports_progress`: `["HZO"]` with fake data → calls are
    `[("Loading the S&P 500 benchmark", 0, 1), ("Analyzing HZO (1 of 1)", 0, 1)]`.

- [ ] **Step 2: Run** them → FAIL.

- [ ] **Step 3: Implement** the calls with exactly those texts (Finviz text after each row read).
  CLI: replace both `console.status` blocks with a Rich `Progress` (`SpinnerColumn`,
  `TextColumn`, `BarColumn`, `TaskProgressColumn`, `TimeElapsedColumn`, `transient=True`) through
  a small context manager in `cli.py` yielding the callback;
  `update(task, description=escape(text), completed=done, total=total or None)` (None = pulsing
  bar). `analyze --finviz-url` shows `"Importing tickers from Finviz"` while it imports.

- [ ] **Step 4: Run** the default suite → all pass; run
  `PYTHONIOENCODING=utf-8 USERPROFILE=<tmp> .venv/Scripts/ilovestock.exe screen --help` to check the
  CLI still starts (no live run without the user's OK).

### Task 4: API: progress and log routes, serve logging

**Files:**
- Modify: `src/ilovestock/api/app.py`, `src/ilovestock/cli.py` (`serve`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `analysis.Progress` (Task 3), `errorlog.read`, `errorlog.LOG_PATH` (Task 1).
- Produces (mirrored in `web/src/types.ts` by Task 5):
  - `GET /api/progress` → `Running {screen: ProgressOut | null, analyze: ProgressOut | null}`,
    `ProgressOut {text: str, done: int, total: int}`.
  - `GET /api/log` → `LogOut {path: str, rows: list[LogRow]}`, `LogRow` = the six `FIELDS`, str.
  - `GET /api/log/csv` → the file (`text/csv`), 404 `"No problems logged"` when missing.
  - `create_app(..., log_path: Path | None = None)`.

- [ ] **Step 1: Write the failing tests**
  - `test_progress_idle_and_after_failure`: `/api/progress` == `{"screen": None, "analyze": None}`;
    after a `/api/screen` that fails (patch `screener.candidates` to raise `FinvizError`) still null.
  - `test_progress_during_screen`: a provider whose `fundamentals` reads
    `app.state.running["screen"]` (expose the dict on `app.state`) sees
    `text.startswith("Checking fundamentals")`.
  - `test_short_run_keeps_long_runs_progress`: set the analyze slot to a foreign `ProgressOut`,
    run `/api/analyze` for one ticker whose slot is overwritten back to the foreign value by the
    provider mid-run → after the request the slot still holds the foreign value.
  - `test_log_routes`: no file → `{"path": …, "rows": []}` and csv 404; after writing one row with
    `CsvLog(log_path)` → one row back and the csv body starts with the BOM; both 401 when locked.

- [ ] **Step 2: Run** them → FAIL.

- [ ] **Step 3: Implement.** `running = {"screen": None, "analyze": None}` on `app.state`; each run
  sets `running[kind] = ProgressOut(...)` from the callback and, in `finally`, clears it only if it
  still holds the last value this run wrote. `/api/analyze` reports
  `"Importing tickers from Finviz"` (0, 0) before the import. Log routes per the interface
  (`FileResponse`). Log `FinvizError` and 502 failures with `logger.exception`; config and ticker
  errors are not logged. `serve`: add a stderr `StreamHandler` (`"%(levelname)s %(name)s: %(message)s"`)
  to the root logger and pass `log_config=None` to `uvicorn.run`.

- [ ] **Step 4: Run** the default suite → all pass.

### Task 5: Web: progress bar and Log page

**Files:**
- Create: `web/src/pages/Log.tsx`
- Modify: `web/src/types.ts`, `web/src/api.ts`, `web/src/components.tsx`, `web/src/Sidebar.tsx`,
  `web/src/App.tsx`, `web/src/pages/Screener.tsx`, `web/src/pages/Analysis.tsx`,
  `README.md` and `CLAUDE.md` (log file, Log page, `/api/progress`)

**Interfaces:**
- Consumes: the Task 4 routes and models.
- Produces: `api.progress()`, `api.log()`, `api.logCsv(): Promise<Blob>`;
  `JobProgress({ job: 'screen' | 'analyze', busy: boolean })` in `components.tsx`;
  page `'log'` in `Sidebar`'s `Page` and `App`'s `PAGES`.

- [ ] **Step 1: `JobProgress`.** Polls `api.progress()` every 1000 ms while `busy` or while the last
  answer for `job` was non-null; one poll on mount. Renders nothing when null; otherwise the text
  and a bar (`role="progressbar"`, `aria-valuenow` = percent) with `Math.round(done / total * 100)%`,
  or a pulsing full-width bar when `total === 0`. Brand colors only.
- [ ] **Step 2: Wire it.** Screener: `<JobProgress job="screen" busy={busy} />` under the busy
  message; "Skipped for data errors: …" gets a `#log` link "Details in Log". Analysis:
  `<JobProgress job="analyze" busy={busy} />` in place of the busy message.
- [ ] **Step 3: Log page.** Header "Log", text "Warnings and errors, newest first. File: {path}",
  "Download CSV" button (`download(blob, 'ilovestock-log.csv')`), table Time / Level / Where /
  Ticker / Message with rows that expand `details` in a `<pre>` (same pattern as Screener's
  `Note`), "No problems logged." when empty. Level colors: WARNING `text-nd`, ERROR and CRITICAL
  `text-fail`. Sidebar entry before Settings.
- [ ] **Step 4: Verify.** `cd web && npm run lint && npm run build` → no errors. Start a server
  with `create_app(...)` on temp paths, a fake slow provider and `PinStore(path).set("1234")`;
  in the browser pane check the Screener bar moves, the Log page lists a row and expands it, and
  the layout holds at 375 px width.

### Task 6: Full check

- [ ] `.venv/Scripts/ruff.exe check .` and `.venv/Scripts/ruff.exe format --check .` → clean.
- [ ] `.venv/Scripts/pytest.exe -m "not slow"` → all pass.
- [ ] `cd web && npm run lint && npm run build` → clean.
