"""Read a file and return its contents as a string."""

from pydantic import BaseModel


class ReadFileInput(BaseModel):
    path: str


def read_file(path: str) -> str:
    """Read file contents. Returns error string on failure (never raises)."""
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as e:
        return f"Error: {e}"
