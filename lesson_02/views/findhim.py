"""
views/findhim.py
================
Thin Django view for the "findhim" investigation module.

GET  /02/findhim/       → render workspace partial (form to trigger the agent)
POST /02/findhim/api/   → run the agent; return HTMX result partial
"""

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST

from lesson_02.services.findhim_agent_service import run_findhim_agent


@require_GET
def findhim_view(request: HttpRequest) -> HttpResponse:
    """Render the findhim workspace form."""
    return render(request, "lesson_02/findhim.html")


@require_POST
def findhim_api(request: HttpRequest) -> HttpResponse:
    """
    Run the findhim agent and return the HTMX result partial.

    Phase 1 (Python) fetches all sightings and finds the closest suspect.
    Phase 2 (LLM) retrieves access level and submits the answer.
    """
    try:
        data = run_findhim_agent()
        return render(request, "lesson_02/partials/findhim_result.html", {"data": data})
    except Exception as exc:
        return render(
            request,
            "lesson_02/partials/findhim_result.html",
            {"error": str(exc)},
        )
