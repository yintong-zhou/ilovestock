"""Web API: PIN gate, config, analysis on recorded data (offline)."""

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
    )
    return TestClient(app, base_url="http://127.0.0.1")


def unlocked(client):
    assert client.post("/api/pin/setup", json={"pin": "1234"}).status_code == 204
    return client


def test_first_visit_asks_for_pin(client):
    assert client.get("/api/pin/status").json() == {"configured": False, "unlocked": False}
    assert client.get("/api/config").status_code == 401  # nothing open before the PIN


def test_setup_unlocks_and_cannot_be_repeated(client):
    unlocked(client)
    assert client.get("/api/pin/status").json() == {"configured": True, "unlocked": True}
    assert client.post("/api/pin/setup", json={"pin": "9999"}).status_code == 409


@pytest.mark.parametrize("pin", ["123", "123456789", "12a4", ""])
def test_pin_format(client, pin):
    assert client.post("/api/pin/setup", json={"pin": pin}).status_code == 422


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
