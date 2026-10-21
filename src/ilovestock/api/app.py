"""Local web API: thin layer over the core, plus the PIN gate. Serves the built frontend.

Listens on 127.0.0.1 only (see cli.serve). Every /api route except the PIN ones needs a session.
The PIN is set in the terminal by `ilovestock serve`, never over HTTP.
"""

import dataclasses
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ilovestock import config as cfgmod
from ilovestock import inputs
from ilovestock.analysis import analyze_many
from ilovestock.api.pin import PinError, PinStore, Sessions, Throttle
from ilovestock.export import SOURCES, data_date
from ilovestock.models import DISCLAIMER, TickerAnalysis
from ilovestock.providers import finviz
from ilovestock.providers.base import MarketDataProvider
from ilovestock.providers.cache import CachedProvider
from ilovestock.providers.yahoo import YahooProvider

COOKIE = "ilovestock_session"
WEB_DIST = Path(__file__).resolve().parents[1] / "static"  # built by `npm run build` in web/
MAX_TICKERS = 50  # ponytail: synchronous request; move to a background job if lists grow


class PinIn(BaseModel):
    pin: str


class PinChange(BaseModel):
    current_pin: str
    new_pin: str


class PinStatus(BaseModel):
    configured: bool
    unlocked: bool


class AnalyzeIn(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    finviz_url: str | None = None
    allow_missing: bool = False


class AnalyzeOut(BaseModel):
    disclaimer: str
    sources: list[str]
    data_date: str
    finviz_warning: str
    results: list[TickerAnalysis]


def create_app(
    pin_path: Path | None = None,
    config_path: Path | None = None,
    provider: MarketDataProvider | None = None,
    static_dir: Path = WEB_DIST,
) -> FastAPI:
    app = FastAPI(title="ilovestock", description=DISCLAIMER)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"]
    )  # blocks DNS-rebinding pages from reaching the local API

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        # No CORS: only this app's own page may call the API. Other local pages (any port is
        # "same site" for the cookie) are refused. The Vite dev proxy keeps the origin equal.
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return PlainTextResponse("Cross-origin request refused", status_code=403)
        return await call_next(request)

    pins = PinStore(pin_path) if pin_path else PinStore()
    sessions, throttle = Sessions(), Throttle()
    provider = provider or CachedProvider(finviz.FinvizProvider(YahooProvider()))
    cfg_path = config_path or cfgmod.CONFIG_PATH

    def login(response: Response) -> None:
        response.set_cookie(COOKIE, sessions.new(), httponly=True, samesite="strict")

    def check_pin(pin: str) -> None:
        if wait := throttle.wait_seconds():
            raise HTTPException(429, f"Too many attempts. Try again in {wait} s.")
        if not pins.verify(pin):
            throttle.failed()
            raise HTTPException(401, "Wrong PIN")
        throttle.succeeded()

    def session(request: Request) -> None:
        if not sessions.valid(request.cookies.get(COOKIE)):
            raise HTTPException(401, "Locked")

    @app.get("/api/pin/status")
    def pin_status(request: Request) -> PinStatus:
        return PinStatus(
            configured=pins.configured(), unlocked=sessions.valid(request.cookies.get(COOKIE))
        )

    @app.post("/api/pin/unlock", status_code=204)
    def pin_unlock(body: PinIn, response: Response) -> None:
        check_pin(body.pin)
        login(response)

    @app.post("/api/pin/lock", status_code=204)
    def pin_lock(request: Request, response: Response) -> None:
        sessions.revoke(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE)

    @app.post("/api/pin/change", status_code=204, dependencies=[Depends(session)])
    def pin_change(body: PinChange, response: Response) -> None:
        check_pin(body.current_pin)
        try:
            pins.set(body.new_pin)
        except PinError as e:
            raise HTTPException(422, str(e)) from e
        sessions.clear()  # other open tabs must unlock with the new PIN
        login(response)

    @app.get("/api/config", dependencies=[Depends(session)])
    def get_config() -> dict:
        try:
            return dataclasses.asdict(cfgmod.load(cfg_path))
        except cfgmod.ConfigError as e:
            raise HTTPException(422, str(e)) from e

    @app.put("/api/config", dependencies=[Depends(session)])
    def put_config(values: dict) -> dict:
        try:
            cfg = cfgmod.load(cfg_path, values)
        except (cfgmod.ConfigError, TypeError) as e:
            raise HTTPException(422, str(e)) from e
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(cfgmod.dump(cfg), encoding="utf-8")
        return dataclasses.asdict(cfg)

    @app.post("/api/analyze", dependencies=[Depends(session)])
    def analyze(body: AnalyzeIn) -> AnalyzeOut:
        try:
            cfg = cfgmod.load(cfg_path)
            tickers = [inputs.normalize(t) for t in body.tickers]
            if body.finviz_url:
                tickers = inputs.merge(tickers, finviz.screener_tickers(body.finviz_url))
        except (cfgmod.ConfigError, ValueError, finviz.FinvizError) as e:
            raise HTTPException(422, str(e)) from e
        if not tickers:
            raise HTTPException(422, "No tickers: enter at least one ticker or a Finviz URL")
        if len(tickers) > MAX_TICKERS:
            raise HTTPException(422, f"Too many tickers ({len(tickers)}): max {MAX_TICKERS}")
        try:
            results = analyze_many(tickers, provider, cfg, date.today(), body.allow_missing)
        except Exception as e:
            raise HTTPException(502, f"Benchmark data not available: {e}") from e
        return AnalyzeOut(
            disclaimer=DISCLAIMER,
            sources=SOURCES,
            data_date=data_date(results),
            finviz_warning=finviz.WARNING,
            results=results,
        )

    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    else:

        @app.get("/", response_class=PlainTextResponse)
        def not_built() -> str:
            return "Frontend not built: run `npm install && npm run build` in web/."

    return app
