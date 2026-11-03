"""Agent loop. Orchestrates LLM calls and tool execution."""

import json

import openai
import typer

from agent.config import API_KEY, BASE_URL, MAX_ITERATIONS, MODEL, validate
from tools.registry import TOOLS, execute_tool

validate()
client = openai.OpenAI(base_url=BASE_URL, api_key=API_KEY)


def run(prompt: str, verbose: bool = False):
    """Run the agent with a single prompt."""
    messages = [{"role": "user", "content": prompt}]

    for iteration in range(MAX_ITERATIONS):
        if verbose:
            print(f"[iteration {iteration + 1}]")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS if TOOLS else None,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump())

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
