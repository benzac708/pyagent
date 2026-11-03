"""Configuration loader. Reads .env and validates required vars."""

import os

from dotenv import load_dotenv

load_dotenv()

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


def validate():
    if not API_KEY:
        raise ValueError("API_KEY not set. Copy .env.example to .env and add your key.")
    if not BASE_URL:
        raise ValueError("BASE_URL not set.")


def has_fallback():
    return bool(FALLBACK_BASE_URL and FALLBACK_API_KEY and FALLBACK_MODEL)
