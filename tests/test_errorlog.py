"""CSV error log: WARNING and above, readable in Excel and on the Log page."""

import io
import logging
from datetime import datetime

import pytest

from ilovestock.errorlog import FIELDS, CsvLog, read


@pytest.fixture
def logger():
    lg = logging.getLogger("ilovestock.test")
    lg.setLevel(logging.WARNING)
    lg.propagate = False
    yield lg
    for h in lg.handlers[:]:
        lg.removeHandler(h)
        h.close()


def test_writes_warning_and_above_only(tmp_path, logger):
    p = tmp_path / "x-log.csv"
    logger.addHandler(CsvLog(p))
    logger.info("i")
    logger.warning("w")
    logger.error("e")
    logger.critical("c")
    assert [r["level"] for r in read(p)] == ["CRITICAL", "ERROR", "WARNING"]  # newest first


def test_row_fields(tmp_path, logger):
    p = tmp_path / "x-log.csv"
    logger.addHandler(CsvLog(p))
    try:
        raise ValueError("boom")
    except ValueError:
        logger.warning("Skipped: %s", "x", exc_info=True, extra={"ticker": "ABC"})
    (row,) = read(p)
    assert (row["where"], row["ticker"], row["message"]) == ("ilovestock.test", "ABC", "Skipped: x")
    assert "Traceback" in row["details"] and "ValueError: boom" in row["details"]
    datetime.fromisoformat(row["time"])


def test_excel_format(tmp_path, logger):
    p = tmp_path / "x-log.csv"
    logger.addHandler(CsvLog(p))
    message = '=1+1, "q"\nline'
    logger.warning(message)
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw[3:].decode().splitlines()[0] == ",".join(FIELDS)
    assert b"\"'=1+1" in raw  # Excel shows it as text instead of running it
    assert read(p)[0]["message"] == message


def test_rotation_names_backup_csv(tmp_path, logger):
    p = tmp_path / "x-log.csv"
    logger.addHandler(CsvLog(p, max_bytes=300))
    for i in range(10):
        logger.warning("message %d", i)
    assert sorted(f.name for f in tmp_path.iterdir()) == ["x-log.1.csv", "x-log.csv"]
    for f in tmp_path.iterdir():
        assert f.read_bytes().startswith(b"\xef\xbb\xbf" + ",".join(FIELDS).encode())


def test_locked_log_is_quiet(tmp_path, logger, capsys):
    logger.addHandler(CsvLog(tmp_path))  # a directory: opening fails like a file locked by Excel
    logger.warning("w")  # the record is lost, the run goes on
    assert capsys.readouterr().err == ""  # no stdlib dump over the progress bar


def test_failed_write_does_not_raise(tmp_path, logger, monkeypatch):
    class DiskFull(io.StringIO):
        def flush(self):
            raise OSError(28, "No space left on device")

    h = CsvLog(tmp_path / "x-log.csv")
    monkeypatch.setattr(h, "_open", DiskFull)
    logger.addHandler(h)
    logger.warning("w")


def test_read_missing_file(tmp_path):
    assert read(tmp_path / "none.csv") == []
