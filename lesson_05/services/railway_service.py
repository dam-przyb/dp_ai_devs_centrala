"""
railway_service.py — Railway X-01 Activation Agent.

Activates railway route X-01 via a self-documenting API at hub.ag3nts.org.

Architecture
------------
A background daemon thread runs a LangGraph Supervisor + Manual-ReAct worker:

    START → railway_worker_node → supervisor_node ──► END
                  ▲                     │ (no flag yet, round cap not reached)
                  └─────────────────────┘

The agent begins by calling action="help" to receive the live API documentation,
then follows the returned instructions step-by-step until it captures {FLG:...}.

Resilience mechanisms
---------------------
- 503 retry: exponential back-off (2 → 4 → 8 … s, capped at 120 s)
- Rate-limit headers: Retry-After / X-RateLimit-Remaining / X-RateLimit-Reset-After
- Supervisor round cap: MAX_SUPERVISOR_ROUNDS prevents infinite loops

Live logging
------------
Every API call, response, retry, and agent decision is appended to an
in-memory task store entry (keyed by task_id).  The SSE stream view polls
this store and pushes events to the browser in real time.
At task completion, log.json and answer.json are saved to 0105task_context/.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

import httpx
from django.conf import settings
from langchain.tools import tool
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Preferred model: strong reasoning with minimal steps conserves rate-limit quota.
RAILWAY_MODEL = "google/gemini-3.1-pro-preview"

TASK_NAME = "railway"
HUB_URL = "https://hub.ag3nts.org/verify"

# Supervisor loop cap — prevents infinite cycles if the flag is never returned.
MAX_SUPERVISOR_ROUNDS = 12

# Per-round tool-call cap — stops the ReAct loop if the LLM never produces
# a final answer (no tool calls) within a single supervisor iteration.
MAX_WORKER_ITERATIONS = 25

# Hard ceiling on rate-limit sleep (seconds).
# x-ratelimit-reset-after can be an absolute Unix timestamp — without a cap
# the sleep duration becomes decades.  Retry-After (24 s) is always honoured
# first; this cap is the safety net for any other header variant.
MAX_RATE_LIMIT_WAIT_S = 120

# 503 retry back-off: 2 s → 4 s → 8 s … capped at 120 s.
MAX_503_RETRIES = 8
INITIAL_BACKOFF_S = 2

# SSE generator poll interval in seconds.
SSE_POLL_INTERVAL_S = 0.3

_ANSWER_DIR = Path(__file__).resolve().parent.parent / "0105task_context"

# Pattern used to locate the flag in any message content.
_FLAG_RE = re.compile(r"\{FLG:[^}]+\}")


# =============================================================================
# In-Memory Task Store
# =============================================================================
# CPython's GIL makes list.append and dict key assignment effectively atomic,
# so a plain dict is sufficient for our single-writer / single-reader pattern
# (one background agent thread writes; one SSE request thread reads).

_task_store: dict[str, dict[str, Any]] = {}


def _ts() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _append_log(
    task_id: str,
    type_: str,
    message: str,
    detail: dict | None = None,
) -> None:
    """
    Append a structured log entry to the task store.

    Args:
        task_id: Running task identifier (key into _task_store).
        type_:   Entry category used by the UI for colour-coding:
                 agent_step | api_call | api_response | retry_503 |
                 rate_limit | flag | error | done.
        message: One-line human-readable summary shown in the timeline.
        detail:  Optional full-detail dict for the expandable panel.
    """
    entry: dict[str, Any] = {
        "type":      type_,
        "timestamp": _ts(),
        "message":   message,
        "detail":    detail or {},
    }
    store = _task_store.get(task_id)
    if store is not None:
        store["log"].append(entry)


# =============================================================================
# Thread-Local Task ID
# =============================================================================
# The @tool function cannot receive task_id as an LLM-visible parameter, so
# we bind it to a threading.local() variable at the start of each worker node
# invocation.  Since each agent run executes in its own daemon thread, there
# is no cross-task interference.

_thread_local = threading.local()


def _current_task_id() -> str:
    """Return the task_id bound to the current background thread."""
    return getattr(_thread_local, "task_id", "unknown")


# =============================================================================
# Low-Level HTTP — 503 Retry + Rate-Limit Handling
# =============================================================================

def _call_hub(payload: dict, *, timeout: int = 60) -> tuple[int, Any, dict]:
    """
    POST payload to HUB_URL with automatic 503 retry and rate-limit sleep.

    503 responses are a deliberate simulation of server overload and are NOT
    real failures — they must be retried.  After each non-503 response,
    *_handle_rate_limit* is called to honour any quota headers.

    Args:
        payload: Complete JSON body (apikey, task, answer).
        timeout: Per-request HTTP timeout in seconds.

    Returns:
        Tuple of (status_code, parsed_response_body, response_headers_dict).

    Raises:
        RuntimeError: If 503 persists through all MAX_503_RETRIES attempts,
                      or if a network-level error occurs.
    """
    task_id = _current_task_id()
    action = payload.get("answer", {}).get("action", "unknown")
    backoff = INITIAL_BACKOFF_S

    for attempt in range(1, MAX_503_RETRIES + 1):
        _append_log(
            task_id,
            "api_call",
            f"→ API request: action={action}",
            {"url": HUB_URL, "payload": payload, "attempt": attempt},
        )

        try:
            resp = httpx.post(HUB_URL, json=payload, timeout=timeout)
        except Exception as exc:
            _append_log(task_id, "error", f"Network error: {exc}", {"exc": str(exc)})
            raise RuntimeError(f"HTTP request failed: {exc}") from exc

        headers = dict(resp.headers)
        status  = resp.status_code

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        if status == 503:
            # Respect Retry-After header if present; otherwise use back-off.
            retry_after_raw = headers.get("retry-after") or headers.get("Retry-After")
            wait_s = backoff
            if retry_after_raw:
                try:
                    wait_s = max(int(retry_after_raw), backoff)
                except (ValueError, TypeError):
                    pass

            if attempt >= MAX_503_RETRIES:
                _append_log(
                    task_id,
                    "error",
                    f"503 persisted after {MAX_503_RETRIES} retries — giving up for action={action}",
                )
                raise RuntimeError(f"503 persisted after {MAX_503_RETRIES} retries")

            _append_log(
                task_id,
                "retry_503",
                f"⚠ 503 received — retrying in {wait_s}s  (attempt {attempt}/{MAX_503_RETRIES})",
                {"attempt": attempt, "wait_s": wait_s, "headers": headers, "body": body},
            )
            time.sleep(wait_s)
            # Double the back-off for the next attempt, cap at 120 s.
            backoff = min(backoff * 2, 120)
            continue

        # Non-503: honour rate-limit headers before returning to the caller.
        _handle_rate_limit(headers, task_id=task_id)

        _append_log(
            task_id,
            "api_response",
            f"← HTTP {status}",
            {"status_code": status, "body": body, "headers": headers},
        )
        return status, body, headers

    raise RuntimeError("Exhausted all 503 retries")


def _handle_rate_limit(headers: dict, *, task_id: str) -> None:
    """
    Inspect rate-limit response headers and sleep if the quota is exhausted.

    Header resolution priority (all keys normalised to lower-case):
      1. ``retry-after``              — standard HTTP header, value is *seconds to wait*.
      2. ``x-ratelimit-reset-after``  — may be an absolute Unix timestamp **or** seconds.
         When the raw value exceeds 3 600 (one hour) it is treated as a Unix timestamp
         and ``wait = value - time.time()`` is computed.  Otherwise it is treated as
         a duration in seconds.
      3. ``x-ratelimit-reset``        — same heuristic as above.
      4. Conservative fallback of 5 s when remaining==0 but no timing header present.

    A hard cap of MAX_RATE_LIMIT_WAIT_S is applied after all calculations.
    This prevents the pathological case where ``x-ratelimit-reset-after`` is a
    distant Unix timestamp (e.g. 1 775 333 535) that would otherwise cause a
    multi-year sleep.

    Args:
        headers: Raw response headers dict from httpx.
        task_id: Used for logging the wait event.
    """
    h = {k.lower(): v for k, v in headers.items()}
    remaining   = h.get("x-ratelimit-remaining")
    reset_after = h.get("x-ratelimit-reset-after") or h.get("x-ratelimit-reset")
    retry_after = h.get("retry-after")

    wait_s: float = 0.0

    def _parse_reset(raw: str) -> float:
        """
        Parse a reset header value into *seconds to wait*.

        Values larger than 3 600 are assumed to be absolute Unix timestamps;
        smaller values are treated as durations in seconds.
        """
        val = float(raw)
        if val > 3_600:
            # Absolute Unix timestamp — compute delta from now.
            delta = val - time.time()
            return max(delta, 0.0)
        return val

    quota_exhausted = False
    if remaining is not None:
        try:
            quota_exhausted = int(str(remaining).split(".")[0]) <= 0
        except (ValueError, TypeError):
            pass

    if quota_exhausted or remaining is None:
        # Priority 1: Retry-After — standard HTTP, always in seconds.
        if retry_after:
            try:
                wait_s = max(wait_s, float(retry_after))
            except (ValueError, TypeError):
                pass

        # Priority 2: x-ratelimit-reset-after / x-ratelimit-reset.
        # Only use if Retry-After didn't already give us a value.
        if not wait_s and reset_after:
            try:
                wait_s = max(wait_s, _parse_reset(str(reset_after)))
            except (ValueError, TypeError):
                pass

        # Priority 3: conservative fallback when quota is exhausted but no
        # useful timing header was found.
        if quota_exhausted and not wait_s:
            wait_s = 5.0

    # Hard cap — no sleep should ever exceed MAX_RATE_LIMIT_WAIT_S regardless
    # of what the headers say.
    wait_s = min(wait_s, MAX_RATE_LIMIT_WAIT_S)

    if wait_s > 0:
        _append_log(
            task_id,
            "rate_limit",
            f"⏳ Rate limit — waiting {wait_s:.1f}s  "
            f"(remaining={remaining}, retry_after={retry_after}, reset_after={reset_after})",
            {
                "wait_s":       wait_s,
                "remaining":    remaining,
                "reset_after":  reset_after,
                "retry_after":  retry_after,
            },
        )
        time.sleep(wait_s)


# =============================================================================
# LangChain Tool
# =============================================================================

@tool
def call_railway_api(action: str, params: dict | None = None) -> str:
    """
    Call the railway hub API at hub.ag3nts.org.

    IMPORTANT: Always start with action='help' to receive the official API
    documentation before calling any other action.  Never invent action names
    or parameter names — use only what the help response documents.

    Args:
        action: The API action name (e.g. 'help').
        params: Optional dict of additional parameters for the action.

    Returns:
        JSON string of the API response body.
    """
    task_id = _current_task_id()
    api_key = getattr(settings, "AIDEVS_API_KEY", "")
    if not api_key:
        raise RuntimeError("AIDEVS_API_KEY is not configured in settings.")

    extra: dict[str, Any] = params or {}

    # Build the full answer payload; action always comes first.
    answer: dict[str, Any] = {"action": action, **extra}
    payload = {"apikey": api_key, "task": TASK_NAME, "answer": answer}

    _append_log(
        task_id,
        "agent_step",
        f"Tool invoked: action={action}" + (f"  params={extra}" if extra else ""),
    )

    _, body, _ = _call_hub(payload)
    return json.dumps(body, ensure_ascii=False)


# =============================================================================
# LangGraph State
# =============================================================================

class RailwayState(TypedDict):
    """
    Shared mutable state for the Railway activation graph.

    Attributes:
        messages:          Full conversation history passed between nodes.
        flag:              Captured {FLG:...} string once found; None before.
        supervisor_rounds: Number of completed supervisor iterations.
        task_id:           References the in-memory task store for logging.
    """

    messages:          list
    flag:              str | None
    supervisor_rounds: int
    task_id:           str


# =============================================================================
# System Prompt
# =============================================================================

_WORKER_SYSTEM_PROMPT = """\
You are a precise API automation agent. Your mission: activate railway route X-01.

STRICT RULES
1. Begin by calling call_railway_api(action="help") — this returns the official documentation.
2. Read the documentation carefully.
3. Use ONLY the exact action names and parameter names that the help response documents.
4. Never guess or invent action names or parameter names.
5. After each API call, read the response and determine the next required step.
6. When any API response contains a pattern like {FLG:...}, that is the success flag.
   Report it as your FINAL ANSWER immediately.
7. If an action fails, the error message usually tells you exactly what went wrong.

Always call help first — the API is fully self-documenting."""


# =============================================================================
# LLM Helper
# =============================================================================

def _get_llm(model: str) -> ChatOpenAI:
    """Return a ChatOpenAI client pointing at OpenRouter with the specified model."""
    return ChatOpenAI(
        model=model,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )


# =============================================================================
# Graph Nodes
# =============================================================================

def railway_worker_node(state: RailwayState) -> dict:
    """
    Manual ReAct tool-calling loop for the railway agent.

    Binds the current task_id to thread-local storage so call_railway_api
    can log against the correct task without receiving task_id as an LLM
    parameter.  Runs the LLM → tool-call → ToolMessage cycle until either:
      • the LLM produces an AIMessage with no tool calls (final answer), or
      • MAX_WORKER_ITERATIONS is reached.

    Args:
        state: Current graph state.

    Returns:
        Partial state update with the full updated messages list.
    """
    # Set task_id for the tool's thread-local logger before any LLM call.
    _thread_local.task_id = state["task_id"]
    task_id = state["task_id"]

    # Resolve model from the task store; fall back to the module default.
    model = _task_store.get(task_id, {}).get("model", RAILWAY_MODEL)
    llm = _get_llm(model)
    llm_with_tools = llm.bind_tools([call_railway_api])
    tools_by_name: dict[str, Any] = {call_railway_api.name: call_railway_api}

    messages = list(state["messages"])
    round_num = state["supervisor_rounds"] + 1

    _append_log(
        task_id,
        "agent_step",
        f"Worker started — supervisor round {round_num}/{MAX_SUPERVISOR_ROUNDS}",
    )

    for iteration in range(1, MAX_WORKER_ITERATIONS + 1):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # No tool calls → LLM produced its final answer for this round.
        if not response.tool_calls:
            _append_log(
                task_id,
                "agent_step",
                f"Worker final answer (iteration {iteration})",
                {"content_preview": str(response.content)[:500]},
            )
            break

        # Process each tool call requested by the LLM.
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})

            if tool_name not in tools_by_name:
                result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})
            else:
                try:
                    result_str = tools_by_name[tool_name].invoke(tool_args)
                except Exception as exc:
                    result_str = json.dumps({"error": str(exc)})
                    _append_log(
                        task_id,
                        "error",
                        f"Tool execution error: {exc}",
                        {"tool": tool_name, "args": tool_args},
                    )

            messages.append(
                ToolMessage(
                    content=result_str,
                    tool_call_id=tc["id"],
                    name=tool_name,
                )
            )
    else:
        # Loop exhausted without a break — log and let supervisor handle it.
        _append_log(
            task_id,
            "agent_step",
            f"Worker reached MAX_WORKER_ITERATIONS ({MAX_WORKER_ITERATIONS}) — "
            "handing off to supervisor",
        )

    return {"messages": messages}


def supervisor_node(state: RailwayState) -> dict:
    """
    Inspect worker output for the success flag and route the graph accordingly.

    Scans all messages in reverse order for the {FLG:...} pattern.
    - Flag found        → store it, route to END.
    - Round cap reached → log error, route to END.
    - Otherwise         → append a nudge HumanMessage, increment round, loop.

    Args:
        state: Current graph state.

    Returns:
        Partial state update: flag + supervisor_rounds, and optionally
        augmented messages (nudge appended when looping).
    """
    task_id = state["task_id"]
    rounds  = state["supervisor_rounds"] + 1

    # Search all messages (newest first) for a flag pattern.
    flag: str | None = None
    for msg in reversed(state["messages"]):
        content = getattr(msg, "content", "") or ""
        if isinstance(content, str):
            match = _FLAG_RE.search(content)
            if match:
                flag = match.group(0)
                break

    if flag:
        _append_log(
            task_id,
            "flag",
            f"🚩 FLAG CAPTURED: {flag}",
            {"flag": flag},
        )
        return {"flag": flag, "supervisor_rounds": rounds}

    if rounds >= MAX_SUPERVISOR_ROUNDS:
        _append_log(
            task_id,
            "error",
            f"Supervisor cap reached ({MAX_SUPERVISOR_ROUNDS} rounds) — terminating.",
        )
        return {"supervisor_rounds": rounds}

    # No flag yet — inject a nudge so the worker knowsits progress and goal.
    nudge = HumanMessage(
        content=(
            f"Round {rounds}/{MAX_SUPERVISOR_ROUNDS}: the flag was not found yet.  "
            "Continue following the API documentation.  "
            "When any response contains {FLG:...}, report it as your final answer."
        )
    )
    _append_log(
        task_id,
        "agent_step",
        f"Supervisor: no flag after round {rounds} — nudging worker to continue",
    )
    return {
        "messages":          state["messages"] + [nudge],
        "supervisor_rounds": rounds,
    }


def _should_continue(state: RailwayState) -> str:
    """
    Conditional edge from supervisor_node.

    Returns:
        "railway_worker" to keep looping, or END to finish.
    """
    if state.get("flag"):
        return END
    if state["supervisor_rounds"] >= MAX_SUPERVISOR_ROUNDS:
        return END
    return "railway_worker"


# =============================================================================
# Graph Builder
# =============================================================================

def _build_graph() -> Any:
    """
    Compile the Supervisor + ReAct worker LangGraph.

    Topology:
        START → railway_worker_node → supervisor_node
                       ▲                    │ (no flag, cap not reached)
                       └────────────────────┘
                                            └──► END  (flag found or cap)
    """
    graph = StateGraph(RailwayState)
    graph.add_node("railway_worker", railway_worker_node)
    graph.add_node("supervisor",     supervisor_node)
    graph.add_edge(START, "railway_worker")
    graph.add_edge("railway_worker", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _should_continue,
        {"railway_worker": "railway_worker", END: END},
    )
    return graph.compile()


# Graph is compiled once at module load; it is stateless and reusable.
_COMPILED_GRAPH = _build_graph()


# =============================================================================
# Background Thread Runner
# =============================================================================

def _run_agent_thread(task_id: str, model: str) -> None:
    """
    Execute the compiled LangGraph in a background daemon thread.

    Appends log entries to _task_store throughout execution; marks
    done=True on completion (success or failure).  Persists artifacts
    to disk regardless of outcome.

    Args:
        task_id: In-memory task store key.
        model:   OpenRouter model identifier string.
    """
    # Bind task_id for any log calls that happen before the first node runs.
    _thread_local.task_id = task_id
    _append_log(task_id, "agent_step", f"Agent thread started — model: {model}")

    try:
        initial_state: RailwayState = {
            "messages": [
                SystemMessage(content=_WORKER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Start now: call action='help' to receive the API documentation."
                    )
                ),
            ],
            "flag":              None,
            "supervisor_rounds": 0,
            "task_id":           task_id,
        }

        final_state = _COMPILED_GRAPH.invoke(initial_state)
        flag = final_state.get("flag")

        if flag:
            _task_store[task_id]["flag"] = flag
            _append_log(
                task_id,
                "done",
                f"✅ Mission complete — Railway X-01 activated.  Flag: {flag}",
                {"flag": flag},
            )
        else:
            err = "Agent completed all supervisor rounds without finding the flag."
            _task_store[task_id]["error"] = err
            _append_log(task_id, "error", err)

    except Exception as exc:
        logger.exception("Railway agent thread error (task=%s): %s", task_id, exc)
        _task_store[task_id]["error"] = str(exc)
        _append_log(task_id, "error", f"Fatal agent error: {exc}", {"exc": str(exc)})

    finally:
        _task_store[task_id]["done"] = True
        _save_artifacts(task_id)


def _save_artifacts(task_id: str) -> None:
    """
    Persist log.json and (if the flag was found) answer.json to disk.

    Files are written to lesson_05/0105task_context/ which is created
    if it does not yet exist.

    Args:
        task_id: Task store key whose data should be saved.
    """
    state = _task_store.get(task_id, {})
    _ANSWER_DIR.mkdir(parents=True, exist_ok=True)

    # Always write the full interaction log for inspection.
    log_path = _ANSWER_DIR / "log.json"
    with log_path.open("w", encoding="utf-8") as fh:
        json.dump(state.get("log", []), fh, indent=2, ensure_ascii=False, default=str)

    # Write answer.json only when the flag was successfully captured.
    flag = state.get("flag")
    if flag:
        answer_path = _ANSWER_DIR / "answer.json"
        with answer_path.open("w", encoding="utf-8") as fh:
            json.dump({"task": TASK_NAME, "flag": flag}, fh, indent=2, ensure_ascii=False)


# =============================================================================
# Public API
# =============================================================================

def run_railway_agent(model: str | None = None) -> str:
    """
    Start the railway activation agent in a background daemon thread.

    Returns immediately with a task_id; the agent runs asynchronously.
    Use the task_id with the SSE stream endpoint to monitor progress.

    Args:
        model: OpenRouter model identifier override.
               Defaults to RAILWAY_MODEL constant.

    Returns:
        task_id (str): Opaque identifier for this run.
    """
    resolved_model = (model or RAILWAY_MODEL).strip()
    task_id = str(uuid.uuid4())

    _task_store[task_id] = {
        "log":   [],
        "done":  False,
        "flag":  None,
        "error": None,
        "model": resolved_model,
    }

    thread = threading.Thread(
        target=_run_agent_thread,
        args=(task_id, resolved_model),
        daemon=True,
        name=f"railway-{task_id[:8]}",
    )
    thread.start()

    logger.info("Railway agent started: task_id=%s  model=%s", task_id, resolved_model)
    return task_id


def get_task_state(task_id: str) -> dict | None:
    """
    Return a snapshot of the current task store entry.

    Args:
        task_id: The identifier returned by run_railway_agent().

    Returns:
        Dict with keys: log, done, flag, error, model — or None if unknown.
    """
    return _task_store.get(task_id)
