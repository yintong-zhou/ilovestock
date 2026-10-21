"""Web API: PIN gate, config, analysis on recorded data (offline)."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from ilovestock.api import pin as pinmod
from ilovestock.api.app import create_app
from ilovestock.providers.finviz import FinvizProvider
from ilovestock.providers.yahoo import YahooProvider


@pytest.fixture
def client(tmp_path, fake_yf, fake_finviz):
    app = create_app(
        pin_path=tmp_path / "pin.json",
        config_path=tmp_path / "config.toml",
        provider=FinvizProvider(YahooProvider()),
        static_dir=tmp_path / "no-dist",
        history_path=tmp_path / "history.csv",
    )
    c = TestClient(app, base_url="http://127.0.0.1")
    c.pin_path = tmp_path / "pin.json"
    return c


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
    assert client.put("/api/config", json={"risk_pct": 3}).status_code == 422  # course limit
    assert client.put("/api/config", json={"nope": 1}).status_code == 422


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
