"""Read a file and return its contents as a string."""

import os

from pydantic import BaseModel

_BLOCKED_NAMES = {".env", ".env.local", ".env.production", ".env.development"}
_BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".crt")
_BLOCKED_SUBSTRINGS = ("secret", "credential", "private_key", "id_rsa", "id_ed25519")


def _is_sensitive(path: str) -> bool:
    name = os.path.basename(path).lower()
    if name in _BLOCKED_NAMES or name.startswith(".env."):
        return True
    if name.endswith(_BLOCKED_SUFFIXES):
        return True
    if any(s in name for s in _BLOCKED_SUBSTRINGS):
        return True
    return False


class ReadFileInput(BaseModel):
    path: str


def read_file(path: str) -> str:
    """Read file contents. Returns error string on failure (never raises)."""
    if _is_sensitive(path):
        return "Error: reading this file is not allowed (sensitive path)"
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as e:
        return f"Error: {e}"
