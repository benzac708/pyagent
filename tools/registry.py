"""Tool registry. Maps tool names to their schemas and functions."""

from tools.read_file import ReadFileInput, read_file

# Registry: list of OpenAI-compatible tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": ReadFileInput.model_json_schema(),
        },
    },
]

# Function dispatch: name -> callable
TOOL_FUNCTIONS = {
    "read_file": read_file,
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
