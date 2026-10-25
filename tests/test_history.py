"""Analysis history CSV: append from CLI/web, read typed rows, edit and delete from the web."""

import csv
import os
import time
from datetime import date, datetime

import pytest

from ilovestock import history
from ilovestock.models import CriterionResult, Status, TickerAnalysis, TradePlan, Verdict

NOW = datetime(2026, 10, 20, 15, 4)
AAA = TickerAnalysis(
    "AAA",
    Verdict.NO_BUY,
    ["ROE: FAIL"],
    fundamental=[CriterionResult("ROE", Status.FAIL, 5.0, "> 15%", "source: Finviz")],
    technical=[CriterionResult("SMA 200d", Status.PASS, 10.0, "> 9.00")],
    earnings=CriterionResult("Next earnings", Status.ND, None, "> 10 days"),
    plan=TradePlan(entry=10, stop=9, target=13, shares=20),
    data_date=date(2026, 10, 19),
    price=10.0,
)
ERR = TickerAnalysis("BBB", Verdict.NO_BUY, ["Data error: boom"], error="boom")


@pytest.fixture
def path(tmp_path):
    return tmp_path / "history.csv"


def test_append_and_read(path):
    history.append([AAA, ERR], NOW, path)
    history.append([AAA], NOW, path)
    rows = history.read(path)
    assert len(rows) == 2  # data errors have nothing to compare: not saved
    r = rows[0]
    assert (r["ticker"], r["verdict"], r["data_date"]) == ("AAA", "NO-BUY", "2026-10-19")
    assert (r["price"], r["entry"], r["stop"], r["target"], r["shares"]) == (10, 10, 9, 13, 20)
    assert r["analyzed_at"] == "2026-10-20T15:04:00" and r["reasons"] == ["ROE: FAIL"]
    assert [c["name"] for c in r["criteria"]] == ["ROE", "Next earnings", "SMA 200d"]
    earnings = {"name": "Next earnings", "status": "N/D", "value": None, "threshold": "> 10 days"}
    assert r["criteria"][1] == {**earnings, "note": ""}
    assert r["note"] == "" and r["edited_at"] is None
    assert rows[0]["id"] != rows[1]["id"]


def test_no_file_is_empty_history(path):
    assert history.read(path) == []


def test_edit_data_marks_row_edited_note_does_not(path):
    history.append([AAA], NOW, path)
    rid = history.read(path)[0]["id"]
    r = history.update(rid, {"note": "bought at 10.10, è ok"}, path)
    assert r["note"] == "bought at 10.10, è ok" and r["edited_at"] is None
    r = history.update(rid, {"verdict": "BUY", "entry": 10.5, "shares": 18}, path)
    assert (r["verdict"], r["entry"], r["shares"]) == ("BUY", 10.5, 18) and r["edited_at"]
    assert history.read(path)[0] == r  # persisted


@pytest.mark.parametrize(
    "changes",
    [
        {"verdict": "MAYBE"},
        {"price": "abc"},
        {"price": float("nan")},
        {"shares": -1},
        {"shares": 1.5},
        {"criteria": []},  # read-only: comes from that day's data
        {"ticker": "ZZZ"},
        {"note": "x" * 1001},
    ],
)
def test_edit_rejects_invalid(path, changes):
    history.append([AAA], NOW, path)
    rid = history.read(path)[0]["id"]
    with pytest.raises(history.HistoryError):
        history.update(rid, changes, path)


def test_note_never_runs_as_a_spreadsheet_formula(path):
    history.append([AAA], NOW, path)
    rid = history.read(path)[0]["id"]
    for note in ('=HYPERLINK("http://x")', "-1+2", "@SUM(A1)", "'quoted", "plain"):
        history.update(rid, {"note": note}, path)
        with path.open(newline="", encoding=history.ENCODING) as f:
            cell = next(csv.DictReader(f))["note"]
        assert cell == (note if note == "plain" else "'" + note)  # Excel shows it as text
        assert history.read(path)[0]["note"] == note  # the app gets it back unchanged


def test_edit_can_clear_a_number(path):
    history.append([AAA], NOW, path)
    rid = history.read(path)[0]["id"]
    assert history.update(rid, {"target": None}, path)["target"] is None


def test_delete_one_and_by_ticker(path):
    other = TickerAnalysis("CCC", Verdict.BUY, data_date=date(2026, 10, 19), price=5.0)
    history.append([AAA, other], NOW, path)
    history.append([AAA], NOW, path)
    first = history.read(path)[0]["id"]
    history.delete(path, ids=[first])
    assert [r["ticker"] for r in history.read(path)] == ["CCC", "AAA"]
    history.delete(path, ticker="AAA")
    assert [r["ticker"] for r in history.read(path)] == ["CCC"]


def test_unknown_id(path):
    history.append([AAA], NOW, path)
    with pytest.raises(KeyError):
        history.update("nope", {"note": "x"}, path)
    with pytest.raises(KeyError):
        history.delete(path, ids=["nope"])


def test_lock_shared_with_other_processes(path, monkeypatch):
    lock = path.with_name(path.name + ".lock")
    lock.write_text("")  # another process is writing
    monkeypatch.setattr(history, "LOCK_TIMEOUT", 0.2)
    with pytest.raises(history.HistoryError, match="busy"):
        history.append([AAA], NOW, path)
    old = time.time() - history.STALE_LOCK - 5
    os.utime(lock, (old, old))  # left by a crashed process
    assert history.append([AAA], NOW, path) == 1 and not lock.exists()
