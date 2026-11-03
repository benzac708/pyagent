"""List files in a directory."""

import os

from pydantic import BaseModel


class ListFilesInput(BaseModel):
    path: str = "."


def list_files(path: str = ".") -> str:
    """List files and directories at the given path."""
    try:
        entries = sorted(os.listdir(path))
        result = []
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                result.append(f"[dir]  {entry}/")
            else:
                result.append(f"[file] {entry}")
        return "\n".join(result) if result else "(empty directory)"
    except FileNotFoundError:
        return f"Error: directory not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as e:
        return f"Error: {e}"
