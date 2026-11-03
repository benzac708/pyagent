"""Edit a file by writing new content (atomic: temp file + rename)."""

import os
import tempfile

from pydantic import BaseModel

from tools.read_file import _is_sensitive


class EditFileInput(BaseModel):
    path: str
    content: str


def edit_file(path: str, content: str) -> str:
    """Write content to a file. Uses temp file + rename for atomicity."""
    if _is_sensitive(path):
        return "Error: writing this file is not allowed (sensitive path)"
    try:
        abs_path = os.path.abspath(path)
        dir_name = os.path.dirname(abs_path) or "."
        os.makedirs(dir_name, exist_ok=True)
        # Preserve existing mode if file exists, else 0644.
        if os.path.exists(abs_path):
            mode = os.stat(abs_path).st_mode & 0o777
        else:
            mode = 0o644
        fd, tmp_path = tempfile.mkstemp(dir=dir_name)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.chmod(tmp_path, mode)
            os.replace(tmp_path, path)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception:
            os.unlink(tmp_path)
            raise
    except Exception as e:
        return f"Error: {e}"
