"""Agent loop. Orchestrates LLM calls and tool execution."""

import json
import uuid

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
from agent.db import (
    create_conversation,
    get_conversation_messages,
    init_db,
    save_message,
    save_run,
)
from agent.providers import ProviderChain
from tools.registry import TOOLS, execute_tool

validate()
init_db()

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


def run(prompt: str, verbose: bool = False, conv_id: str = None):
    """Run the agent with a single prompt."""
    if conv_id is None:
        conv_id = str(uuid.uuid4())[:8]
    create_conversation(conv_id)

    save_message(conv_id, "user", content=prompt)
    messages = [{"role": "user", "content": prompt}]

    run_id = str(uuid.uuid4())[:8]
    iterations = 0
    total_tokens = 0
    status = "completed"
    error = None
    provider_name = None

    try:
        for iteration in range(MAX_ITERATIONS):
            iterations = iteration + 1
            if verbose:
                print(f"[iteration {iteration + 1}]")

            response, provider_name = chain.chat(messages, TOOLS)
            msg = response.choices[0].message
            total_tokens += response.usage.total_tokens if response.usage else 0

            messages.append(msg.model_dump(exclude_none=True))
            save_message(
                conv_id,
                "assistant",
                content=msg.content,
                tool_calls=[tc.model_dump() for tc in msg.tool_calls] if msg.tool_calls else None,
            )

            if verbose:
                print(f"  provider: {provider_name}")

            # No tool calls = agent is done
            if not msg.tool_calls:
                print(msg.content)
                break

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
                save_message(conv_id, "tool", content=result, tool_call_id=tc.id)

        else:
            # Hit max iterations without break
            status = "max_iterations"
            print(f"Warning: reached max iterations ({MAX_ITERATIONS})")

    except Exception as e:
        status = "error"
        error = str(e)
        print(f"Error: {e}")

    save_run(run_id, conv_id, provider_name, iterations, total_tokens, status, error)

    if verbose:
        print(
            f"\n[run] id={run_id} conv={conv_id} provider={provider_name} "
            f"iterations={iterations} tokens={total_tokens} status={status}"
        )


def main(prompt: str, verbose: bool = False, resume: str = None):
    if resume:
        prev = get_conversation_messages(resume)
        if not prev:
            print(f"No conversation found: {resume}")
            return
        print(f"Resuming conversation {resume} ({len(prev)} messages)")
        # Append new prompt and run with existing conv_id
        save_message(resume, "user", content=prompt)
        messages = prev + [{"role": "user", "content": prompt}]
        # Run inline with existing messages
        run_id = str(uuid.uuid4())[:8]
        iterations = 0
        total_tokens = 0
        status = "completed"
        error = None
        provider_name = None

        try:
            for iteration in range(MAX_ITERATIONS):
                iterations = iteration + 1
                if verbose:
                    print(f"[iteration {iteration + 1}]")
                response, provider_name = chain.chat(messages, TOOLS)
                msg = response.choices[0].message
                total_tokens += response.usage.total_tokens if response.usage else 0
                messages.append(msg.model_dump(exclude_none=True))
                save_message(
                    resume,
                    "assistant",
                    content=msg.content,
                    tool_calls=[tc.model_dump() for tc in msg.tool_calls] if msg.tool_calls else None,
                )
                if not msg.tool_calls:
                    print(msg.content)
                    break
                for tc in msg.tool_calls:
                    if verbose:
                        print(f"  tool: {tc.function.name}({tc.function.arguments})")
                    args = json.loads(tc.function.arguments)
                    result = execute_tool(tc.function.name, args)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                    save_message(resume, "tool", content=result, tool_call_id=tc.id)
            else:
                status = "max_iterations"
                print(f"Warning: reached max iterations ({MAX_ITERATIONS})")
        except Exception as e:
            status = "error"
            error = str(e)
            print(f"Error: {e}")

        save_run(run_id, resume, provider_name, iterations, total_tokens, status, error)
        if verbose:
            print(
                f"\n[run] id={run_id} conv={resume} provider={provider_name} "
                f"iterations={iterations} tokens={total_tokens} status={status}"
            )
    else:
        run(prompt, verbose)


if __name__ == "__main__":
    typer.run(main)
