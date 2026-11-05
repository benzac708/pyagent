"""Check whether a backup file exists and how old it is."""

import os
import time
from datetime import datetime, timezone

from pydantic import BaseModel


class CheckBackupsInput(BaseModel):
    path: str


def check_backups(path: str) -> str:
    """Report existence and age of a backup file at *path*."""
    try:
        if not os.path.exists(path):
            return f"path={path} exists=false"
        mtime = os.path.getmtime(path)
        age_hours = (time.time() - mtime) / 3600
        size = os.path.getsize(path)
        return (
            f"path={path} exists=true size={size} "
            f"mtime={datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()} "
            f"age_hours={age_hours:.1f}"
        )
    except Exception as e:
        return f"Error: {e}"
