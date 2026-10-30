"""Web API: PIN gate, config, analysis on recorded data (offline)."""

import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from ilovestock import config as cfgmod
from ilovestock import inputs, screener, watchlist
from ilovestock.api import pin as pinmod
from ilovestock.api.app import ProgressOut, create_app
from ilovestock.errorlog import CsvLog
from ilovestock.models import Quality
from ilovestock.providers import finviz
from ilovestock.providers.finviz import FinvizProvider
from ilovestock.providers.yahoo import YahooProvider


def make_client(tmp_path, provider=None):
    app = create_app(
        pin_path=tmp_path / "pin.json",
        config_path=tmp_path / "config.toml",
        provider=provider or FinvizProvider(YahooProvider()),
        static_dir=tmp_path / "no-dist",
        history_path=tmp_path / "history.csv",
        watchlist_path=tmp_path / "watchlist.txt",
        log_path=tmp_path / "log.csv",
    )
    c = TestClient(app, base_url="http://127.0.0.1")
    c.pin_path = tmp_path / "pin.json"
    return c


@pytest.fixture
def client(tmp_path, fake_yf, fake_finviz):
    return make_client(tmp_path)


def unlocked(client):
    pinmod.PinStore(client.pin_path).set("1234")  # what `ilovestock serve` does in the terminal
    assert client.post("/api/pin/unlock", json={"pin": "1234"}).status_code == 204
    return client


def test_first_visit_asks_for_pin(client):
    assert client.get("/api/pin/status").json() == {"configured": False, "unlocked": False}
    assert client.get("/api/config").status_code == 401  # nothing open before the PIN


def test_pin_cannot_be_set_over_http(client):
    assert client.post("/api/pin/setup", json={"pin": "1234"}).status_code in (404, 405)
    assert client.post("/api/pin/unlock", json={"pin": "1234"}).status_code == 401
    unlocked(client)
    assert client.get("/api/pin/status").json() == {"configured": True, "unlocked": True}


@pytest.mark.parametrize("pin", ["123", "123456789", "12a4", ""])
def test_pin_format(tmp_path, pin):
    with pytest.raises(pinmod.PinError):
        pinmod.PinStore(tmp_path / "pin.json").set(pin)


def test_cross_origin_refused(client):
    unlocked(client)
    evil = {"Origin": "http://localhost:5173"}  # another local page, same site for the cookie
    assert client.get("/api/config", headers=evil).status_code == 403
    own = {"Origin": "http://127.0.0.1"}
    assert client.get("/api/config", headers=own).status_code == 200
    assert "access-control-allow-origin" not in client.get("/api/config", headers=evil).headers


def test_pin_never_stored_in_clear(client, tmp_path):
    unlocked(client)
    assert "1234" not in (tmp_path / "pin.json").read_text()


def test_lock_and_unlock(client):
    unlocked(client)
    client.post("/api/pin/lock")
    assert client.get("/api/config").status_code == 401
    assert client.post("/api/pin/unlock", json={"pin": "0000"}).status_code == 401
    assert client.post("/api/pin/unlock", json={"pin": "1234"}).status_code == 204
    assert client.get("/api/config").status_code == 200


def test_throttle_after_repeated_failures(client):
    unlocked(client)
    client.post("/api/pin/lock")
    codes = [client.post("/api/pin/unlock", json={"pin": "0000"}).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    # even the right PIN waits during the lockout
    assert client.post("/api/pin/unlock", json={"pin": "1234"}).status_code == 429


def test_throttle_expires():
    now = [0.0]
    t = pinmod.Throttle(clock=lambda: now[0])
    for _ in range(pinmod.MAX_FAILS):
        t.failed()
    assert t.wait_seconds() == pinmod.LOCKOUT_SECONDS
    now[0] += pinmod.LOCKOUT_SECONDS
    assert t.wait_seconds() == 0


def test_change_pin(client):
    unlocked(client)
    body = {"current_pin": "0000", "new_pin": "5678"}
    assert client.post("/api/pin/change", json=body).status_code == 401
    body["current_pin"] = "1234"
    assert client.post("/api/pin/change", json=body).status_code == 204
    client.post("/api/pin/lock")
    assert client.post("/api/pin/unlock", json={"pin": "5678"}).status_code == 204


def test_untrusted_host_rejected(tmp_path):
    app = create_app(pin_path=tmp_path / "p.json", static_dir=tmp_path)
    c = TestClient(app, base_url="http://evil.example.com")
    assert c.get("/api/pin/status").status_code == 400


def test_config_read_and_update(client, tmp_path):
    unlocked(client)
    assert client.get("/api/config").json()["capital"] == 20000
    r = client.put("/api/config", json={"capital": 15000, "risk_pct": 0.5})
    assert r.status_code == 200 and r.json()["capital"] == 15000
    assert "capital = 15000" in (tmp_path / "config.toml").read_text()
    assert client.put("/api/config", json={"risk_pct": 3}).status_code == 422  # method limit
    assert client.put("/api/config", json={"nope": 1}).status_code == 422


def test_config_save_never_leaves_half_a_file(client, tmp_path, monkeypatch):
    unlocked(client)
    client.put("/api/config", json={"capital": 15000})
    before = (tmp_path / "config.toml").read_text()

    def crash(*a):
        raise OSError("disk full")

    monkeypatch.setattr(cfgmod.os, "replace", crash)
    with pytest.raises(OSError):
        client.put("/api/config", json={"capital": 9000})
    assert (tmp_path / "config.toml").read_text() == before


def test_analyze(client):
    unlocked(client)
    r = client.post("/api/analyze", json={"tickers": ["hzo", "WLST"]})
    assert r.status_code == 200, r.text
    doc = r.json()
    assert "not financial advice" in doc["disclaimer"]
    assert doc["data_date"] == "2026-10-19"
    hzo, wlst = doc["results"]
    assert hzo["ticker"] == "HZO" and hzo["verdict"] == "NO-BUY"
    assert any(c["note"] == "source: Finviz" for c in hzo["fundamental"])
    assert hzo["quality"]["roic_pct"] == 0.28
    assert hzo["plan"]["shares"] >= 1
    assert wlst["error"]  # no recorded data: reported per ticker


@pytest.mark.parametrize(
    "body", [{"tickers": []}, {"tickers": ["not a ticker"]}, {"tickers": ["A"] * 51}]
)
def test_analyze_bad_input(client, body):
    unlocked(client)
    if len(body["tickers"]) > 50:
        body["tickers"] = [f"T{i}" for i in range(51)]
    assert client.post("/api/analyze", json=body).status_code == 422


def test_frontend_not_built_message(client):
    assert "npm run build" in client.get("/").text


def test_parallel_guesses_cannot_skip_throttle(client):
    unlocked(client)
    client.post("/api/pin/lock")
    with ThreadPoolExecutor(8) as pool:
        codes = list(
            pool.map(
                lambda _: client.post("/api/pin/unlock", json={"pin": "0000"}).status_code, range(8)
            )
        )
    assert codes.count(401) == pinmod.MAX_FAILS and codes.count(429) == 3


def test_history_api(client):
    assert client.get("/api/history").status_code == 401  # locked
    unlocked(client)
    assert client.get("/api/history").json() == []
    client.post("/api/analyze", json={"tickers": ["HZO", "WLST"]})
    client.post("/api/analyze", json={"tickers": ["HZO"]})
    rows = client.get("/api/history").json()
    assert [r["ticker"] for r in rows] == ["HZO", "HZO"]  # WLST: data error, not saved
    rid = rows[0]["id"]

    r = client.patch(f"/api/history/{rid}", json={"note": "watching", "stop": 1.5})
    assert r.status_code == 200 and r.json()["note"] == "watching" and r.json()["edited_at"]
    assert client.patch(f"/api/history/{rid}", json={"verdict": "MAYBE"}).status_code == 422
    assert client.patch("/api/history/nope", json={"note": "x"}).status_code == 404

    assert client.delete(f"/api/history/{rid}").status_code == 204
    assert len(client.get("/api/history").json()) == 1
    assert client.delete("/api/history", params={"ticker": "hzo"}).status_code == 204
    assert client.get("/api/history").json() == []


def test_history_bulk_delete(client):
    assert client.post("/api/history/delete", json={"ids": ["x"]}).status_code == 401  # locked
    unlocked(client)
    for _ in range(3):
        client.post("/api/analyze", json={"tickers": ["HZO"]})
    ids = [r["id"] for r in client.get("/api/history").json()]
    r = client.post("/api/history/delete", json={"ids": [ids[0], "nope"]})
    assert r.status_code == 404 and len(client.get("/api/history").json()) == 3  # all or nothing
    assert client.post("/api/history/delete", json={"ids": ids[:2]}).status_code == 204
    assert [r["id"] for r in client.get("/api/history").json()] == ids[2:]
    assert client.post("/api/history/delete", json={"ids": []}).status_code == 422


def test_history_pdf(client):
    body = {"title": "History", "ids": ["x"]}
    assert client.post("/api/history/pdf", json=body).status_code == 401  # locked
    unlocked(client)
    client.post("/api/analyze", json={"tickers": ["HZO"]})
    rid = client.get("/api/history").json()[0]["id"]
    r = client.post("/api/history/pdf", json={"title": "History", "ids": [rid]})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert client.post("/api/history/pdf", json=body).status_code == 404  # no id matches
    r = client.post("/api/history/pdf", json={"title": "History", "ids": ["nope", rid]})
    assert r.status_code == 404 and "nope" in r.json()["detail"]  # never a partial PDF
    twice = {"title": "History", "ids": [rid, rid]}
    assert client.post("/api/history/pdf", json=twice).status_code == 422
    assert client.post("/api/history/pdf", json={"title": "History", "ids": []}).status_code == 422
    assert client.post("/api/history/pdf", json={"title": "Other", "ids": [rid]}).status_code == 422


def test_watchlist_api(client, tmp_path, monkeypatch):
    assert client.get("/api/watchlist").status_code == 401  # locked
    unlocked(client)
    assert client.get("/api/watchlist").json() == []
    assert client.put("/api/watchlist/hzo").json() == ["HZO"]
    assert client.put("/api/watchlist/HZO").json() == ["HZO"]  # already there: no duplicate
    assert client.put("/api/watchlist/BRK.B").json() == ["HZO", "BRK.B"]
    assert client.put("/api/watchlist/no%20way").status_code == 422
    assert inputs.read_watchlist(tmp_path / "watchlist.txt") == ["HZO", "BRK.B"]  # CLI reads it

    monkeypatch.setattr(watchlist, "MAX", 2)
    assert client.put("/api/watchlist/WLST").status_code == 422  # full
    assert client.delete("/api/watchlist/hzo").json() == ["BRK.B"]
    assert client.delete("/api/watchlist/HZO").json() == ["BRK.B"]  # already gone: no error


def test_pin_input_checked_before_hashing(client):
    assert client.post("/api/pin/unlock", json={"pin": "1" * 100}).status_code == 422
    big = "x" * (70 * 1024)
    assert client.post("/api/pin/unlock", json={"pin": big}).status_code == 413
    chunked = client.post("/api/pin/unlock", content=iter([big.encode()]))
    assert chunked.status_code == 411  # no Content-Length: the size is not known up front


# --- screener ---
def test_screen_needs_session(client):
    assert client.post("/api/screen", json={"max": 20}).status_code == 401


def test_screen_bounds(client):
    unlocked(client)
    assert client.post("/api/screen", json={"max": 51}).status_code == 422
    assert client.post("/api/screen", json={"max": 0}).status_code == 422


def test_screen_returns_counts_and_no_history(client, monkeypatch, tmp_path):
    unlocked(client)
    monkeypatch.setattr(finviz, "screener_rows", lambda url: [("HZO", 1e9)])
    r = client.post("/api/screen", json={"max": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["candidates"], body["passed"], body["hits"]) == (1, 0, [])
    assert "not financial advice" in body["disclaimer"]
    assert not (tmp_path / "history.csv").exists()


def test_screen_serializes_hits(client, monkeypatch):
    unlocked(client)
    hit = screener.ScreenHit("ABCD", "1,240M (small)", Quality(31.2, 18.1, 14.0, 4.1), 96.0, 2, 3)
    monkeypatch.setattr(
        screener, "screen", lambda *a, **k: screener.ScreenResult(47, 47, ["ZZZ"], [hit])
    )
    body = client.post("/api/screen", json={}).json()
    assert body["errors"] == ["ZZZ"]
    assert body["hits"][0]["quality"]["margin_change_pt"] == 4.1
    assert body["hits"][0]["roic_rank"] == 2


def test_screen_include_large(client, monkeypatch):
    unlocked(client)
    seen = {}

    def fake(*a, **k):
        seen.update(k)
        return screener.ScreenResult(0, 0, [], [])

    monkeypatch.setattr(screener, "screen", fake)
    body = client.post("/api/screen", json={"include_large": True}).json()
    assert seen["include_large"] is True and body["include_large"] is True
    assert client.post("/api/screen", json={}).json()["include_large"] is False


def test_screen_too_many_is_422(client, monkeypatch):
    unlocked(client)

    rows = [(f"T{i}", 1e9) for i in range(101)]
    monkeypatch.setattr(finviz, "screener_rows", lambda url: iter(rows))
    r = client.post("/api/screen", json={})
    assert r.status_code == 422 and "more than 100" in r.json()["detail"]


# --- progress and log ---
IDLE = {"screen": None, "analyze": None}


def test_progress_and_log_need_session(client):
    for path in ("/api/progress", "/api/log", "/api/log/csv"):
        assert client.get(path).status_code == 401


def test_progress_idle_and_after_failure(client, monkeypatch, caplog):
    unlocked(client)
    assert client.get("/api/progress").json() == IDLE

    def fail(cfg, include_large=False, progress=None):
        progress("Reading the Finviz screener: 1 rows, 1 candidates", 0, 0)
        raise finviz.FinvizError("page changed")

    monkeypatch.setattr(screener, "candidates", fail)
    assert client.post("/api/screen", json={}).status_code == 422
    assert client.get("/api/progress").json() == IDLE  # no stale bar after a failed run
    assert [r.levelname for r in caplog.records] == ["ERROR"]


def test_progress_during_screen(tmp_path, monkeypatch):
    seen = []

    class Spy:
        def fundamentals(self, t):
            seen.append(c.app.state.running["screen"].text)
            raise ConnectionError("offline")

    c = unlocked(make_client(tmp_path, Spy()))
    monkeypatch.setattr(screener, "candidates", lambda *a, **k: ["A"])
    assert c.post("/api/screen", json={}).json()["errors"] == ["A"]
    assert seen == ["Checking fundamentals: A (1 of 1)"]


def test_short_run_keeps_long_runs_progress(tmp_path, fake_yf, fake_finviz):
    # a Watchlist refresh ends while a long analysis runs: the long run's step stays on show
    step = ProgressOut(text="Analyzing A (3 of 40)", done=2, total=40)

    class Racing(FinvizProvider):
        def fundamentals(self, t):
            c.app.state.running["analyze"] = step  # the long run reports its next ticker
            return super().fundamentals(t)

    c = unlocked(make_client(tmp_path, Racing(YahooProvider())))
    assert c.post("/api/analyze", json={"tickers": ["HZO"]}).status_code == 200
    assert c.get("/api/progress").json()["analyze"] == step.model_dump()


def test_log_routes(client, tmp_path):
    unlocked(client)
    assert client.get("/api/log").json() == {"path": str(tmp_path / "log.csv"), "rows": []}
    assert client.get("/api/log/csv").status_code == 404
    record = {"name": "ilovestock.screener", "levelname": "WARNING", "levelno": logging.WARNING}
    record |= {"msg": "Skipped", "ticker": "AB"}
    CsvLog(tmp_path / "log.csv").handle(logging.makeLogRecord(record))
    (row,) = client.get("/api/log").json()["rows"]
    assert (row["level"], row["where"], row["ticker"], row["message"]) == (
        "WARNING",
        "ilovestock.screener",
        "AB",
        "Skipped",
    )
    r = client.get("/api/log/csv")
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")  # Excel reads the accents
