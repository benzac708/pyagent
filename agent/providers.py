"""Provider failover. Tries primary, falls back on failure."""

import os
import uuid
from typing import Any, Optional

import openai


def _mock_response(messages: list[Any], tools: Optional[list[Any]] = None) -> tuple[Any, str]:
    """Return a canned OpenAI-compatible response for demo/mock mode."""
    from types import SimpleNamespace

    last = messages[-1] if messages else {}
    prompt = str(last.get("content", ""))

    # Demo the tool path when the prompt asks to read fizzbuzz.js.
    if tools and "read" in prompt.lower() and "fizzbuzz" in prompt.lower():
        tc = SimpleNamespace(
            id="mock-tc-1",
            function=SimpleNamespace(name="read_file", arguments='{"path": "fizzbuzz.js"}'),
        )

        def tc_dump() -> dict[str, Any]:
            return {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }

        tc.model_dump = tc_dump
        msg = SimpleNamespace(content=None, tool_calls=[tc])

        def msg_dump(exclude_none: bool = True) -> dict[str, Any]:
            return {"role": "assistant", "tool_calls": [tc.model_dump()]}

        msg.model_dump = msg_dump
        choice = SimpleNamespace(message=msg)
        usage = SimpleNamespace(total_tokens=10)
        return SimpleNamespace(choices=[choice], usage=usage), "mock"

    content = (
        "This is a mock response (MOCK_LLM=true). "
        "In real mode I would call the LLM and any tools needed. "
        f"You said: {prompt[:120]}"
    )
    msg = SimpleNamespace(content=content, tool_calls=None)

    def model_dump(exclude_none: bool = True) -> dict[str, Any]:
        return {"role": "assistant", "content": content}

    msg.model_dump = model_dump
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(total_tokens=42)
    return SimpleNamespace(choices=[choice], usage=usage), "mock"


def create_client(base_url: str, api_key: str, session_id: str, user_agent: str = "pyagent/0.7.0") -> Any:
    """Create an OpenAI-compatible client with required headers."""
    headers = {"User-Agent": user_agent}
    # OpenCode Go requires a session header; don't leak it to other providers.
    if "opencode" in (base_url or "").lower():
        headers["x-opencode-session"] = session_id
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers=headers,
        timeout=60.0,
    )


class ProviderChain:
    """Tries providers in order. Falls back on any exception."""

    def __init__(self, providers: list[dict[str, Any]]) -> None:
        self.providers = providers
        self.session_id = str(uuid.uuid4())
        self.last_provider: Optional[str] = None

    def chat(
        self,
        messages: list[Any],
        tools: Optional[list[Any]] = None,
        response_format: Optional[dict[str, Any]] = None,
    ) -> tuple[Any, str]:
        if os.getenv("MOCK_LLM", "").lower() in ("1", "true", "yes"):
            self.last_provider = "mock"
            return _mock_response(messages, tools)
        last_error: Optional[Exception] = None
        for p in self.providers:
            try:
                client = create_client(p["base_url"], p["api_key"], self.session_id)
                kwargs: dict[str, Any] = {
                    "model": p["model"],
                    "messages": messages,
                    "tools": tools if tools else None,
                }
                if response_format:
                    kwargs["response_format"] = response_format
                response = client.chat.completions.create(**kwargs)
                self.last_provider = p["name"]
                return response, p["name"]
            except Exception as e:
                last_error = e
                print(f"[provider] {p['name']} failed: {e}")
                print("[provider] trying next...")
                continue
        if last_error is not None:
            raise last_error
        raise RuntimeError("no providers configured")
