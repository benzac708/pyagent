"""Tool registry. Maps tool names to their schemas and functions."""


from tools.bash import BashInput, bash
from tools.edit_file import EditFileInput, edit_file
from tools.list_files import ListFilesInput, list_files
from tools.read_file import ReadFileInput, read_file

TOOLS = [
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

TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
    "bash": bash,
    "edit_file": edit_file,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name. Returns a string result (never raises)."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Error: unknown tool '{name}'"
    try:
        return str(func(**arguments))
    except Exception as e:
        return f"Error: {e}"
