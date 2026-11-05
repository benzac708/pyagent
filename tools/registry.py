"""Tool registry. Maps tool names to their schemas and functions."""

from typing import Any

from tools.bash import BashInput, bash
from tools.check_backups import CheckBackupsInput, check_backups
from tools.check_disk import CheckDiskInput, check_disk
from tools.check_services import CheckServicesInput, check_services
from tools.edit_file import EditFileInput, edit_file
from tools.list_files import ListFilesInput, list_files
from tools.read_file import ReadFileInput, read_file

_INPUT_MODELS = {
    "read_file": ReadFileInput,
    "check_disk": CheckDiskInput,
    "check_services": CheckServicesInput,
    "check_backups": CheckBackupsInput,
    "list_files": ListFilesInput,
    "bash": BashInput,
    "edit_file": EditFileInput,
}

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

TOOL_FUNCTIONS: dict[str, Any] = {
    "read_file": read_file,
    "check_disk": check_disk,
    "check_services": check_services,
    "check_backups": check_backups,
    "list_files": list_files,
    "bash": bash,
    "edit_file": edit_file,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool by name. Returns a string result (never raises)."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Error: unknown tool '{name}'"
    model = _INPUT_MODELS.get(name)
    if model is not None:
        try:
            validated = model(**arguments)
            arguments = validated.model_dump()
        except Exception as e:
            return f"Error: invalid arguments: {e}"
    try:
        return str(func(**arguments))
    except Exception as e:
        return f"Error: {e}"
