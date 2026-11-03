"""Agent loop. Orchestrates LLM calls and tool execution."""

import json

import typer

from agent.config import (
    API_KEY,
    BASE_URL,
    FALLBACK_API_KEY,
    FALLBACK_BASE_URL,
    FALLBACK_MODEL,
    MAX_ITERATIONS,
    MODEL,
    has_fallback,
    validate,
)
from agent.providers import ProviderChain
from tools.registry import TOOLS, execute_tool

validate()

# Build provider list: primary + optional fallback
providers = [{"base_url": BASE_URL, "api_key": API_KEY, "model": MODEL, "name": "primary"}]
if has_fallback():
    providers.append(
        {
            "base_url": FALLBACK_BASE_URL,
            "api_key": FALLBACK_API_KEY,
            "model": FALLBACK_MODEL,
            "name": "fallback (groq)",
        }
    )

chain = ProviderChain(providers)


def run(prompt: str, verbose: bool = False):
    """Run the agent with a single prompt."""
    messages = [{"role": "user", "content": prompt}]

    for iteration in range(MAX_ITERATIONS):
        if verbose:
            print(f"[iteration {iteration + 1}]")

        response, provider_name = chain.chat(messages, TOOLS)
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if verbose:
            print(f"  provider: {provider_name}")

        # No tool calls = agent is done
        if not msg.tool_calls:
            print(msg.content)
            return

        # Execute each tool call
        for tc in msg.tool_calls:
            if verbose:
                print(f"  tool: {tc.function.name}({tc.function.arguments})")
            args = json.loads(tc.function.arguments)
            result = execute_tool(tc.function.name, args)
            if verbose:
                print(f"  result: {result[:200]}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    print(f"Warning: reached max iterations ({MAX_ITERATIONS})")


def main(prompt: str, verbose: bool = False):
    run(prompt, verbose)


if __name__ == "__main__":
    typer.run(main)
