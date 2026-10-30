"""Error log: warnings and errors from every module, as CSV next to the config.

Shared by CLI and web app; the web app's Log page reads it. Same Excel conventions as history.csv.
"""

import csv
import io
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ilovestock.config import CONFIG_PATH
from ilovestock.history import ENCODING, FORMULA

LOG_PATH = CONFIG_PATH.parent / "ilovestock-log.csv"
FIELDS = ["time", "level", "where", "ticker", "message", "details"]
MAX_BYTES = 1_000_000  # then the file becomes ilovestock-log.1.csv, replacing the older backup
_traceback = logging.Formatter()


def _cell(text: str) -> str:
    return "'" + text if text.startswith(FORMULA) else text


class CsvLog(RotatingFileHandler):
    """One CSV row per record; pass the ticker as `extra={"ticker": t}`."""

    terminator = ""  # the csv row ends the line

    def __init__(self, path: Path, max_bytes: int = MAX_BYTES):
        super().__init__(path, maxBytes=max_bytes, backupCount=1, encoding="utf-8", delay=True)
        self.namer = lambda name: name.removesuffix(".csv.1") + ".1.csv"  # Excel needs .csv last

    def _open(self):
        path = Path(self.baseFilename)
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        f = path.open("a", newline="", encoding=ENCODING if new else "utf-8")
        if new:
            csv.writer(f).writerow(FIELDS)
        return f

    def format(self, record: logging.LogRecord) -> str:
        details = _traceback.formatException(record.exc_info) if record.exc_info else ""
        buf = io.StringIO()
        csv.writer(buf).writerow(
            [
                datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                record.levelname,
                record.name,
                getattr(record, "ticker", ""),
                _cell(record.getMessage()),
                _cell(details),
            ]
        )
        return buf.getvalue()

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        # Errors are rare: closing after each one lets the file rotate while CLI and server log.
        try:
            self.close()  # flushes: a full disk fails here
        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        """A locked file (open in Excel) or a full disk loses the record, never the run; no stdlib
        dump on stderr over the progress bar."""


def setup(path: Path | None = None) -> None:
    """Root logger: WARNING and above from every module (ours, yfinance, uvicorn) to the CSV."""
    logging.basicConfig(level=logging.WARNING, handlers=[CsvLog(path or LOG_PATH)])


def read(path: Path | None = None) -> list[dict[str, str]]:
    """Rows of the current file (not the backup), newest first."""
    path = path or LOG_PATH
    if not path.exists():
        return []
    with path.open(newline="", encoding=ENCODING) as f:
        rows = [{k: raw.get(k) or "" for k in FIELDS} for raw in csv.DictReader(f)]
    for r in rows:
        for k in ("message", "details"):
            r[k] = r[k].removeprefix("'")
    return rows[::-1]
