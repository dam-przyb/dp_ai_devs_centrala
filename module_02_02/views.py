"""
Views for module_02_02 — Chunking, Embeddings, Hybrid RAG.

Three HTMX-driven views:

1. ChunkingView (GET /s2/02/chunking/)
   - Shows chunking demo UI.
   - POST triggers run_chunking_demo() and returns results partial.

2. EmbeddingView (GET /s2/02/embeddings/)
   - Shows phrase input form.
   - POST triggers embed_texts() and returns similarity matrix partial.

3. HybridRagView (GET /s2/02/rag/)
   - Shows chat UI.
   - POST /s2/02/rag/chat/ — runs run_hybrid_rag() and returns chat partial.
   - POST /s2/02/rag/clear/ — clears session history.
   - POST /s2/02/rag/reindex/ — reindexes workspace files.
"""

from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from module_02_02.indexer import get_index_stats, index_workspace
from module_02_02.services import (
    deserialise_history,
    embed_texts,
    run_chunking_demo,
    run_hybrid_rag,
    serialise_history,
)

logger = logging.getLogger(__name__)

# Session key prefix — scoped to this module
_KEY_RAG_HISTORY = "m0202_rag_history"
_KEY_RAG_STATS = "m0202_rag_stats"


# =============================================================================
# Chunking Demo
# =============================================================================

@require_GET
def chunking_index(request: HttpRequest) -> HttpResponse:
    """Render the chunking demo landing page."""
    return render(request, "module_02_02/chunking.html", {"active_file": "example.md"})


@require_POST
def chunking_run(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint: run all four chunking strategies and return results partial.

    Expects form field `source_file` (default: example.md).
    Returns HTML partial rendered into the results container.
    """
    source_file = request.POST.get("source_file", "example.md").strip()

    try:
        result = run_chunking_demo(source_file)
        # Build per-strategy summary for the template
        strategies_summary = [
            {
                "name": strategy_name,
                "count": len(chunks),
                "chunks": [
                    {
                        "index": c.metadata.index,
                        "content_preview": c.content[:300],
                        "heading": c.metadata.heading,
                        "context": c.metadata.context,
                        "topic": c.metadata.topic,
                        "char_count": len(c.content),
                    }
                    for c in chunks[:6]  # show first 6 chunks in UI
                ],
            }
            for strategy_name, chunks in result.strategies.items()
        ]
        ctx = {
            "source_file": source_file,
            "strategies": strategies_summary,
            "llm_prompt_tokens": result.llm_prompt_tokens,
            "llm_completion_tokens": result.llm_completion_tokens,
            "error": None,
        }
    except FileNotFoundError:
        ctx = {"error": f"File not found in workspace: {source_file}"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chunking demo failed")
        ctx = {"error": str(exc)}

    return render(request, "module_02_02/partials/_chunking_result.html", ctx)


# =============================================================================
# Embeddings Demo
# =============================================================================

@require_GET
def embeddings_index(request: HttpRequest) -> HttpResponse:
    """Render the embeddings similarity demo landing page."""
    return render(request, "module_02_02/embeddings.html", {})


@require_POST
def embeddings_compute(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint: embed phrases and return the similarity matrix partial.

    Expects form field `phrases` — one phrase per line.
    """
    raw = request.POST.get("phrases", "").strip()
    phrases = [p.strip() for p in raw.splitlines() if p.strip()]

    if not phrases:
        ctx = {"error": "Please enter at least one phrase."}
        return render(request, "module_02_02/partials/_embeddings_result.html", ctx)

    if len(phrases) > 20:
        ctx = {"error": "Maximum 20 phrases per request."}
        return render(request, "module_02_02/partials/_embeddings_result.html", ctx)

    try:
        matrix = embed_texts(phrases)
        # Zip texts with matrix rows so templates can iterate without indexing tricks
        rows = list(zip(matrix.texts, matrix.matrix))
        ctx = {
            "texts": matrix.texts,
            "rows": rows,
            "dim": 1536,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Embedding computation failed")
        ctx = {"error": str(exc)}

    return render(request, "module_02_02/partials/_embeddings_result.html", ctx)


# =============================================================================
# Hybrid RAG Chat
# =============================================================================

@require_GET
def rag_index(request: HttpRequest) -> HttpResponse:
    """Render the Hybrid RAG chat landing page with current index stats."""
    stats = get_index_stats()
    history_data = request.session.get(_KEY_RAG_HISTORY, [])
    messages = _build_display_messages(history_data)
    return render(request, "module_02_02/rag.html", {
        "messages": messages,
        "index_stats": stats,
    })


@require_POST
def rag_chat(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint: run one Hybrid RAG turn and return the chat partial.

    Reads session history, appends user query, invokes the agent, appends
    the AI reply, and stores the updated history back in the session.
    """
    query = request.POST.get("query", "").strip()
    if not query:
        return HttpResponse("", status=204)

    # Load and deserialise session history
    history_data = request.session.get(_KEY_RAG_HISTORY, [])
    history = deserialise_history(history_data)

    try:
        answer = run_hybrid_rag(query, history)

        # Persist updated history (human + ai messages only — skip tool internals)
        from langchain_core.messages import HumanMessage, AIMessage
        updated_history = list(history) + [
            HumanMessage(content=query),
            AIMessage(content=answer.answer),
        ]
        request.session[_KEY_RAG_HISTORY] = serialise_history(updated_history)

        # Accumulate stats
        prev_stats = request.session.get(_KEY_RAG_STATS, {"search_calls": 0, "turns": 0})
        prev_stats["search_calls"] += answer.search_calls
        prev_stats["turns"] += 1
        request.session[_KEY_RAG_STATS] = prev_stats

        ctx = {
            "query": query,
            "answer": answer.answer,
            "sources": answer.sources,
            "search_calls": answer.search_calls,
            "vector_available": answer.vector_available,
            "stats": prev_stats,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Hybrid RAG chat failed")
        ctx = {"query": query, "error": str(exc)}

    return render(request, "module_02_02/partials/_rag_result.html", ctx)


@require_POST
def rag_clear(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint: clear the RAG conversation history from the session."""
    request.session.pop(_KEY_RAG_HISTORY, None)
    request.session.pop(_KEY_RAG_STATS, None)
    return render(request, "module_02_02/partials/_rag_cleared.html", {})


@require_POST
def rag_reindex(request: HttpRequest) -> HttpResponse:
    """
    HTMX endpoint: (re)index all workspace markdown files.

    Returns a status partial with the indexing statistics.
    """
    try:
        stats = index_workspace()
        ctx = {"stats": stats, "error": None}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Workspace reindex failed")
        ctx = {"error": str(exc)}

    return render(request, "module_02_02/partials/_reindex_result.html", ctx)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _build_display_messages(history_data: list[dict]) -> list[dict]:
    """
    Convert session-stored history to display-ready dicts for templates.

    Filters down to only human and AI messages — tool internals are omitted
    from the chat display.

    Args:
        history_data: Raw session history as stored by serialise_history.

    Returns:
        List of {"role": "human"|"ai", "content": str} dicts.
    """
    return [
        {"role": item["type"], "content": item["content"]}
        for item in history_data
        if item.get("type") in ("human", "ai") and item.get("content")
    ]
