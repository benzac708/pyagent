"""Configuration loader. Reads .env and validates required vars."""

import logging
import os
import stat
from typing import Any

import structlog
from dotenv import load_dotenv

load_dotenv()

# Exact key names that hold secrets (lowercased).
_SECRET_KEY_NAMES = {
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
}
# Key-name suffixes that indicate a secret value.
_SECRET_SUFFIXES = ("_key", "_secret", "_password", "_passwd", "_token", "_private_key")


def _is_secret_key(name: str) -> bool:
    low = name.lower()
    if low in _SECRET_KEY_NAMES:
        return True
    if low.endswith(_SECRET_SUFFIXES):
        return True
    # Avoid redacting metric fields like "total_tokens".
    if "token" in low and not low.endswith("_token") and low != "token":
        return False
    return False


def _redact_processor(logger: Any, method_name: str, event_dict: Any) -> Any:
    """Redact values of any key whose name looks like a secret."""
    for key in list(event_dict.keys()):
        if _is_secret_key(key):
            event_dict[key] = "[REDACTED]"
    # Redact secret-like substrings in string values (defence in depth).
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            for secret in (os.getenv("API_KEY", ""), os.getenv("FALLBACK_API_KEY", "")):
                if secret and secret in value:
                    event_dict[key] = value.replace(secret, "[REDACTED]")
    return event_dict


def _check_env_perms() -> None:
    """Warn if .env is world-readable."""
    for path in (".env",):
        try:
            mode = os.stat(path).st_mode
        except FileNotFoundError:
            continue
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            logging.getLogger("pyagent").warning(
                ".env is group/world readable (%s); chmod 600 recommended", oct(mode & 0o777)
            )


_check_env_perms()

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        _redact_processor,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, os.getenv("LOG_LEVEL", "info").upper(), logging.INFO)
    ),
)

log = structlog.get_logger()

# Primary provider
BASE_URL = os.getenv("BASE_URL", "https://api.openai.com/v1")
API_KEY = os.getenv("API_KEY", "")
MODEL = os.getenv("MODEL", "gpt-4o-mini")

# Fallback provider (optional)
FALLBACK_BASE_URL = os.getenv("FALLBACK_BASE_URL", "")
FALLBACK_API_KEY = os.getenv("FALLBACK_API_KEY", "")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "")

# App
DB_PATH = os.getenv("DB_PATH", "agent.db")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))


def is_mock_mode() -> bool:
    return os.getenv("MOCK_LLM", "").lower() in ("1", "true", "yes")


def validate() -> None:
    if is_mock_mode():
        return
    if not API_KEY:
        raise ValueError("API_KEY not set. Copy .env.example to .env and add your key.")
    if not BASE_URL:
        raise ValueError("BASE_URL not set.")


def has_fallback() -> bool:
    return bool(FALLBACK_BASE_URL and FALLBACK_API_KEY and FALLBACK_MODEL)


def __getattr__(name: str) -> Any:
    """Dynamic module attributes for mock mode."""
    if name in ("MOCK_LLM", "MOCK_MODE", "mock_mode"):
        return is_mock_mode()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
