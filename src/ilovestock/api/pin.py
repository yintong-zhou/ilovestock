"""PIN gate for the local web app: hashed PIN on disk, in-memory sessions, retry throttle.

Not an account system: one PIN for the one local user. The PIN is never stored in clear.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

from ilovestock.config import CONFIG_PATH

PIN_PATH = CONFIG_PATH.parent / "web_pin.json"
PIN_RE = re.compile(r"^\d{4,8}$")
ITERATIONS = 600_000  # PBKDF2-SHA256, OWASP 2023 minimum
MAX_FAILS = 5
LOCKOUT_SECONDS = 30


class PinError(ValueError):
    pass


def _hash(pin: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations).hex()


class PinStore:
    def __init__(self, path: Path = PIN_PATH):
        self.path = path

    def configured(self) -> bool:
        return self.path.exists()

    def set(self, pin: str) -> None:
        if not PIN_RE.match(pin):
            raise PinError("PIN must be 4 to 8 digits")
        salt = secrets.token_bytes(16)
        data = {"salt": salt.hex(), "iterations": ITERATIONS, "hash": _hash(pin, salt, ITERATIONS)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(self.path, 0o600)  # owner only (best effort on Windows)

    def verify(self, pin: str) -> bool:
        if not self.configured():
            return False
        data = json.loads(self.path.read_text(encoding="utf-8"))
        candidate = _hash(pin, bytes.fromhex(data["salt"]), data["iterations"])
        return hmac.compare_digest(candidate, data["hash"])

    def reset(self) -> None:
        self.path.unlink(missing_ok=True)


class Throttle:
    """After MAX_FAILS wrong PINs in a row, refuse attempts for LOCKOUT_SECONDS."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.fails = 0
        self.locked_until = 0.0

    def wait_seconds(self) -> int:
        return max(0, round(self.locked_until - self.clock()))

    def failed(self) -> None:
        self.fails += 1
        if self.fails >= MAX_FAILS:
            self.fails = 0
            self.locked_until = self.clock() + LOCKOUT_SECONDS

    def succeeded(self) -> None:
        self.fails = 0


class Sessions:
    """Random tokens kept in memory: a server restart locks the app again."""

    def __init__(self):
        self.tokens: set[str] = set()

    def new(self) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens.add(token)
        return token

    def valid(self, token: str | None) -> bool:
        return token is not None and token in self.tokens

    def revoke(self, token: str | None) -> None:
        self.tokens.discard(token)

    def clear(self) -> None:
        self.tokens.clear()
