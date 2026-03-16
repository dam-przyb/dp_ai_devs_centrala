from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from lesson_01.services.structured_service import evaluate_text


@require_GET
def structured_view(request: HttpRequest) -> HttpResponse:
    return render(request, "lesson_01/structured.html")


@require_POST
def structured_api(request: HttpRequest) -> HttpResponse:
    text = request.POST.get("text", "").strip()
    if not text:
        return render(request, "lesson_01/partials/structured_result.html",
                      {"error": "Please enter some text to evaluate."})
    try:
        result = evaluate_text(text)
        return render(request, "lesson_01/partials/structured_result.html",
                      {"result": result})
    except Exception as exc:
        return render(request, "lesson_01/partials/structured_result.html",
                      {"error": str(exc)})
