"""
views/railway.py — Railway X-01 Activation views.

Three URL handlers:

    railway_view   GET  /05/railway/                    Workspace partial (form)
    railway_api    POST /05/railway/api/                Start agent; return live-log partial
    railway_stream GET  /05/railway/stream/<task_id>/   SSE event stream for live log
"""

from __future__ import annotations

import json
import logging
import time

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render

from lesson_05.services.railway_service import (
    SSE_POLL_INTERVAL_S,
    get_task_state,
    run_railway_agent,
)

logger = logging.getLogger(__name__)


@require_GET
def railway_view(request: HttpRequest) -> HttpResponse:
    """Render the Railway X-01 quest workspace partial."""
    return render(request, "lesson_05/railway.html")


@require_POST
def railway_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — start the railway agent in a background thread.

    Does NOT wait for the agent to finish; returns the live-log partial
    immediately so the browser can connect to the SSE stream.

    Returns:
        HTML partial containing the live log container and the EventSource
        script wired to the task's SSE endpoint.
    """
    try:
        task_id = run_railway_agent()
    except Exception as exc:
        logger.exception("railway_api: failed to start agent: %s", exc)
        return HttpResponse(
            f'<p class="text-red-600 text-sm p-6">Failed to start agent: {exc}</p>',
            status=500,
        )

    return render(
        request,
        "lesson_05/partials/railway_started.html",
        {"task_id": task_id},
    )


def railway_stream(request: HttpRequest, task_id: str) -> StreamingHttpResponse:
    """
    SSE endpoint — push structured log events to the browser as they arrive.

    Each message is a JSON object on a 'data:' line (the default SSE format).
    Entry types: agent_step | api_call | api_response | retry_503 |
                 rate_limit | flag | error | done

    The stream closes automatically when the task completes or after a
    10-minute safety timeout.

    Args:
        task_id: Opaque task identifier returned by run_railway_agent().
    """

    def _generate():
        """Generator that polls the task store and yields SSE frames."""
        last_index   = 0
        # 10-minute hard ceiling — prevents a dangling open connection.
        max_cycles   = int(600 / SSE_POLL_INTERVAL_S)
        cycles       = 0

        while cycles < max_cycles:
            state = get_task_state(task_id)

            if state is None:
                yield (
                    "data: "
                    + json.dumps({"type": "error", "message": "Task not found."})
                    + "\n\n"
                )
                return

            # Push any log entries that have arrived since the last poll.
            log = state["log"]
            while last_index < len(log):
                entry = log[last_index]
                yield "data: " + json.dumps(entry, default=str) + "\n\n"
                last_index += 1

            # Once done, send the terminal event and close the stream.
            if state["done"]:
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type":  "done",
                            "flag":  state.get("flag"),
                            "error": state.get("error"),
                        }
                    )
                    + "\n\n"
                )
                return

            time.sleep(SSE_POLL_INTERVAL_S)
            cycles += 1

        # Safety timeout.
        yield (
            "data: "
            + json.dumps({"type": "error", "message": "Stream timeout after 10 minutes."})
            + "\n\n"
        )

    response = StreamingHttpResponse(_generate(), content_type="text/event-stream")
    # Disable caching and proxy buffering so events reach the browser immediately.
    response["Cache-Control"]    = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
