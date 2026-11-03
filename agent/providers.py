"""Provider failover. Tries primary, falls back on failure."""

import uuid

import openai


def create_client(base_url, api_key, session_id, user_agent="pyagent/0.1"):
    """Create an OpenAI-compatible client with required headers."""
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers={
            "x-opencode-session": session_id,
            "User-Agent": user_agent,
        },
    )


class ProviderChain:
    """Tries providers in order. Falls back on any exception."""

    def __init__(self, providers):
        # providers: list of dicts with keys: base_url, api_key, model, name
        self.providers = providers
        self.session_id = str(uuid.uuid4())
        self.last_provider = None

    def chat(self, messages, tools=None):
        last_error = None
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
        raise last_error
