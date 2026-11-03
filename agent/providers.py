"""Provider failover. Tries primary, falls back on failure."""

import os
import uuid
from typing import Any, Optional

import openai


def _mock_response(messages: list[Any], tools: Optional[list[Any]] = None) -> tuple[Any, str]:
    """Return a canned OpenAI-compatible response for demo/mock mode."""
    from types import SimpleNamespace

    last = messages[-1] if messages else {}
    content = (
        "This is a mock response (MOCK_LLM=true). "
        "In real mode I would call the LLM and any tools needed. "
        f"You said: {str(last.get('content', ''))[:120]}"
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
    )


class ProviderChain:
    """Tries providers in order. Falls back on any exception."""

    def __init__(self, providers: list[dict[str, Any]]) -> None:
        # providers: list of dicts with keys: base_url, api_key, model, name
        self.providers = providers
        self.session_id = str(uuid.uuid4())
        self.last_provider: Optional[str] = None

    def chat(self, messages: list[Any], tools: Optional[list[Any]] = None) -> tuple[Any, str]:
        if os.getenv("MOCK_LLM", "").lower() in ("1", "true", "yes"):
            self.last_provider = "mock"
            return _mock_response(messages, tools)
        last_error: Optional[Exception] = None
        for p in self.providers:
            try:
                client = create_client(p["base_url"], p["api_key"], self.session_id)
                response = client.chat.completions.create(
                    model=p["model"],
                    messages=messages,
                    tools=tools if tools else None,
                )
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
