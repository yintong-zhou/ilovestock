"""Local web API: thin layer over the core, plus the PIN gate. Serves the built frontend.

Listens on 127.0.0.1 only (see cli.serve). Every /api route except the PIN ones needs a session.
The PIN is set in the terminal by `ilovestock serve`, never over HTTP.
"""

import threading
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ilovestock import config as cfgmod
from ilovestock import history, inputs, pdf, screener, watchlist
from ilovestock.analysis import analyze_many
from ilovestock.api.pin import PinError, PinStore, Sessions, Throttle
from ilovestock.export import SOURCES, data_date
from ilovestock.models import DISCLAIMER, CriterionResult, TickerAnalysis, Verdict
from ilovestock.providers import finviz
from ilovestock.providers.base import MarketDataProvider
from ilovestock.providers.cache import CachedProvider
from ilovestock.providers.yahoo import YahooProvider

COOKIE = "ilovestock_session"
WEB_DIST = Path(__file__).resolve().parents[1] / "static"  # built by `npm run build` in web/
MAX_TICKERS = inputs.MAX_TICKERS  # ponytail: synchronous request; background job if lists grow
MAX_BODY = 64 * 1024  # every request body here is small: tickers, config, a note


Pin = Annotated[str, Field(pattern=r"^\d{4,8}$")]  # checked before any PBKDF2 work


class PinIn(BaseModel):
    pin: Pin


class PinChange(BaseModel):
    current_pin: Pin
    new_pin: Pin


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


class ScreenIn(BaseModel):
    max: int = Field(screener.DEFAULT_RESULTS, ge=1, le=screener.MAX_RESULTS)
    include_large: bool = False


class HistoryRow(BaseModel):
    """One saved analysis of one ticker: history.py's row dict."""

    id: str
    analyzed_at: str
    data_date: str | None
    ticker: str
    verdict: Verdict
    price: float | None
    entry: float | None
    stop: float | None
    target: float | None
    shares: int | None
    reasons: list[str]
    criteria: list[CriterionResult]
    note: str
    edited_at: str | None


class DeleteIn(BaseModel):
    ids: list[str] = Field(min_length=1)  # the analyses ticked on the page; MAX_BODY: ~4,000 ids


class PdfIn(BaseModel):
    title: Literal["History", "Watchlist"]
    ids: list[str] = Field(min_length=1, max_length=1000)  # the analyses shown on the page


class ScreenOut(BaseModel):
    disclaimer: str
    finviz_warning: str
    screened_on: str
    include_large: bool  # the Market cap rule was skipped
    candidates: int
    passed: int
    errors: list[str]
    hits: list[screener.ScreenHit]


def create_app(
    pin_path: Path | None = None,
    config_path: Path | None = None,
    provider: MarketDataProvider | None = None,
    static_dir: Path = WEB_DIST,
    history_path: Path | None = None,
    watchlist_path: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="ilovestock", description=DISCLAIMER)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"]
    )  # blocks DNS-rebinding pages from reaching the local API

    @app.middleware("http")
    async def small_bodies(request: Request, call_next):
        # The server reads exactly Content-Length bytes, so that header bounds the body. A chunked
        # body has no length up front: refused (fetch() always sends Content-Length here).
        if "transfer-encoding" in request.headers:
            return PlainTextResponse("Length required", status_code=411)
        if int(request.headers.get("content-length") or 0) > MAX_BODY:
            return PlainTextResponse("Request too large", status_code=413)
        return await call_next(request)

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

    check_lock = threading.Lock()  # routes run in a thread pool: one PIN check at a time

    def check_pin(pin: str) -> None:
        # check + verify + count as one step, so parallel guesses can't slip past the throttle.
        # ponytail: the lockout is global; every local client is 127.0.0.1, so a local process
        # can keep it engaged (it could also just stop the server). Per-client limits need clients
        # that can be told apart.
        with check_lock:
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
    def get_config() -> cfgmod.Config:
        try:
            return cfgmod.load(cfg_path)
        except cfgmod.ConfigError as e:
            raise HTTPException(422, str(e)) from e

    # Config and history edits come in as dicts: config.py and history.py check them with messages
    # the page can show (Pydantic's 422 detail is a list). Responses are typed.
    @app.put("/api/config", dependencies=[Depends(session)])
    def put_config(values: dict) -> cfgmod.Config:
        try:
            cfg = cfgmod.load(cfg_path, values)
        except (cfgmod.ConfigError, TypeError) as e:
            raise HTTPException(422, str(e)) from e
        cfgmod.save(cfg, cfg_path)
        return cfg

    @app.post("/api/analyze", dependencies=[Depends(session)])
    def analyze(body: AnalyzeIn) -> AnalyzeOut:
        try:
            cfg = cfgmod.load(cfg_path)
            tickers = [inputs.normalize(t) for t in body.tickers]
            if body.finviz_url:
                tickers = inputs.merge(
                    tickers, finviz.screener_tickers(body.finviz_url, MAX_TICKERS)
                )
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
        history.append(results, datetime.now(), history_path)
        return AnalyzeOut(
            disclaimer=DISCLAIMER,
            sources=SOURCES,
            data_date=data_date(results),
            finviz_warning=finviz.WARNING,
            results=results,
        )

    @app.post("/api/screen", dependencies=[Depends(session)])
    def screen(body: ScreenIn) -> ScreenOut:
        today = date.today()
        try:  # ponytail: synchronous like /api/analyze; the config's max_candidates bound it
            result = screener.screen(
                provider,
                cfgmod.load(cfg_path),
                today,
                body.max,
                include_large=body.include_large,
            )
        except (cfgmod.ConfigError, finviz.FinvizError) as e:
            raise HTTPException(422, str(e)) from e
        except Exception as e:
            raise HTTPException(502, f"Finviz screener not available: {e}") from e
        return ScreenOut(
            disclaimer=DISCLAIMER,
            finviz_warning=finviz.WARNING,
            screened_on=today.isoformat(),
            include_large=body.include_large,
            **vars(result),
        )

    @app.get("/api/history", dependencies=[Depends(session)])
    def history_rows() -> list[HistoryRow]:
        return history.read(history_path)

    @app.patch("/api/history/{row_id}", dependencies=[Depends(session)])
    def history_edit(row_id: str, changes: dict) -> HistoryRow:
        try:
            return history.update(row_id, changes, history_path)
        except history.HistoryError as e:
            raise HTTPException(422, str(e)) from e
        except KeyError as e:
            raise HTTPException(404, "Analysis not found in the history") from e

    @app.delete("/api/history/{row_id}", status_code=204, dependencies=[Depends(session)])
    def history_delete(row_id: str) -> None:
        try:
            history.delete(history_path, ids=[row_id])
        except KeyError as e:
            raise HTTPException(404, "Analysis not found in the history") from e

    @app.delete("/api/history", status_code=204, dependencies=[Depends(session)])
    def history_delete_ticker(ticker: str) -> None:
        history.delete(history_path, ticker=ticker.upper())

    @app.post("/api/history/delete", status_code=204, dependencies=[Depends(session)])
    def history_delete_many(body: DeleteIn) -> None:
        try:  # all or nothing: one unknown id (deleted elsewhere) deletes none
            history.delete(history_path, ids=body.ids)
        except KeyError as e:
            raise HTTPException(404, "Analysis not found in the history: reload the page") from e

    @app.post("/api/history/pdf", dependencies=[Depends(session)])
    def history_pdf(body: PdfIn) -> Response:
        if len(set(body.ids)) < len(body.ids):
            raise HTTPException(422, "Each analysis can appear only once")
        by_id = {r["id"]: r for r in history.read(history_path)}
        if missing := [i for i in body.ids if i not in by_id]:  # deleted since the page loaded
            raise HTTPException(404, f"Not in the history, reload the page: {', '.join(missing)}")
        rows = [by_id[i] for i in body.ids]
        return Response(pdf.render(rows, body.title, datetime.now()), media_type="application/pdf")

    # Each route returns the whole list: the page shows exactly what is on disk.
    @app.get("/api/watchlist", dependencies=[Depends(session)])
    def watchlist_read() -> list[str]:
        try:
            return watchlist.read(watchlist_path)
        except ValueError as e:  # a bad line written by hand
            raise HTTPException(422, str(e)) from e

    @app.put("/api/watchlist/{ticker}", dependencies=[Depends(session)])
    def watchlist_add(ticker: str) -> list[str]:
        try:
            return watchlist.add(ticker, watchlist_path)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.delete("/api/watchlist/{ticker}", dependencies=[Depends(session)])
    def watchlist_remove(ticker: str) -> list[str]:
        try:
            return watchlist.remove(ticker, watchlist_path)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    else:

        @app.get("/", response_class=PlainTextResponse)
        def not_built() -> str:
            return "Frontend not built: run `npm install && npm run build` in web/."

    return app
