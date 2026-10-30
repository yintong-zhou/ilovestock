---
type: handoff
date: 2026-10-30
status: merged (PR #8 on main, CI green)
seq: 6
prev: docs/handoff/2026-10-23-web-watchlist-dashboard.md
tags: [ilovestock, logging, progress, web, cli, desktop]
---

## Goal

A screen failed and the user could not tell why: skipped tickers lost their reason, and the desktop
app hid the server's output. This work adds two things:
- a WARNING+ error log the user can read, as a CSV that opens in Excel and on a Log page in the app;
- a progress bar with phase text during screens and analyses, in the terminal, the browser and the
  desktop app.

From now on, logs and documents inside ilovestock are written in English; chat stays in Italian.

## Where we are

- **Merged:** https://github.com/yintong-zhou/ilovestock/pull/8 (commit `8bf58ed`) was merged
  into `main` on 2026-10-30 as `74ca672`. This handoff was added to `main` afterwards as `f8f8d7e`.
- **Branches:** the remote branch `yintong-zhou/error-log-progress` is deleted. The local one is
  still there, with an extra commit `1712ee5` holding an earlier copy of this handoff, under a
  "Feat:" message.
- **Checks:**
  - CI on PR #8 and on `main` after the merge: green on Python 3.11 and 3.13, and web lint and
    build;
  - local, Python 3.12: 273 tests pass; ruff, eslint and `npm run build` are clean;
  - manual: Screener and Analysis bars, the Log page, the 375 px layout, the terminal Rich bar,
    and `serve` on a busy port (error on stderr and in the CSV).
- **Local venv:** reinstalled with `pip install -e .`; its `ilovestock.exe` calls `cli:main`.
- **Not done yet:** a real screen against live Finviz/Yahoo with the new log and bar. Live
  requests need the user's OK.
- **Deferred minors from the final review, not started:**
  - the `serve` tests in `tests/test_cli.py` leave a root `StreamHandler` bound to CliRunner's
    closed stderr, which causes hidden "Logging error" noise in the test output. Fix:
    `monkeypatch.setattr(logging.getLogger(), "handlers", [])` in those tests;
  - a mistyped Finviz URL raises `FinvizError("invalid URL…")` and is logged as ERROR, although
    it is a user input error. Fix: raise `ValueError` in `finviz.screener_tickers`, and add
    `except ValueError: _fail(str(e))` in `cli.analyze`;
  - `analyze` in the terminal prints no log hint when a source fails but the ticker still gets a
    verdict: only `Fundamentals.note` is set, so `r.error` is empty.

## What we tried that did NOT work

- **Setting up logging in a Typer callback (`@app.callback`).** CliRunner tests would write to the
  real log, and `basicConfig(force=True)` would remove pytest's caplog handler. Moved to
  `cli.main`, the console entry point, instead.
- **Heredocs with backslash escapes through the Bash tool.** `b"\\xef\\xbb\\xbf"` ended up as
  literal `ï»¿` in the file, and one heredoc failed with "unexpected EOF". Use the Write or Edit
  tools, or a script file in the scratchpad, for edits that contain backslashes.
- **`| head` on Rich output in Git Bash.** It raises `OSError: [Errno 22]` (a broken pipe on the
  legacy Windows console). This is not a bug in our code: redirect to a file instead.
- **Fixing the Log page table width:**
  - `break-words` on the message cell did not stop long paths from widening the table;
  - `overflow-x-auto` on the `<pre>` did nothing inside a table cell.
  What worked: `wrap-anywhere`, `whitespace-pre-wrap` on the `<pre>`, and `min-w-[600px]`.
- **Navigating the browser pane to the same URL with a different `#hash`.** It does not reload the
  page, so a rebuilt bundle is not picked up. Add a query string (`?reload=N#log`) to force a
  reload.

## Problems we hit and how we fixed them

- **Log file locked by Excel.**
  - Symptom: a 35–60 line "--- Logging error ---" dump on stderr for every record, over the
    progress bar.
  - Cause: stdlib `handleError` with `raiseExceptions=True`.
  - Fix: `CsvLog.handleError` does nothing; the record is lost and the run goes on.
- **Write failing after the file opened (disk full).**
  - Symptom: `OSError` raised out of `logger.warning`, which aborts the screen.
  - Cause: our `close()` after each record runs outside the stdlib's try.
  - Fix: wrap `self.close()` in try/except and route the error to `handleError`.
- **uvicorn errors missing from the log.**
  - Cause: uvicorn's own log config gives its loggers `propagate=False`.
  - Fix: `uvicorn.run(..., log_config=None)`, plus a stderr handler on the root logger in `serve`.
- **Desktop "server stopped" box.**
  - Symptom: it would hold every warning since launch.
  - Fix: `desktop/main.js` keeps the last 4000 characters of the output.

## Decisions made

- **CSV format:** comma separator, UTF-8 BOM and formula guard, the same as `history.csv`. A `;`
  separator was rejected: the user is fine with commas.
- **Rotation:** at 1 MB the file becomes `ilovestock-log.1.csv`, one backup. Keeping the `.csv.1`
  name was rejected: Excel needs `.csv` last.
- **One record per open/close:** the file is closed after each record so it can rotate while the
  CLI and the server both log. Keeping it open was rejected: Windows cannot rename an open file.
- **Web progress:** the page polls `GET /api/progress` about once a second. Streaming the POST
  response or SSE was rejected as more code for the same result.
- **Progress slots:** one slot per kind (`screen`, `analyze`), cleared at the end only if it still
  holds the run's own last step. Per-request ids were rejected as unneeded for one local user; two
  tabs share the slot.
- **Analysis page state:** the busy state stays local to the page, and `JobProgress` polls once on
  mount, so the bar comes back after leaving and returning. Moving the analysis state into `App`
  was rejected.
- **Where logs go:**
  - `serve` writes to the CSV and to stderr;
  - `analyze` and `screen` write to the CSV only and print the log path at the end. Showing
    warnings in the terminal was rejected: they would break the Rich bar.
- **User input errors** (config, tickers) are shown, not logged. Finviz errors, including config
  limits like "more than 100 candidates", are logged.
- **Not built:** filters, a "clear log" button, reading the `.1` backup, INFO logging, frontend
  logging.
- **Log page "Where" column:** shows the logger name without `ilovestock.`. The CSV keeps the full
  name.
- **Commits:** no commit per task, one commit at the end, because the user commits on request.

## Files touched

- `src/ilovestock/errorlog.py` (new): `CsvLog` handler, `setup()`, `read()`, `LOG_PATH`, `FIELDS`.
- `src/ilovestock/cli.py`:
  - `main()` entry point;
  - `_fail(msg, logged=)`;
  - `_progress()` Rich bar;
  - the log path printed after runs;
  - `serve` gets a stderr handler and `log_config=None`.
- `src/ilovestock/__main__.py` and `pyproject.toml`: the script now points to `cli:main`.
- `src/ilovestock/analysis.py`:
  - the `Progress` type, `(text, done, total)`;
  - progress calls;
  - log calls for data and analysis errors.
- `src/ilovestock/screener.py`:
  - progress during the Finviz read, the per-candidate check and ranking;
  - the reason for each skipped ticker is logged.
- `src/ilovestock/providers/finviz.py`: logs Yahoo and Finviz fetch failures with the ticker.
- `src/ilovestock/api/app.py`:
  - `ProgressOut`, `Running`, `LogRow`, `LogOut`;
  - `report()` slot handling;
  - `GET /api/progress`, `/api/log`, `/api/log/csv`;
  - the `log_path` parameter;
  - failures are logged.
- `desktop/main.js`: keeps only the tail of the server output.
- `web/src/components.tsx`: the `JobProgress` component.
- `web/src/pages/Log.tsx` (new), `Sidebar.tsx`, `App.tsx`: the Log page and its route.
- `web/src/pages/Screener.tsx`: the bar and the "Details in Log" link.
- `web/src/pages/Analysis.tsx`: the bar replaces the busy message.
- `web/src/api.ts` and `web/src/types.ts`: the new routes and types.
- `tests/test_errorlog.py` (new), plus `tests/test_api.py`, `test_cli.py`, `test_rules.py`,
  `test_screener.py` and `test_providers.py`: tests for the log calls, progress and routes.
- `README.md` and `CLAUDE.md`: the error log, the Log page and progress.
- `docs/superpowers/specs/2026-10-30-error-log-and-progress-design.md` and
  `docs/superpowers/plans/2026-10-30-error-log-and-progress.md`.

## Where we want to go

1. Run a real `ilovestock screen` (ask the user first: it hits Finviz and Yahoo). Then open the Log
   page or `~/.config/ilovestock/ilovestock-log.csv` to see why tickers were skipped; this was the
   reason for the whole feature.
2. Fix the three deferred minors listed above, in a small follow-up PR, on a new branch from
   `main`.
3. Delete the local branch `yintong-zhou/error-log-progress` with `git branch -D`. Plain `-d`
   refuses because `1712ee5` is on `main` under another hash (`f8f8d7e`). Ask the user first.
4. Run `pip install -e .` again in any other editable install used by the desktop dev mode
   (`ILOVESTOCK_BIN`); the repo's `.venv` is already done.

## Know before touching anything

- **Entry point:** it is now `ilovestock.cli:main`. An editable install made before this change
  calls `app` directly and writes no log, so the Log page always says "No problems logged." Run
  `pip install -e .` again.
- **Tests never write the real log:**
  - `errorlog.setup()` runs only in `cli.main`;
  - the `offline` fixture in `test_cli.py` patches `errorlog.LOG_PATH`;
  - `create_app(log_path=...)` takes a temp path.
- **Log volume:** each skipped screen ticker usually produces three log rows: the Yahoo error, the
  Finviz error (each with its traceback) and the screener's "Skipped" line. This is expected.
- **Manual web check without network:**
  - run `create_app` with temp paths;
  - patch `yahoo.yf.Ticker = conftest.FakeTicker` and
    `finviz.finviz.get_stock = conftest.fake_get_stock` (put `tests` on `sys.path`);
  - replace `finviz.screener_rows` with a slow generator and slow the provider with `time.sleep`;
  - call `errorlog.setup(tmp/"log.csv")` and `PinStore(tmp/"pin.json").set("1234")`, then run
    `uvicorn.run(app, ..., log_config=None)`.
  The scratch scripts were not kept.
- **Python versions:** only 3.12 is installed locally (`py -0`). CI runs 3.11 and 3.13, and both
  passed on this work.
- **`npm run build`** writes into `src/ilovestock/static/`, which is git-ignored.
