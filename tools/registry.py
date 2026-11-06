"""Tool registry. Maps tool names to their schemas and functions."""

import os
from typing import Any

from tools.bash import BashInput, bash
from tools.check_backups import CheckBackupsInput, check_backups
from tools.check_disk import CheckDiskInput, check_disk
from tools.check_health import CheckHealthInput, check_health
from tools.check_services import CheckServicesInput, check_services
from tools.edit_file import EditFileInput, edit_file
from tools.list_files import ListFilesInput, list_files
from tools.list_runs import ListRunsInput, list_runs
from tools.read_file import ReadFileInput, read_file
from tools.restart_service import RestartServiceInput, restart_service

_ALLOWED = {t.strip() for t in os.getenv("ALLOWED_TOOLS", "").split(",") if t.strip()}

# Tools that can modify state or run arbitrary commands require confirmation.
DESTRUCTIVE_TOOLS = {"restart_service", "edit_file", "bash"}

_INPUT_MODELS = {
    "read_file": ReadFileInput,
    "restart_service": RestartServiceInput,
    "check_health": CheckHealthInput,
    "list_runs": ListRunsInput,
    "check_disk": CheckDiskInput,
    "check_services": CheckServicesInput,
    "check_backups": CheckBackupsInput,
    "list_files": ListFilesInput,
    "bash": BashInput,
    "edit_file": EditFileInput,
}
if _ALLOWED:
    _INPUT_MODELS = {k: v for k, v in _INPUT_MODELS.items() if k in _ALLOWED}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": ReadFileInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_service",
            "description": "Restart an allowlisted service via the host actuator. Returns result + verification.",
            "parameters": RestartServiceInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_health",
            "description": "Check the HTTP health of a known service (read-only).",
            "parameters": CheckHealthInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_runs",
            "description": "List the most recent agent runs (id, status, iterations, tokens, time). Read-only.",
            "parameters": ListRunsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_disk",
            "description": "Check disk usage for a path. Returns total/used/free GB and used percentage.",
            "parameters": CheckDiskInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_services",
            "description": "Check whether systemd services are active. Returns active/inactive for each.",
            "parameters": CheckServicesInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_backups",
            "description": "Check whether a backup file exists and how old it is.",
            "parameters": CheckBackupsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at the given path.",
            "parameters": ListFilesInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command and return its output. Has a timeout.",
            "parameters": BashInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Write content to a file. Creates or overwrites the file.",
            "parameters": EditFileInput.model_json_schema(),
        },
    },
]

if _ALLOWED:
    TOOLS[:] = [t for t in TOOLS if t["function"]["name"] in _ALLOWED]

TOOL_FUNCTIONS: dict[str, Any] = {
    "read_file": read_file,
    "restart_service": restart_service,
    "check_health": check_health,
    "list_runs": list_runs,
    "check_disk": check_disk,
    "check_services": check_services,
    "check_backups": check_backups,
    "list_files": list_files,
    "bash": bash,
    "edit_file": edit_file,
}
if _ALLOWED:
    TOOL_FUNCTIONS = {k: v for k, v in TOOL_FUNCTIONS.items() if k in _ALLOWED}


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool by name. Returns a string result (never raises)."""
    if _ALLOWED and name not in _ALLOWED:
        return f"Error: tool '{name}' is not allowed in this mode"
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Error: unknown tool '{name}'"
    # Human-in-the-loop: destructive tools require explicit confirmation.
    if name in DESTRUCTIVE_TOOLS:
        if not arguments.get("confirmed"):
            return (
                f"Confirmation required: '{name}' is a destructive operation. "
                f"Verify necessity, then re-call with confirmed=true."
            )
    model = _INPUT_MODELS.get(name)
    if model is not None:
        try:
            validated = model(**arguments)
            arguments = validated.model_dump()
        except Exception as e:
            return f"Error: invalid arguments: {e}"
    # Strip the confirmation flag before calling the function.
    call_args = {k: v for k, v in arguments.items() if k != "confirmed"}
    try:
        return str(func(**call_args))
    except Exception as e:
        return f"Error: {e}"
