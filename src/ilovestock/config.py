"""Config: course defaults < TOML file < CLI options."""

import dataclasses
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "ilovestock" / "config.toml"
MAX_RISK_PCT = 2.0  # course: above 2% per trade destroys the account
ENTRY_MODES = ("breakout", "pullback", "restart")
GROWTH_BASES = ("qoq", "yoy")

TEMPLATE = """\
# ilovestock config. CLI options override these values.

[portfolio]
capital = 20000          # equity portfolio capital
risk_pct = 1.0           # max loss per trade (%); above 2 -> rejected
max_position_pct = 10    # max weight per stock (%)

[plan]
r_multiple = 3           # take profit in R; below 2 -> trade discarded
entry_mode = "breakout"  # breakout | pullback | restart

[fundamental]
growth_basis = "qoq"     # qoq (vs previous quarter) | yoy (vs same quarter last year)
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
            ok = isinstance(v, str) if f.type is str else type(v) in (int, float)
            if not ok:
                raise ConfigError(f"{f.name}: valore non valido {v!r}")
        if self.capital <= 0:
            raise ConfigError("capital deve essere > 0")
        if not 0 < self.risk_pct <= MAX_RISK_PCT:
            raise ConfigError(
                f"risk_pct {self.risk_pct} rifiutato: deve essere > 0 e <= {MAX_RISK_PCT}"
            )
        if not 0 < self.max_position_pct <= 100:
            raise ConfigError("max_position_pct deve essere tra 0 e 100")
        if self.r_multiple <= 0:
            raise ConfigError("r_multiple deve essere > 0")
        if self.entry_mode not in ENTRY_MODES:
            raise ConfigError(f"entry_mode deve essere uno di {ENTRY_MODES}")
        if self.growth_basis not in GROWTH_BASES:
            raise ConfigError(f"growth_basis deve essere uno di {GROWTH_BASES}")


def load(path: Path | None = None, overrides: dict | None = None) -> Config:
    """Defaults, then file values, then non-None overrides. Unknown keys are errors."""
    path = path or CONFIG_PATH
    values = {k: v for section in DEFAULTS.values() for k, v in section.items()}
    if path.exists():
        try:
            file = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"{path}: TOML non valido: {e}") from e
        for section, items in file.items():
            if section not in DEFAULTS or not isinstance(items, dict):
                raise ConfigError(f"{path}: sezione sconosciuta [{section}]")
            for k, v in items.items():
                if k not in DEFAULTS[section]:
                    raise ConfigError(f"{path}: chiave sconosciuta {section}.{k}")
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
