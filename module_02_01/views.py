"""
views.py — Django views for the Agentic RAG module (02_01).

Three endpoints:
  GET  /s2/01/              → index_view   — renders the full workspace partial.
  POST /s2/01/chat/         → chat_api     — HTMX: runs the agent, returns new turn.
  POST /s2/01/clear/        → clear_api    — HTMX: resets session, clears chat area.

Conversation history and per-session statistics are persisted in Django's
session store (backed by the project's SQLite DB).
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from module_02_01.services import get_doc_root, run_agentic_rag, serialise_history

# Session keys scoped to this module to avoid collision with other apps.
_SESSION_HISTORY = "m0201_history"
_SESSION_STATS = "m0201_stats"


# =============================================================================
# Views
# =============================================================================


@require_GET
def index_view(request: HttpRequest) -> HttpResponse:
    """
    Render the full Agentic RAG workspace partial.

    Restores conversation history and cumulative stats from the session so
    the chat survives page reloads.
    """
    history = request.session.get(_SESSION_HISTORY, [])
    stats = request.session.get(_SESSION_STATS, {"total_steps": 0, "turns": 0})
    doc_root = str(get_doc_root())

    return render(
        request,
        "module_02_01/index.html",
        {
            "history": history,
            "stats": stats,
            "doc_root": doc_root,
        },
    )


@require_POST
def chat_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint: run the agentic RAG loop and return a new message pair.

    The returned partial (_chat_result.html) is appended to the chat history
    container via HTMX `hx-swap="beforeend"`. An out-of-band swap also updates
    the stats bar without a full-page reload.
    """
    question = request.POST.get("question", "").strip()
    if not question:
        return HttpResponse("")

    history = request.session.get(_SESSION_HISTORY, [])

    try:
        reply = run_agentic_rag(query=question, history=history)
    except Exception as exc:
        return render(
            request,
            "module_02_01/partials/_error.html",
            {"error": str(exc)},
        )

    # Persist the new turn to session.
    history.append({"role": "human", "content": question})
    history.append({"role": "ai", "content": reply.answer})
    request.session[_SESSION_HISTORY] = history
    request.session.modified = True

    # Update cumulative statistics.
    stats = request.session.get(_SESSION_STATS, {"total_steps": 0, "turns": 0})
    stats["total_steps"] += reply.steps_taken
    stats["turns"] += 1
    request.session[_SESSION_STATS] = stats

    return render(
        request,
        "module_02_01/partials/_chat_result.html",
        {
            "question": question,
            "reply": reply,
            "stats": stats,
        },
    )


@require_POST
def clear_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint: clear conversation history and session stats.

    Replaces the entire chat history container with an empty-state message
    and resets the stats bar via an out-of-band swap.
    """
    request.session.pop(_SESSION_HISTORY, None)
    request.session.pop(_SESSION_STATS, None)
    request.session.modified = True

    empty_stats = {"total_steps": 0, "turns": 0}
    return render(
        request,
        "module_02_01/partials/_cleared.html",
        {"stats": empty_stats},
    )
