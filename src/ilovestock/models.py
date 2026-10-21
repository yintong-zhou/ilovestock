"""Data models shared by core, CLI and (later) the web API."""

import math
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

DISCLAIMER = "Educational screening tool, not financial advice."


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ND = "N/D"


class Verdict(StrEnum):
    BUY = "BUY"
    BUY_INCOMPLETE = "BUY*"  # --allow-missing: everything with data passed, some fundamentals N/D
    NO_BUY = "NO-BUY"


@dataclass
class CriterionResult:
    name: str
    status: Status
    value: float | str | None
    threshold: str
    note: str = ""

    def __post_init__(self):
        # numpy scalars (from pandas) -> plain float, so JSON/API serialization stays clean
        if self.value is not None and not isinstance(self.value, str):
            self.value = float(self.value)
            if not math.isfinite(self.value):  # NaN/inf is missing data: N/D, never PASS/FAIL
                self.value, self.status = None, Status.ND
                self.note = "; ".join(x for x in (self.note, "non-finite value") if x)


@dataclass
class Fundamentals:
    """Raw fundamental inputs. None = missing data (-> N/D, never PASS)."""

    sales: list[float | None]  # quarterly, most recent first (Yahoo)
    eps: list[float | None]  # quarterly diluted EPS, most recent first (Yahoo)
    roe_pct: float | None
    market_cap: float | None
    next_earnings: date | None
    inst_own_pct: float | None = None
    inst_trans_pct: float | None = None
    sales_growth_yoy_pct: float | None = None  # Finviz "Sales Q/Q" (actually YoY)
    eps_growth_yoy_pct: float | None = None  # Finviz "EPS Q/Q" (actually YoY)
    dividend_yield_pct: float | None = None  # None -> computed from the dividend history
    last_earnings: date | None = None  # Finviz, while the next date is not announced yet
    last_earnings_amc: bool | None = None  # reported after the close: reaction the next session
    sources: dict[str, str] = field(default_factory=dict)  # field name -> "Finviz" | "Yahoo"
    note: str = ""  # why Finviz data is missing
    fetched: date | None = None  # when this snapshot was taken (prices have their own date)


@dataclass
class TradePlan:
    entry: float
    stop: float
    target: float | None = None
    shares: int = 0
    max_loss: float = 0.0
    effective_risk: float = 0.0
    position_value: float = 0.0
    binding: str = ""  # "risk" or "exposure": which constraint set the shares
    risk_band: str = ""
    trailing_stop_10w: float | None = None
    trailing_stop_8w: float | None = None
    discarded: str | None = None  # reason the trade is not valid
    info: list[str] = field(default_factory=list)  # informational, non-blocking


@dataclass
class TickerAnalysis:
    ticker: str
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    fundamental: list[CriterionResult] = field(default_factory=list)
    technical: list[CriterionResult] = field(default_factory=list)
    earnings: CriterionResult | None = None
    plan: TradePlan | None = None
    data_date: date | None = None
    error: str | None = None
    price: float | None = None  # last close of the analyzed data
    fundamentals_date: date | None = None  # when the fundamentals were fetched
