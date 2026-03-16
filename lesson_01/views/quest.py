from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings

from lesson_01.services.quest_service import execute_quest


@require_GET
def quest_view(request: HttpRequest) -> HttpResponse:
    """Render the quest workspace"""
    return render(request, "lesson_01/quest.html")


@require_POST
def quest_api(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint - executes quest and returns results"""
    try:
        # Get API key from settings
        api_key = settings.AIDEVS_API_KEY

        # Execute quest workflow
        result = execute_quest(api_key)

        # Render result partial with all data
        return render(
            request,
            "lesson_01/partials/quest_result.html",
            {"result": result}
        )
    except Exception as exc:
        # Return error in result format
        return render(
            request,
            "lesson_01/partials/quest_result.html",
            {"result": {"error": str(exc)}}
        )
