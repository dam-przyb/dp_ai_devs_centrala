"""
views/sendit.py
===============
Django view for the SPK "sendit" quest module.

GET  /04/sendit/      → render the workspace form (quest parameters + run button)
POST /04/sendit/api/  → trigger the LLM agent; return HTMX result partial
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_04.services.sendit_service import run_sendit_agent


@require_GET
def sendit_view(request: HttpRequest) -> HttpResponse:
    """Render the SPK quest workspace page with shipment parameters summary."""
    return render(request, "lesson_04/sendit.html")


@require_POST
def sendit_api(request: HttpRequest) -> HttpResponse:
    """
    Run the SPK declaration agent and return the HTMX result partial.

    The agent fetches full SPK documentation from the hub, reasons about the
    correct category and route code, fills the Załącznik E template, and submits
    to /verify — retrying up to 3 times on validation errors.

    All actions are logged to 0104task_context/log.json.
    """
    try:
        data = run_sendit_agent()
        return render(request, "lesson_04/partials/sendit_result.html", {"data": data})
    except Exception as exc:
        return render(
            request,
            "lesson_04/partials/sendit_result.html",
            {"error": str(exc)},
        )
