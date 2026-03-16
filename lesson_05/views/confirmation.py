"""
Confirmation views — Human-in-the-Loop with LangGraph.

Three URL handlers:
  confirmation_view   (GET)  — renders the task input form
  confirmation_start  (POST) — initiates the graph, returns approval partial
  confirmation_resume (POST) — resumes the graph after user approval
"""

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_05.services.confirmation_service import resume_confirmation, start_confirmation

logger = logging.getLogger(__name__)


@require_GET
def confirmation_view(request: HttpRequest) -> HttpResponse:
    """Workspace partial — renders the human-in-the-loop task form."""
    return render(request, "lesson_05/confirmation.html")


@require_POST
def confirmation_start(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — initiates the LangGraph run.

    Invokes the graph, which halts before ``send_email_node``.
    Returns the approval partial containing the planned action and thread_id.

    Expected POST fields:
        task (str): Natural-language description of the action to perform.
    """
    task = request.POST.get("task", "").strip()
    if not task:
        return HttpResponse(
            '<p class="text-red-600 text-sm">Please enter a task description.</p>',
            status=400,
        )

    try:
        thread_id, pending_action = start_confirmation(task)
    except Exception as exc:
        logger.exception("confirmation_start failed: %s", exc)
        return HttpResponse(
            f'<p class="text-red-600 text-sm">Error: {exc}</p>',
            status=500,
        )

    return render(request, "lesson_05/partials/confirm_prompt.html", {
        "task":           task,
        "pending_action": pending_action,
        "thread_id":      thread_id,
    })


@require_POST
def confirmation_resume(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — resumes the graph after user approval.

    Picks up the frozen graph state by thread_id and runs
    ``send_email_node`` to completion.

    Expected POST fields:
        thread_id (str): The UUID returned by ``confirmation_start``.
    """
    thread_id = request.POST.get("thread_id", "").strip()
    if not thread_id:
        return HttpResponse(
            '<p class="text-red-600 text-sm">Missing thread_id.</p>',
            status=400,
        )

    try:
        result = resume_confirmation(thread_id)
    except Exception as exc:
        logger.exception("confirmation_resume failed: %s", exc)
        return HttpResponse(
            f'<p class="text-red-600 text-sm">Error: {exc}</p>',
            status=500,
        )

    return render(request, "lesson_05/partials/confirm_done.html", {
        "result": result,
    })
