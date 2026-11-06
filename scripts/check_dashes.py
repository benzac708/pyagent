"""Pre-commit hook: reject em/en dashes in staged files."""

import sys

files = sys.argv[1:] if len(sys.argv) > 1 else []
bad = False
for f in files:
    if ".venv" in f or "node_modules" in f:
        continue
    try:
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if "\u2014" in line or "\u2013" in line:
                    print(f"{f}:{i}: em/en dash found")
                    bad = True
    except (UnicodeDecodeError, FileNotFoundError):
        pass
sys.exit(1 if bad else 0)
