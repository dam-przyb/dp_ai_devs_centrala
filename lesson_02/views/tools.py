from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from lesson_02.services.weather_service import run_weather_query


@require_GET
def tools_view(request: HttpRequest) -> HttpResponse:
    return render(request, "lesson_02/tools.html")


@require_POST
def tools_api(request: HttpRequest) -> HttpResponse:
    prompt = request.POST.get("prompt", "").strip()
    if not prompt:
        return render(request, "lesson_02/partials/weather_result.html",
                      {"error": "Please enter a question."})
    try:
        data = run_weather_query(prompt)
        return render(request, "lesson_02/partials/weather_result.html", {"data": data})
    except Exception as exc:
        return render(request, "lesson_02/partials/weather_result.html",
                      {"error": str(exc)})
