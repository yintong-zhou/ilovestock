"""Config precedence, inputs, and the CLI end to end on recorded data (offline)."""

import pytest
from rich.console import Console
from typer.testing import CliRunner

from ilovestock import cli, config, history, inputs
from ilovestock.models import DISCLAIMER

runner = CliRunner()


# --- config ---
def test_precedence_default_file_cli(tmp_path):
    path = tmp_path / "c.toml"
    assert config.load(path).capital == 20000  # course default
    path.write_text("[portfolio]\ncapital = 5000\nrisk_pct = 0.5\n")
    cfg = config.load(path)
    assert (cfg.capital, cfg.risk_pct, cfg.r_multiple) == (5000, 0.5, 3)  # file > default
    cfg = config.load(path, {"capital": 7000, "risk_pct": None})
    assert (cfg.capital, cfg.risk_pct) == (7000, 0.5)  # CLI > file; None = not given


@pytest.mark.parametrize(
    "text",
    [
        "[portfolio]\nrisk_pct = 3\n",  # course hard limit
        "[portfolio]\nfoo = 1\n",
        "[nope]\nx = 1\n",
        '[portfolio]\ncapital = "a lot"\n',
        "[plan]\nentry_mode = 'yolo'\n",
        "not toml ===",
        "[portfolio]\ncapital = nan\n",
        "[plan]\nr_multiple = inf\n",
        "[market_cap]\nsmall_max = 100\n",  # bands must increase: micro 300 > small 100
        "[portfolio]\nmax_position_pct = 25\n",  # course: a stock is at most 10%
        "[fundamental]\nroe_min = -5\n",
        "[fundamental]\ninstitutional_own_max = 120\n",
    ],
)
def test_invalid_config_rejected(tmp_path, text):
    path = tmp_path / "c.toml"
    path.write_text(text)
    with pytest.raises(config.ConfigError):
        config.load(path)


def test_dump_roundtrip(tmp_path):
    path = tmp_path / "c.toml"
    path.write_text(config.dump(config.load(path, {"capital": 1234.5})))
    assert config.load(path).capital == 1234.5


# --- inputs ---
def test_watchlist_txt_and_csv(tmp_path):
    txt = tmp_path / "w.txt"
    txt.write_text("hzo\n\n# comment\nNIO  # inline\n")
    csv = tmp_path / "w.csv"
    csv.write_text('Ticker,Name\n"AAPL",Apple\nmsft,Microsoft\n')
    assert inputs.read_watchlist(txt) == ["HZO", "NIO"]
    assert inputs.read_watchlist(csv) == ["AAPL", "MSFT"]


def test_invalid_ticker_rejected():
    with pytest.raises(ValueError):
        inputs.normalize("not a ticker")


def test_merge_dedupes_in_order():
    assert inputs.merge(["A", "B"], ["B", "C"], ["A", "D"]) == ["A", "B", "C", "D"]


# --- CLI ---
@pytest.fixture
def offline(monkeypatch, fake_yf, fake_finviz, tmp_path):
    monkeypatch.setattr(cli, "CachedProvider", lambda p: p)
    monkeypatch.setattr(cli, "console", Console(width=200))
    monkeypatch.setattr(cli.finviz, "screener_tickers", lambda url, limit=None: ["SCRN", "HZO"])
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr(history, "HISTORY_PATH", tmp_path / "history.csv")
    return tmp_path


def test_help():
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0 and "analyze" in result.output


def test_analyze_combines_three_inputs(offline):
    wl = offline / "w.txt"
    wl.write_text("HZO\nWLST\n")
    result = runner.invoke(
        cli.app,
        ["analyze", "HZO", "--watchlist", str(wl), "--finviz-url", "https://finviz.com/x"],
    )
    assert result.exit_code == 0, result.output
    rows = [line.split("│")[1].strip() for line in result.output.splitlines() if "NO-BUY" in line]
    assert rows == ["HZO", "WLST", "SCRN"]  # union, deduplicated, input order
    assert "Data error" in result.output  # WLST/SCRN have no recorded data: reported, not crashed
    assert DISCLAIMER in result.output.replace("\n", " ")


def test_analyze_detail_shows_criteria(offline):
    result = runner.invoke(cli.app, ["analyze", "HZO", "--detail"])
    assert result.exit_code == 0, result.output
    for text in ("Sales growth YOY", "source: Finviz", "DMI 18d", "Trade plan", "Next earnings"):
        assert text in result.output


def test_analyze_rejects_risk_above_2(offline):
    result = runner.invoke(cli.app, ["analyze", "HZO", "--risk-pct", "2.5"])
    assert result.exit_code == 1 and "risk_pct" in result.output


def test_analyze_needs_tickers(offline):
    assert runner.invoke(cli.app, ["analyze"]).exit_code == 1


def test_config_init_show_path(offline):
    assert runner.invoke(cli.app, ["config", "init"]).exit_code == 0
    assert runner.invoke(cli.app, ["config", "init"]).exit_code == 1  # no silent overwrite
    show = runner.invoke(cli.app, ["config", "show"])
    assert show.exit_code == 0 and "capital = 20000" in show.output
    path = runner.invoke(cli.app, ["config", "path"])
    assert "config.toml" in path.output


def test_analyze_exports_three_files(offline):
    out = offline / "reports"
    result = runner.invoke(
        cli.app, ["analyze", "HZO", "WLST", "--export", "md,csv,json", "--out-dir", str(out)]
    )
    assert result.exit_code == 0, result.output
    files = sorted(p.name for p in out.glob("*/*"))
    assert files == ["report.md", "results.csv", "results.json"]
    for path in out.glob("*/*"):
        text = path.read_text(encoding="utf-8")
        assert DISCLAIMER in text
        assert "2026-10-19" in text  # data date of the recorded HZO prices
        assert "Finviz" in text and "Yahoo" in text  # sources


def test_analyze_rejects_unknown_export_format(offline):
    result = runner.invoke(cli.app, ["analyze", "HZO", "--export", "pdf"])
    assert result.exit_code == 1 and "export format" in result.output


def test_serve_asks_pin_in_terminal(monkeypatch, tmp_path):
    import uvicorn

    from ilovestock.api import pin as pinmod

    path, real = tmp_path / "pin.json", pinmod.PinStore
    monkeypatch.setattr(pinmod, "PinStore", lambda: real(path))
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    result = runner.invoke(cli.app, ["serve"], input="12\n12\n4821\n4821\n")
    assert result.exit_code == 0, result.output
    assert "4 to 8 digits" in result.output  # "12" refused, asked again
    assert real(path).verify("4821")


def test_analyze_saves_history(offline):
    runner.invoke(cli.app, ["analyze", "HZO"])
    runner.invoke(cli.app, ["analyze", "HZO", "NOPE"])  # NOPE: data error, not saved
    rows = history.read(offline / "history.csv")
    assert [r["ticker"] for r in rows] == ["HZO", "HZO"] and rows[0]["price"] > 0


def test_analyze_ticker_limit(offline):
    result = runner.invoke(cli.app, ["analyze", "AAA", "BBB", "CCC", "--max-tickers", "2"])
    assert result.exit_code == 1 and "max 2" in result.output
