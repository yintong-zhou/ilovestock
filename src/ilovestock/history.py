"""Analysis history: one CSV row per ticker per analysis, shared by CLI and web app.

Analyses are appended; the web app edits and deletes rows. Criteria and reasons are JSON in one
column each: criterion names vary (e.g. growth basis), so fixed columns would break the file.
"""

import csv
import dataclasses
import json
import math
import os
import secrets
import threading
from datetime import datetime
from pathlib import Path

from ilovestock.config import CONFIG_PATH
from ilovestock.models import TickerAnalysis, Verdict

HISTORY_PATH = CONFIG_PATH.parent / "history.csv"
FIELDS = [
    "id", "analyzed_at", "data_date", "ticker", "verdict", "price", "entry", "stop", "target",
    "shares", "reasons", "criteria", "note", "edited_at",
]  # fmt: skip
NUMBERS = ("price", "entry", "stop", "target")
EDITABLE = {"verdict", *NUMBERS, "shares", "note"}
MAX_NOTE = 1000
# Excel reads UTF-8 only with a BOM; utf-8-sig also reads files without one.
ENCODING = "utf-8-sig"
# ponytail: one lock per process; a CLI run writing during a web edit could interleave.
_lock = threading.Lock()


class HistoryError(ValueError):
    pass


def _row(r: TickerAnalysis, analyzed_at: datetime) -> dict:
    p = r.plan
    criteria = [*r.fundamental, *([r.earnings] if r.earnings else []), *r.technical]
    return {
        "id": secrets.token_hex(6),
        "analyzed_at": analyzed_at.isoformat(timespec="seconds"),
        "data_date": r.data_date.isoformat() if r.data_date else "",
        "ticker": r.ticker,
        "verdict": str(r.verdict),
        "price": r.price,
        "entry": p.entry if p else None,
        "stop": p.stop if p else None,
        "target": p.target if p else None,
        "shares": p.shares if p else None,
        "reasons": r.reasons,
        "criteria": [dataclasses.asdict(c) for c in criteria],
        "note": "",
        "edited_at": None,
    }


def _to_csv(row: dict) -> dict:
    out = {k: ("" if row[k] is None else row[k]) for k in FIELDS}
    out["reasons"] = json.dumps(row["reasons"])
    out["criteria"] = json.dumps(row["criteria"])
    return out


def _from_csv(raw: dict) -> dict:
    row = {k: (raw.get(k) or None) for k in FIELDS}
    for k in NUMBERS:
        row[k] = float(row[k]) if row[k] else None
    row["shares"] = int(row["shares"]) if row["shares"] else None
    row["reasons"] = json.loads(raw["reasons"] or "[]")
    row["criteria"] = json.loads(raw["criteria"] or "[]")
    row["note"] = raw.get("note") or ""
    return row


def append(results: list[TickerAnalysis], analyzed_at: datetime, path: Path | None = None) -> int:
    """Add one row per analyzed ticker. Data errors are skipped: nothing to compare."""
    path = path or HISTORY_PATH
    rows = [_to_csv(_row(r, analyzed_at)) for r in results if not r.error]
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="", encoding=ENCODING if new else "utf-8") as f:
            w = csv.DictWriter(f, FIELDS)
            if new:
                w.writeheader()
            w.writerows(rows)
    return len(rows)


def read(path: Path | None = None) -> list[dict]:
    """All rows, oldest first."""
    path = path or HISTORY_PATH
    if not path.exists():
        return []
    with path.open(newline="", encoding=ENCODING) as f:
        return [_from_csv(raw) for raw in csv.DictReader(f)]


def _write(rows: list[dict], path: Path) -> None:
    """Rewrite through a temp file: a crash mid-write never leaves a half file."""
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding=ENCODING) as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(_to_csv(r) for r in rows)
    os.replace(tmp, path)


def _check(changes: dict) -> dict:
    if bad := set(changes) - EDITABLE:
        raise HistoryError(f"not editable: {', '.join(sorted(bad))}")
    clean = {}
    for k, v in changes.items():
        if k == "verdict":
            if v not in set(Verdict):
                raise HistoryError(f"verdict must be one of {', '.join(Verdict)}")
        elif k == "note":
            if not isinstance(v, str) or len(v) > MAX_NOTE:
                raise HistoryError(f"note: text up to {MAX_NOTE} characters")
        elif k == "shares":
            if v is not None and (type(v) is not int or v < 0):
                raise HistoryError("shares: whole number >= 0")
        elif v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0):
            raise HistoryError(f"{k}: number >= 0")
        clean[k] = float(v) if k in NUMBERS and v is not None else v
    return clean


def update(row_id: str, changes: dict, path: Path | None = None) -> dict:
    """Edit one row. Changing analysis data marks it edited; the note is the user's own."""
    path = path or HISTORY_PATH
    clean = _check(changes)
    with _lock:
        rows = read(path)
        row = next((r for r in rows if r["id"] == row_id), None)
        if row is None:
            raise KeyError(row_id)
        if any(row[k] != v for k, v in clean.items() if k != "note"):
            row["edited_at"] = datetime.now().isoformat(timespec="seconds")
        row.update(clean)
        _write(rows, path)
    return row


def delete(path: Path | None = None, ids: list[str] | None = None, ticker: str | None = None):
    """Delete rows by id, or every row of a ticker."""
    path = path or HISTORY_PATH
    with _lock:
        rows = read(path)
        if ids and not set(ids) <= {r["id"] for r in rows}:
            raise KeyError(ids)
        keep = [r for r in rows if r["id"] not in (ids or []) and r["ticker"] != ticker]
        _write(keep, path)
    return len(rows) - len(keep)
