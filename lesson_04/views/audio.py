"""
Audio view — upload an audio file and get back a Whisper transcript + LLM summary.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_04.services.audio_service import process_audio


@require_GET
def audio_view(request: HttpRequest) -> HttpResponse:
    """Workspace partial — renders the audio upload form."""
    return render(request, "lesson_04/audio.html")


@require_POST
def audio_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — process uploaded audio file.

    Expects multipart/form-data with a field named 'audio_file'.
    Returns a partial with the transcript and summary.
    """
    audio_file = request.FILES.get("audio_file")
    if not audio_file:
        return render(request, "lesson_04/partials/audio_result.html",
                      {"error": "No audio file received. Please choose a file to upload."})

    try:
        data = process_audio(audio_file)
        return render(request, "lesson_04/partials/audio_result.html", {"data": data})
    except Exception as exc:
        return render(request, "lesson_04/partials/audio_result.html",
                      {"error": str(exc)})
