"""
Agent views — Master Orchestrator.

Two URL handlers:
  agent_view (GET)  — renders the orchestrator chat UI
  agent_api  (POST) — processes a message through the orchestrator
"""

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_05.services.orchestrator_service import orchestrate

logger = logging.getLogger(__name__)


@require_GET
def agent_view(request: HttpRequest) -> HttpResponse:
    """Workspace partial — renders the master orchestrator chat interface."""
    return render(request, "lesson_05/agent.html")


@require_POST
def agent_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — routes the user's message through the orchestrator.

    Classifies the intent, delegates to the appropriate sub-agent, and
    returns an HTML partial containing the routing metadata and the response.

    Expected POST fields:
        message (str): The user's natural-language input.
    """
    message = request.POST.get("message", "").strip()
    if not message:
        return HttpResponse(
            '<p class="text-red-600 text-sm">Please enter a message.</p>',
            status=400,
        )

    try:
        result = orchestrate(message)
    except Exception as exc:
        logger.exception("agent_api orchestration failed: %s", exc)
        return HttpResponse(
            f'<p class="text-red-600 text-sm">Orchestration error: {exc}</p>',
            status=500,
        )

    return render(request, "lesson_05/partials/agent_result.html", {
        "message":     message,
        "intent":      result["intent"],
        "agent_label": result["agent_label"],
        "reasoning":   result["reasoning"],
        "response":    result["response"],
    })
