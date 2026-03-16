from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from lesson_01.services.grounding_service import answer_question


@require_GET
def grounding_view(request: HttpRequest) -> HttpResponse:
    return render(request, "lesson_01/grounding.html")


@require_POST
def grounding_api(request: HttpRequest) -> HttpResponse:
    question = request.POST.get("question", "").strip()
    if not question:
        return render(request, "lesson_01/partials/grounding_result.html",
                      {"error": "Please enter a question."})
    try:
        data = answer_question(question)
        return render(request, "lesson_01/partials/grounding_result.html",
                      {"answer": data["answer"], "snippets": data["snippets"],
                       "question": question})
    except Exception as exc:
        return render(request, "lesson_01/partials/grounding_result.html",
                      {"error": str(exc)})
