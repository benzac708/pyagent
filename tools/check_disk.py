"""Check disk usage for a path."""

import shutil

from pydantic import BaseModel


class CheckDiskInput(BaseModel):
    path: str = "/"


def check_disk(path: str = "/") -> str:
    """Return disk usage for *path* as a human-readable string."""
    try:
        total, used, free = shutil.disk_usage(path)
        pct = (used / total) * 100 if total else 0
        return (
            f"path={path} total={total // (1024**3)}GB "
            f"used={used // (1024**3)}GB free={free // (1024**3)}GB "
            f"used_pct={pct:.1f}%"
        )
    except Exception as e:
        return f"Error: {e}"
