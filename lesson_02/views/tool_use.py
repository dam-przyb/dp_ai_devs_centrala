from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from lesson_02.services.filesystem_agent_service import run_filesystem_agent


@require_GET
def tool_use_view(request: HttpRequest) -> HttpResponse:
    return render(request, "lesson_02/tool_use.html")


@require_POST
def tool_use_api(request: HttpRequest) -> HttpResponse:
    objective = request.POST.get("objective", "").strip()
    if not objective:
        return render(request, "lesson_02/partials/agent_result.html",
                      {"error": "Please enter an objective."})
    try:
        data = run_filesystem_agent(objective)
        return render(request, "lesson_02/partials/agent_result.html", {"data": data})
    except Exception as exc:
        return render(request, "lesson_02/partials/agent_result.html",
                      {"error": str(exc)})
