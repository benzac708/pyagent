"""Shared test helpers and environment setup for pyagent tests."""

import os
import tempfile

# Configure environment BEFORE any pyagent module is imported.
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("BASE_URL", "https://example.com/v1")
os.environ.setdefault("MODEL", "test-model")
os.environ.setdefault("LOG_LEVEL", "warning")
_tmp = tempfile.mkdtemp(prefix="pyagent_test_")
os.environ.setdefault("DB_PATH", os.path.join(_tmp, "agent.db"))

from types import SimpleNamespace  # noqa: E402


class FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = SimpleNamespace(name=name, arguments=arguments)

    def model_dump(self):
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


def make_tool_call(id, name, arguments):
    return FakeToolCall(id, name, arguments)


def make_response(content=None, tool_calls=None, total_tokens=10):
    """Build a fake OpenAI chat completion response."""
    tc_list = tool_calls or None
    msg = SimpleNamespace(content=content, tool_calls=tc_list)

    def model_dump(exclude_none=True):
        d = {"role": "assistant"}
        if content is not None or not exclude_none:
            d["content"] = content
        if tc_list:
            d["tool_calls"] = [tc.model_dump() for tc in tc_list]
        if exclude_none:
            d = {k: v for k, v in d.items() if v is not None}
        return d

    msg.model_dump = model_dump
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(total_tokens=total_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)
