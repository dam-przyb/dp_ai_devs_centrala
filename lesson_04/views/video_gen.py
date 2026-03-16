"""
Video generation views — submit a prompt, poll for status using HTMX.

Two endpoints:
  - video_gen_view / video_gen_api : accept the prompt, create the job,
    return an HTMX polling div.
  - video_status : called by HTMX every 5 seconds; returns either the
    polling div again (if still running) or a final <video> element (if done).
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_04.services.video_generation_service import create_video_job, poll_video_job


@require_GET
def video_gen_view(request: HttpRequest) -> HttpResponse:
    """Workspace partial — renders the video generation prompt form."""
    return render(request, "lesson_04/video_gen.html")


@require_POST
def video_gen_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — submit a video-generation prompt.

    Creates a VideoGenerationJob and returns a polling div that HTMX
    will refresh every 5 seconds via the status endpoint.
    """
    prompt = request.POST.get("prompt", "").strip()
    if not prompt:
        return render(request, "lesson_04/partials/video_status.html",
                      {"error": "Please enter a prompt."})

    try:
        job = create_video_job(prompt)
        return render(request, "lesson_04/partials/video_status.html", {"job": job})
    except Exception as exc:
        return render(request, "lesson_04/partials/video_status.html",
                      {"error": str(exc)})


@require_GET
def video_status(request: HttpRequest, task_id: str) -> HttpResponse:
    """
    HTMX polling endpoint — check video job status.

    - If job is still pending/processing → return the polling div (HTMX keeps polling).
    - If job is done → return a <video> element (no hx-trigger, polling stops).
    - If job failed  → return an error message.
    """
    try:
        job = poll_video_job(task_id)
        return render(request, "lesson_04/partials/video_status.html", {"job": job})
    except Exception as exc:
        return render(request, "lesson_04/partials/video_status.html",
                      {"error": str(exc)})
