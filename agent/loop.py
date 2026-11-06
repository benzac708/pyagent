"""Agent loop. Orchestrates LLM calls and tool execution."""

import concurrent.futures
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import typer

from agent.config import (
    API_KEY,
    BASE_URL,
    FALLBACK_API_KEY,
    FALLBACK_BASE_URL,
    FALLBACK_MODEL,
    MAX_ITERATIONS,
    MAX_OUTPUT_RETRIES,
    MAX_TOKENS,
    MODEL,
    RESPONSE_FORMAT,
    has_fallback,
    log,
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

VERIFICATION_TOOLS = {"check_health"}

chain = None


def get_chain() -> Any:
    """Lazily build (and cache) the provider chain."""
    global chain
    if chain is None:
        validate()
        init_db()
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
    return chain


def _run_loop(
    messages: list[dict[str, Any]],
    conv_id: str,
    verbose: bool = False,
    quiet: bool = False,
) -> dict[str, Any]:
    """Shared execution loop used by run() and resume. Returns a result dict."""
    run_id = str(uuid.uuid4())[:8]
    iterations = 0
    total_tokens = 0
    status = "completed"
    error = None
    provider_name = None
    final_content = None
    saved = False
    output_retries = 0
    verified_called = False
    started_at = datetime.now(timezone.utc).isoformat()
    notes: dict[str, Any] = {}  # working memory: latest result per tool

    log.info("run_started", conv_id=conv_id, prompt=str(messages[-1].get("content", ""))[:100])

    try:
        for iteration in range(MAX_ITERATIONS):
            iterations = iteration + 1
            if verbose:
                print(f"[iteration {iteration + 1}]")

            rf = RESPONSE_FORMAT.strip().lower()
            rf_arg = {"type": "json_object"} if rf == "json" else None
            response, provider_name = get_chain().chat(messages, TOOLS, response_format=rf_arg)
            msg = response.choices[0].message
            total_tokens += response.usage.total_tokens if response.usage else 0

            if total_tokens > MAX_TOKENS:
                status = "max_tokens"
                if not quiet:
                    print(f"Warning: reached token budget ({MAX_TOKENS})")
                break

            rf = RESPONSE_FORMAT.strip().lower()
            if rf == "json" and not msg.tool_calls and msg.content:
                try:
                    parsed = json.loads(msg.content)
                    ok = (
                        isinstance(parsed, dict)
                        and "status" in parsed
                        and "findings" in parsed
                        and "recommendations" in parsed
                        and "verified" in parsed
                        and isinstance(parsed.get("verified"), bool)
                    )
                    if not ok:
                        raise ValueError("missing required keys")
                    if parsed.get("verified") is True and not verified_called:
                        raise ValueError("claimed verified without calling a verification tool")
                except (json.JSONDecodeError, ValueError):
                    if output_retries < MAX_OUTPUT_RETRIES:
                        output_retries += 1
                        msg_text = (
                            "Your previous output was not valid JSON matching the schema "
                            "{status, findings[], recommendations[], verified}. Output only valid JSON, no markdown."
                        )
                        messages.append({"role": "user", "content": msg_text})
                        save_message(conv_id, "user", content="Output correction: valid JSON only.")
                        continue
                    status = "error"
                    error = "invalid JSON output after retries"
                    if not quiet:
                        print(f"Error: {error}")
                    break

            messages.append(msg.model_dump(exclude_none=True))
            save_message(
                conv_id,
                "assistant",
                content=msg.content,
                tool_calls=[tc.model_dump() for tc in msg.tool_calls] if msg.tool_calls else None,
            )

            if verbose:
                print(f"  provider: {provider_name}")

            if not msg.tool_calls:
                final_content = msg.content
                if not quiet and msg.content:
                    print(msg.content)
                break

            # Execute tool calls in parallel (read-only tools can run concurrently).
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(msg.tool_calls), 8)) as pool:
                futures = []
                for tc in msg.tool_calls:
                    if verbose:
                        print(f"  tool: {tc.function.name}({tc.function.arguments})")
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except (json.JSONDecodeError, TypeError) as e:
                        args = None
                        err_result = f"Error: invalid tool arguments: {e}"
                        futures.append((tc, None, err_result))
                        continue
                    if tc.function.name in VERIFICATION_TOOLS:
                        verified_called = True
                    futures.append((tc, args, None))

                # Run valid tools in parallel.
                def _run(tc, args):
                    return execute_tool(tc.function.name, args)

                future_map = {}
                for tc, args, err in futures:
                    if args is None and err is not None:
                        continue
                    future_map[tc.id] = pool.submit(_run, tc, args)

                # Collect results in original order.
                for tc in msg.tool_calls:
                    if tc.id in future_map:
                        try:
                            result = future_map[tc.id].result()
                        except Exception as e:
                            result = f"Error: {e}"
                    else:
                        # Invalid args case: find the error result.
                        result = "Error: invalid tool arguments"
                        for t, a, e in futures:
                            if t.id == tc.id and e is not None:
                                result = e
                                break
                    if verbose:
                        print(f"  result: {str(result)[:200]}")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
                    save_message(conv_id, "tool", content=str(result), tool_call_id=tc.id)
                    # Working memory: keep latest result per tool (truncated).
                    notes[tc.function.name] = str(result)[:500]
        else:
            status = "max_iterations"
            if not quiet:
                print(f"Warning: reached max iterations ({MAX_ITERATIONS})")
    except Exception as e:
        status = "error"
        error = str(e)
        if not quiet:
            print(f"Error: {e}")

    if not saved:
        try:
            save_run(
                run_id,
                conv_id,
                provider_name,
                iterations,
                total_tokens,
                status,
                error,
                started_at=started_at,
                notes=notes,
            )
            saved = True
        except Exception:
            pass

    log.info(
        "run_finished",
        run_id=run_id,
        conv_id=conv_id,
        provider=provider_name,
        iterations=iterations,
        total_tokens=total_tokens,
        status=status,
        notes=list(notes.keys()),
    )

    if verbose and not quiet:
        print(
            f"\n[run] id={run_id} conv={conv_id} provider={provider_name} "
            f"iterations={iterations} tokens={total_tokens} status={status}"
        )

    return {
        "run_id": run_id,
        "conv_id": conv_id,
        "provider": provider_name,
        "iterations": iterations,
        "total_tokens": total_tokens,
        "status": status,
        "error": error,
        "response": final_content,
        "notes": notes,
    }


def run(prompt: str, verbose: bool = False, conv_id: Optional[str] = None, quiet: bool = False) -> dict[str, Any]:
    """Run the agent with a single prompt. Returns a result dict."""
    if conv_id is None:
        conv_id = str(uuid.uuid4())[:8]
    init_db()
    create_conversation(conv_id)
    save_message(conv_id, "user", content=prompt)
    messages = [{"role": "user", "content": prompt}]
    return _run_loop(messages, conv_id, verbose=verbose, quiet=quiet)


def main(
    prompt: str,
    verbose: bool = False,
    resume: Optional[str] = None,
    quiet: bool = False,
) -> Optional[dict[str, Any]]:
    init_db()
    if resume:
        prev = get_conversation_messages(resume)
        if not prev:
            print(f"No conversation found: {resume}")
            return None
        print(f"Resuming conversation {resume} ({len(prev)} messages)")
        save_message(resume, "user", content=prompt)
        messages = prev + [{"role": "user", "content": prompt}]
        return _run_loop(messages, resume, verbose=verbose, quiet=quiet)
    return run(prompt, verbose=verbose, quiet=quiet)


if __name__ == "__main__":
    typer.run(main)
