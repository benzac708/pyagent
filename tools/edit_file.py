"""Edit a file by writing new content (atomic: temp file + rename)."""

import os
import tempfile

from pydantic import BaseModel


class EditFileInput(BaseModel):
    path: str
    content: str


def edit_file(path: str, content: str) -> str:
    """Write content to a file. Uses temp file + rename for atomicity."""
    try:
        dir_name = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(tmp_path, path)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception:
            os.unlink(tmp_path)
            raise
    except Exception as e:
        return f"Error: {e}"
