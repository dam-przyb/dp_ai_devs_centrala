"""
services.py — Business logic and file tools for the Agentic RAG module (02_01).

Responsibilities:
- Define three file-access tools (list_directory, search_text, read_file_fragment)
  scoped to a configurable document root. All paths are validated to prevent
  directory-traversal attacks.
- Build and cache the LangGraph compiled graph.
- Expose run_agentic_rag() as the single entry point for views.
- Provide helpers to serialise/deserialise conversation history for Django sessions.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from langchain.tools import tool
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from module_02_01.graphs import build_rag_graph
from module_02_01.prompts import SYSTEM_PROMPT
from module_02_01.schemas import AgentReply, Source

# =============================================================================
# Configuration constants
# =============================================================================

# Model used for the RAG agent — override via RAG_02_01_MODEL env var.
RAG_MODEL: str = os.getenv("RAG_02_01_MODEL", "openai/gpt-5-mini")

# Maximum number of LLM invocations before graceful exit.
MAX_STEPS: int = 50

# Maximum number of search results returned per query.
MAX_SEARCH_RESULTS: int = 50

# Maximum lines returned by read_file_fragment in one call (prevent huge reads).
MAX_READ_LINES: int = 200

# =============================================================================
# Document root helpers
# =============================================================================


def get_doc_root() -> Path:
    """
    Return the configured document root directory.

    Uses settings.LESSONS_TEXTS_DIR when set; falls back to a
    `_lessons_texts/` folder at the project BASE_DIR.
    """
    return Path(getattr(settings, "LESSONS_TEXTS_DIR", settings.BASE_DIR / "_lessons_texts"))


def _safe_path(subpath: str) -> Path:
    """
    Resolve *subpath* relative to the document root and verify it stays within it.

    This is the single choke-point that prevents directory-traversal attacks
    (e.g. '../../../etc/passwd') regardless of what the LLM passes to a tool.

    Args:
        subpath: A path string supplied by the LLM tool call.

    Returns:
        Resolved absolute Path inside the document root.

    Raises:
        PermissionError: If the resolved path escapes the document root.
    """
    root = get_doc_root().resolve()
    # Strip leading slashes so the join is always relative
    cleaned = subpath.lstrip("/\\")
    target = (root / cleaned).resolve()
    if not str(target).startswith(str(root)):
        raise PermissionError(
            f"Access denied: '{subpath}' resolves outside the document root."
        )
    return target


# =============================================================================
# File tools (LangChain @tool decorated)
# =============================================================================


@tool
def list_directory(path: str = ".") -> str:
    """
    List files and subdirectories inside the document root.

    Pass '.' to list the root itself, or a relative subdirectory path.
    Directories are suffixed with '/'.

    Args:
        path: Relative path within the document root (default '.').

    Returns:
        Newline-separated listing, or an error message string.
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Directory '{path}' does not exist."
        if not target.is_dir():
            return f"'{path}' is a file, not a directory. Use read_file_fragment to read it."

        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
        lines = [
            f"{'[DIR]  ' if e.is_dir() else '[FILE] '}{e.name}{'/' if e.is_dir() else ''}"
            for e in entries
        ]
        root_str = str(get_doc_root().resolve())
        relative_display = str(target.resolve()).replace(root_str, "").lstrip("/\\") or "."
        header = f"Contents of '{relative_display}' ({len(lines)} entries):"
        return "\n".join([header] + lines) if lines else f"'{path}' is empty."
    except PermissionError as exc:
        return str(exc)


@tool
def search_text(query: str, path: str = ".") -> str:
    """
    Search for text across all .md and .txt files in the document root.

    Performs a case-insensitive substring search and returns matching lines with
    their file paths and line numbers. Returns up to 50 results.

    Use Polish keywords when the document content is in Polish.

    Args:
        query: Search string (case-insensitive).
        path:  Relative path to scope the search (default '.' = entire root).

    Returns:
        JSON string with keys 'query', 'total', and 'matches' (list of
        {file, line_number, line_content} objects).
    """
    try:
        scope = _safe_path(path)
        if not scope.exists():
            return json.dumps({"query": query, "total": 0, "matches": [], "error": f"Path '{path}' does not exist."})

        root = get_doc_root().resolve()
        pattern = query.lower()
        matches: list[dict] = []
        total = 0

        # Walk all markdown and plain-text files within the scope.
        glob_root = scope if scope.is_dir() else scope.parent
        for file_path in sorted(glob_root.rglob("*")):
            if file_path.suffix.lower() not in {".md", ".txt"} or not file_path.is_file():
                continue
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            for line_no, line in enumerate(lines, start=1):
                if pattern in line.lower():
                    total += 1
                    if len(matches) < MAX_SEARCH_RESULTS:
                        rel = str(file_path.resolve()).replace(str(root), "").lstrip("/\\")
                        matches.append(
                            {
                                "file": rel,
                                "line_number": line_no,
                                "line_content": line.strip()[:200],
                            }
                        )

        return json.dumps(
            {"query": query, "total": total, "matches": matches},
            ensure_ascii=False,
        )
    except PermissionError as exc:
        return json.dumps({"query": query, "total": 0, "matches": [], "error": str(exc)})


@tool
def read_file_fragment(path: str, start_line: int = 1, end_line: int = 50) -> str:
    """
    Read a specific line range from a file inside the document root.

    Always prefer reading targeted line ranges rather than whole files.
    Lines are 1-based; end_line is inclusive. Maximum 200 lines per call.

    Args:
        path:       Relative file path within the document root.
        start_line: First line to return (1-based, default 1).
        end_line:   Last line to return inclusive (default 50).

    Returns:
        The requested lines as a string with line numbers prepended,
        or an error message.
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"File '{path}' does not exist."
        if target.is_dir():
            return f"'{path}' is a directory. Use list_directory instead."

        # Enforce per-call read limit to prevent accidental huge reads.
        clamped_end = min(end_line, start_line + MAX_READ_LINES - 1)
        all_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        total_lines = len(all_lines)

        # Convert to 0-based slice indices.
        s = max(0, start_line - 1)
        e = min(clamped_end, total_lines)

        if s >= total_lines:
            return f"File '{path}' has only {total_lines} lines; start_line {start_line} is out of range."

        selected = all_lines[s:e]
        numbered = [f"{s + i + 1:>5}: {line}" for i, line in enumerate(selected)]
        header = f"--- {path} (lines {s + 1}–{s + len(selected)} of {total_lines}) ---"
        return "\n".join([header] + numbered)
    except PermissionError as exc:
        return str(exc)


# The ordered list of tools exposed to the agent.
_TOOLS = [list_directory, search_text, read_file_fragment]

# =============================================================================
# LLM and graph singletons (lazy-initialised)
# =============================================================================

_graph: Any = None  # cached compiled LangGraph


def _get_graph() -> Any:
    """
    Return the compiled LangGraph, building it on first call.

    The graph is built once per process and reused for all requests.
    The LLM is configured here to avoid settings access at import time.
    """
    global _graph
    if _graph is None:
        llm = ChatOpenAI(
            model=RAG_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            temperature=0,
            max_tokens=4096,
        ).bind_tools(_TOOLS)
        _graph = build_rag_graph(tools=_TOOLS, llm=llm, max_steps=MAX_STEPS)
    return _graph


# =============================================================================
# Session serialisation helpers
# =============================================================================


def serialise_history(messages: list[AnyMessage]) -> list[dict]:
    """
    Convert LangChain message objects to JSON-serialisable dicts for session storage.

    Only human and AI messages are preserved; system and tool messages are
    excluded — system prompts are injected fresh on each run, and tool messages
    are ephemeral scaffolding.

    Args:
        messages: LangChain message list from the agent run.

    Returns:
        List of {"role": "human"|"ai", "content": str} dicts.
    """
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append({"role": "human", "content": str(msg.content)})
        elif isinstance(msg, AIMessage) and msg.content:
            # Exclude pure tool-calling turns (content is empty, only tool_calls set)
            result.append({"role": "ai", "content": str(msg.content)})
    return result


def deserialise_history(data: list[dict]) -> list[AnyMessage]:
    """
    Reconstruct LangChain message objects from session-stored dicts.

    Args:
        data: List of {"role": "human"|"ai", "content": str} dicts.

    Returns:
        List of HumanMessage / AIMessage objects suitable for LangGraph input.
    """
    messages: list[AnyMessage] = []
    for item in data:
        role = item.get("role", "")
        content = item.get("content", "")
        if role == "human":
            messages.append(HumanMessage(content=content))
        elif role == "ai":
            messages.append(AIMessage(content=content))
    return messages


# =============================================================================
# Source extraction
# =============================================================================


def _extract_sources(messages: list[AnyMessage]) -> list[Source]:
    """
    Scan all AIMessages for read_file_fragment tool calls and collect sources.

    Deduplicates by (file, start_line, end_line) so repeated reads of the same
    range only appear once in the source list.

    Args:
        messages: Full message list from the completed graph run.

    Returns:
        Ordered, deduplicated list of Source objects.
    """
    seen: set[tuple] = set()
    sources: list[Source] = []

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        for tc in tool_calls:
            if tc.get("name") != "read_file_fragment":
                continue
            args = tc.get("args", {})
            file_path = args.get("path", "")
            start = args.get("start_line")
            end = args.get("end_line")
            key = (file_path, start, end)
            if key not in seen:
                seen.add(key)
                sources.append(Source(file=file_path, start_line=start, end_line=end))

    return sources


# =============================================================================
# Public API
# =============================================================================


def run_agentic_rag(query: str, history: list[dict]) -> AgentReply:
    """
    Execute the agentic RAG loop for a user query.

    Builds the initial message list from the system prompt + previous turns
    + the new question, runs the compiled LangGraph, then extracts the final
    answer and sources from the resulting state.

    Args:
        query:   The user's new question (plain text).
        history: Previous turns from session storage —
                 list of {"role": "human"|"ai", "content": str} dicts.

    Returns:
        AgentReply with the synthesised answer, sources, and step count.
        On error (max steps, LLM failure), the error field is populated and
        answer contains a partial/fallback message.
    """
    # Build initial messages: system prompt + prior conversation + new query.
    prior_messages = deserialise_history(history)
    initial_messages = [SystemMessage(content=SYSTEM_PROMPT)] + prior_messages + [HumanMessage(content=query)]

    try:
        graph = _get_graph()
        final_state = graph.invoke({"messages": initial_messages, "step": 0})
    except Exception as exc:
        return AgentReply(
            answer="The agent encountered an unexpected error and could not complete the request.",
            error=str(exc),
        )

    # Extract the last meaningful AI answer (non-empty content, no tool calls).
    answer_text = ""
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            answer_text = str(msg.content)
            break

    if not answer_text:
        answer_text = "The agent did not produce a final answer."

    sources = _extract_sources(final_state["messages"])
    steps_taken = final_state.get("step", 0)

    # Detect whether the run hit the max-steps guardrail.
    error: str | None = None
    if steps_taken >= MAX_STEPS:
        error = f"Reached the {MAX_STEPS}-step limit. Answer may be incomplete."

    return AgentReply(
        answer=answer_text,
        sources=sources,
        steps_taken=steps_taken,
        error=error,
    )
