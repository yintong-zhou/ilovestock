"""Config: course defaults < TOML file < CLI options."""

import dataclasses
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "ilovestock" / "config.toml"
MAX_RISK_PCT = 2.0  # course: above 2% per trade destroys the account
MAX_POSITION_PCT = 10.0  # course: a single stock is always at most 10% of the portfolio
ENTRY_MODES = ("breakout", "pullback", "restart")
GROWTH_BASES = ("qoq", "yoy")

TEMPLATE = """\
# ilovestock config. CLI options override these values.

[portfolio]
capital = 20000          # equity portfolio capital
risk_pct = 1.0           # max loss per trade (%); above 2 -> rejected
max_position_pct = 10    # max weight per stock (%); above 10 -> rejected

[plan]
r_multiple = 3           # take profit in R; below 2 -> trade discarded
entry_mode = "breakout"  # breakout | pullback | restart

[fundamental]
growth_basis = "yoy"     # yoy (Finviz, vs same quarter a year ago) | qoq (Yahoo, vs last quarter)
sales_growth_min = 20
eps_growth_min = 15
roe_min = 15
institutional_own_max = 80

[market_cap]             # band upper bounds, millions USD (Finviz bands)
nano_max = 50
micro_max = 300
small_max = 2000
mid_max = 10000
large_max = 200000
"""
DEFAULTS: dict[str, dict] = tomllib.loads(TEMPLATE)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    capital: float
    risk_pct: float
    max_position_pct: float
    r_multiple: float
    entry_mode: str
    growth_basis: str
    sales_growth_min: float
    eps_growth_min: float
    roe_min: float
    institutional_own_max: float
    nano_max: float
    micro_max: float
    small_max: float
    mid_max: float
    large_max: float

    def __post_init__(self):
        for f in dataclasses.fields(self):
            v = getattr(self, f.name)
            if f.type is str:
                ok = isinstance(v, str)
            else:  # NaN/inf would slip past every range check below
                ok = type(v) in (int, float) and math.isfinite(v)
            if not ok:
                raise ConfigError(f"{f.name}: invalid value {v!r}")
        if self.capital <= 0:
            raise ConfigError("capital must be > 0")
        if not 0 < self.risk_pct <= MAX_RISK_PCT:
            raise ConfigError(
                f"risk_pct {self.risk_pct} rejected: must be > 0 and <= {MAX_RISK_PCT}"
            )
        if not 0 < self.max_position_pct <= MAX_POSITION_PCT:
            raise ConfigError(
                f"max_position_pct {self.max_position_pct} rejected: must be > 0 and "
                f"<= {MAX_POSITION_PCT}"
            )
        for k in ("sales_growth_min", "eps_growth_min", "roe_min"):
            if getattr(self, k) < 0:
                raise ConfigError(f"{k} must be >= 0: the method looks for growth")
        if not 0 < self.institutional_own_max <= 100:
            raise ConfigError("institutional_own_max must be between 0 and 100")
        if self.r_multiple <= 0:
            raise ConfigError("r_multiple must be > 0")
        if self.entry_mode not in ENTRY_MODES:
            raise ConfigError(f"entry_mode must be one of {ENTRY_MODES}")
        if self.growth_basis not in GROWTH_BASES:
            raise ConfigError(f"growth_basis must be one of {GROWTH_BASES}")
        bands = (self.nano_max, self.micro_max, self.small_max, self.mid_max, self.large_max)
        if not 0 < bands[0] < bands[1] < bands[2] < bands[3] < bands[4]:
            raise ConfigError("market cap bands must be > 0 and increasing (nano < ... < large)")


def load(path: Path | None = None, overrides: dict | None = None) -> Config:
    """Defaults, then file values, then non-None overrides. Unknown keys are errors."""
    path = path or CONFIG_PATH
    values = {k: v for section in DEFAULTS.values() for k, v in section.items()}
    if path.exists():
        try:
            file = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"{path}: invalid TOML: {e}") from e
        for section, items in file.items():
            if section not in DEFAULTS or not isinstance(items, dict):
                raise ConfigError(f"{path}: unknown section [{section}]")
            for k, v in items.items():
                if k not in DEFAULTS[section]:
                    raise ConfigError(f"{path}: unknown key {section}.{k}")
                values[k] = v
    for k, v in (overrides or {}).items():
        if v is not None:
            values[k] = v
    return Config(**values)


def dump(cfg: Config) -> str:
    """Effective config as TOML."""
    flat = dataclasses.asdict(cfg)
    lines = []
    for section, keys in DEFAULTS.items():
        lines.append(f"[{section}]")
        lines += [f"{k} = {flat[k]!r}".replace("'", '"') for k in keys]
        lines.append("")
    return "\n".join(lines)
