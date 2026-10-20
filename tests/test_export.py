import io
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from ilovestock import export
from ilovestock.config import load
from ilovestock.models import CriterionResult, Status, TickerAnalysis, TradePlan, Verdict

CFG = load(Path("does-not-exist.toml"))
NOW = datetime(2026, 10, 20, 15, 4)
RESULTS = [
    TickerAnalysis(
        "AAA",
        Verdict.NO_BUY,
        ["ROE: FAIL"],
        fundamental=[CriterionResult("ROE", Status.FAIL, 5.0, "> 15%", "a|b")],
        technical=[CriterionResult("SMA 200d", Status.PASS, 10.0, "> 9.00")],
        earnings=CriterionResult("Next earnings", Status.ND, None, "> 10 days"),
        plan=TradePlan(entry=10, stop=9, target=13, shares=20, binding="risk"),
        data_date=date(2026, 10, 19),
    ),
    TickerAnalysis("BBB", Verdict.NO_BUY, ["Data error: boom"], error="boom"),
]


def test_parse_formats():
    assert export.parse_formats("md, CSV,md") == ["md", "csv"]
    with pytest.raises(ValueError):
        export.parse_formats("md,pdf")
    with pytest.raises(ValueError):
        export.parse_formats(",")


def test_csv_reads_back_with_pandas():
    df = pd.read_csv(io.StringIO(export.to_csv(RESULTS, NOW)), comment="#")
    assert df["ticker"].tolist() == ["AAA", "BBB"]
    assert df.loc[0, "shares"] == 20 and df.loc[0, "ROE status"] == "FAIL"
    assert df.loc[0, "Next earnings status"] == "N/D"
    assert df.loc[1, "reasons"] == "Data error: boom"


def test_json_is_complete():
    doc = json.loads(export.to_json(RESULTS, CFG, NOW))
    assert doc["data_date"] == "2026-10-19"
    assert doc["config"]["risk_pct"] == 1.0
    assert doc["results"][0]["plan"]["shares"] == 20
    assert doc["results"][0]["fundamental"][0]["status"] == "FAIL"


def test_markdown_escapes_table_cells():
    md = export.to_markdown(RESULTS, CFG, NOW)
    assert "a\\|b" in md
    assert "## BBB: NO-BUY" in md and "Data error: boom" in md
    assert md.count(export.NOTICE) == 2  # top and bottom


def test_write_reports_layout(tmp_path):
    paths = export.write_reports(RESULTS, ["json", "md"], tmp_path, CFG, NOW)
    assert [p.relative_to(tmp_path).as_posix() for p in paths] == [
        "2026-10-20_1504/results.json",
        "2026-10-20_1504/report.md",
    ]
