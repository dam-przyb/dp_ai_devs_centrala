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
from django.conf import settings

from lesson_02.services.findhim_agent_service import run_findhim_agent

# Models available for selection in the UI — (value, display_label)
_AVAILABLE_MODELS = [
    ("openai/gpt-4o",       "GPT-4o (Recommended)"),
    ("openai/gpt-4o-mini",  "GPT-4o Mini (faster/cheaper)"),
    ("openai/gpt-4.1",      "GPT-4.1"),
]


@require_GET
def findhim_view(request: HttpRequest) -> HttpResponse:
    """Render the findhim workspace form."""
    default_model = getattr(settings, "FINDHIM_MODEL", "openai/gpt-4o")
    return render(request, "lesson_02/findhim.html", {
        "available_models": _AVAILABLE_MODELS,
        "default_model": default_model,
    })


@require_POST
def findhim_api(request: HttpRequest) -> HttpResponse:
    """
    Run the findhim agent and return the HTMX result partial.

    Phase 1 (Python) fetches all sightings and finds the closest suspect.
    Phase 2 (LLM) retrieves access level and submits the answer.
    """
    model = request.POST.get("model", "").strip() or None
    try:
        data = run_findhim_agent(model=model)
        return render(request, "lesson_02/partials/findhim_result.html", {"data": data})
    except Exception as exc:
        return render(
            request,
            "lesson_02/partials/findhim_result.html",
            {"error": str(exc)},
        )
