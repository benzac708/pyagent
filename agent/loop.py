"""Agent loop. Orchestrates LLM calls and tool execution."""

import concurrent.futures
import json
import time
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


SYSTEM_PROMPT = (
    "You are a VPS triage agent. Your job is to diagnose VPS health issues and produce a JSON report.\n\n"
    "RULES:\n"
    "1. Call tools to gather information. Do not guess.\n"
    "2. After gathering enough information (max 3 tool calls), output your final answer as JSON.\n"
    "3. Do NOT explore files, read source code, or run unnecessary commands.\n"
    "4. Do NOT call more than 3 tools total across all iterations.\n"
    "5. Your final output MUST be valid JSON with these fields: status, findings, recommendations, verified.\n"
    "6. Set verified=true ONLY if you called check_health and it returned healthy.\n"
    "7. Be concise. Do not explain your reasoning in the output.\n\n"
    "TOOLS (use only these, in this order):\n"
    "- check_failed_services: lists failed systemd units. Call FIRST.\n"
    "- check_disk: disk usage for a path. Call if disk might be an issue.\n"
    "- check_backups: backup file age. Call if backups might be stale.\n"
    "- check_health: HTTP health check. Call to verify a fix.\n"
    "- restart_service: restart an allowlisted service (requires confirmed=true).\n\n"
    "DO NOT use: read_file, list_files, bash, edit_file, list_runs (unless specifically needed).\n\n"
    "OUTPUT FORMAT (JSON only, no markdown):\n"
    '{"status": "ok|warning|critical", "findings": ["..."], "recommendations": ["..."], "verified": true|false}\n'
)

MAX_TOOL_RESULT_CHARS = 1000
MAX_TOOL_CALLS = 3  # Hard limit on tool calls per run


def _run_loop(
    messages: list[dict[str, Any]],
    conv_id: str,
    verbose: bool = False,
    quiet: bool = False,
    tools_filter: Optional[list[str]] = None,
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
    events: list[dict[str, Any]] = []  # simple event log
    tool_call_count = 0  # Hard rail: track total tool calls
    tool_call_cache: dict[str, str] = {}  # Hard rail: deduplicate tool calls

    # Inject system prompt if not already present.
    if not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    log.info("run_started", conv_id=conv_id, prompt=str(messages[-1].get("content", ""))[:100])

    try:
        for iteration in range(MAX_ITERATIONS):
            iterations = iteration + 1
            # Forced convergence: tell LLM to stop exploring when running out of iterations.
            if iteration >= MAX_ITERATIONS - 2:
                messages.append(
                    {
                        "role": "user",
                        "content": "You have limited iterations remaining. "
                        "Output your final JSON answer NOW. Do not call more tools.",
                    }
                )
                save_message(conv_id, "user", content="Output your final JSON answer now.")

            # Hard rail: inject iteration budget into context.
            if iteration > 0:
                budget_msg = f"Iteration {iteration + 1} of {MAX_ITERATIONS}. "
                if tool_call_count >= MAX_TOOL_CALLS:
                    budget_msg += "Tool call budget exhausted. Output final JSON now."
                else:
                    budget_msg += f"Tool calls used: {tool_call_count}/{MAX_TOOL_CALLS}."
                messages.append({"role": "user", "content": budget_msg})
                save_message(conv_id, "user", content=budget_msg)

            if verbose:
                print(f"[iteration {iteration + 1}]")

            rf = RESPONSE_FORMAT.strip().lower()
            rf_arg = {"type": "json_object"} if rf == "json" else None
            # Hard rail: disable tools on last iterations or when budget exhausted.
            if tool_call_count >= MAX_TOOL_CALLS or iteration >= MAX_ITERATIONS - 1:
                available_tools = []
            elif tools_filter:
                available_tools = [t for t in TOOLS if t["function"]["name"] in tools_filter]
            else:
                available_tools = TOOLS
            response, provider_name = get_chain().chat(messages, available_tools, response_format=rf_arg)
            msg = response.choices[0].message
            total_tokens += response.usage.total_tokens if response.usage else 0
            # Event log: generation completed.
            events.append(
                {
                    "type": "generation_completed",
                    "provider": provider_name,
                    "tokens": response.usage.total_tokens if response.usage else 0,
                    "has_tool_calls": bool(msg.tool_calls),
                    "ts": time.time(),
                }
            )

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

            # Hard rail: check if we should execute tools or force convergence.
            should_execute = True
            if tool_call_count >= MAX_TOOL_CALLS:
                should_execute = False
            if iteration >= MAX_ITERATIONS - 1:
                should_execute = False

            if not should_execute:
                # Force convergence: don't execute tools, ask for final output.
                messages.append(
                    {
                        "role": "user",
                        "content": "Tool call budget exhausted. Output your final JSON answer now.",
                    }
                )
                save_message(conv_id, "user", content="Tool call budget exhausted. Output final JSON.")
                continue

            if msg.tool_calls:
                # Hard rail: if tool budget exhausted or on last iteration, force convergence.
                if tool_call_count >= MAX_TOOL_CALLS or iteration >= MAX_ITERATIONS - 1:
                    messages.append(
                        {
                            "role": "user",
                            "content": "You must output your final JSON answer now. Do not call more tools.",
                        }
                    )
                    save_message(conv_id, "user", content="Output your final JSON answer now.")
                    continue

                # Execute tool calls in parallel.
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(msg.tool_calls), 8)) as pool:
                    futures: list[tuple[Any, Optional[dict[str, Any]], Optional[str]]] = []
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
                    def _run(tc: Any, args: dict[str, Any]) -> str:
                        return execute_tool(tc.function.name, args)

                    future_map: dict[str, concurrent.futures.Future[str]] = {}
                    for tc, args, err in futures:
                        if args is None:
                            continue
                        # Hard rail: deduplicate tool calls.
                        cache_key = f"{tc.function.name}:{json.dumps(args, sort_keys=True)}"
                        if cache_key in tool_call_cache:
                            cached = tool_call_cache[cache_key]
                            messages.append({"role": "tool", "tool_call_id": tc.id, "content": cached})
                            save_message(conv_id, "tool", content=cached, tool_call_id=tc.id)
                            notes[tc.function.name] = cached[:500]
                            events.append(
                                {
                                    "type": "tool_completed",
                                    "tool": tc.function.name,
                                    "is_error": False,
                                    "ts": time.time(),
                                    "cached": True,
                                }
                            )
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
                            result = "Error: invalid tool arguments"
                            for t, a, err_val in futures:
                                if t.id == tc.id and err_val is not None:
                                    result = err_val
                                    break
                        if verbose:
                            print(f"  result: {str(result)[:200]}")
                        truncated = str(result)[:MAX_TOOL_RESULT_CHARS]
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": truncated})
                        save_message(conv_id, "tool", content=str(result), tool_call_id=tc.id)
                        # Hard rail: increment tool call counter.
                        tool_call_count += 1
                        # Hard rail: cache result for deduplication.
                        try:
                            cache_args = json.loads(tc.function.arguments or "{}")
                            cache_key = f"{tc.function.name}:{json.dumps(cache_args, sort_keys=True)}"
                            tool_call_cache[cache_key] = str(result)[:MAX_TOOL_RESULT_CHARS]
                        except (json.JSONDecodeError, TypeError):
                            pass
                        # Working memory: keep latest result per tool (truncated).
                        notes[tc.function.name] = str(result)[:500]
                        # Event log: tool completed.
                        events.append(
                            {
                                "type": "tool_completed",
                                "tool": tc.function.name,
                                "is_error": str(result).startswith("Error:"),
                                "ts": time.time(),
                            }
                        )

        else:
            status = "max_iterations"
            if not quiet:
                print(f"Warning: reached max iterations ({MAX_ITERATIONS})")
    except Exception as e:
        status = "error"
        error = str(e)
        if not quiet:
            print(f"Error: {e}")

    # Event log: agent completed.
    events.append(
        {
            "type": "agent_completed",
            "status": status,
            "iterations": iterations,
            "total_tokens": total_tokens,
            "ts": time.time(),
        }
    )
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
                events=events,
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
        events=len(events),
    )

    # Hard rail: guaranteed fallback response (never return null).
    if final_content is None:
        # Construct fallback from notes and events.
        findings = []
        for tool_name, result in notes.items():
            findings.append(f"{tool_name}: {result[:200]}")
        if not findings:
            findings = ["No findings  -  agent did not produce output."]
        fallback = {
            "status": "unknown",
            "findings": findings,
            "recommendations": ["Manual review required."],
            "verified": False,
        }
        final_content = json.dumps(fallback)
        status = "completed" if status != "error" else status
        log.warning("fallback_response_generated", run_id=run_id, reason="no_valid_json")

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
        "events": events,
    }


TRIAGE_TOOLS = [
    "check_failed_services",
    "check_disk",
    "check_backups",
    "check_health",
    "restart_service",
    "check_services",
]


def run(
    prompt: str,
    verbose: bool = False,
    conv_id: Optional[str] = None,
    quiet: bool = False,
    tools_filter: Optional[list[str]] = None,
    all_tools: bool = False,
) -> dict[str, Any]:
    """Run the agent with a single prompt. Returns a result dict."""
    if conv_id is None:
        conv_id = str(uuid.uuid4())[:8]
    init_db()
    create_conversation(conv_id)
    save_message(conv_id, "user", content=prompt)
    messages = [{"role": "user", "content": prompt}]
    # Hard rail: default to triage tools unless all_tools requested.
    if tools_filter is None and not all_tools:
        tools_filter = TRIAGE_TOOLS
    return _run_loop(messages, conv_id, verbose=verbose, quiet=quiet, tools_filter=tools_filter)


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
