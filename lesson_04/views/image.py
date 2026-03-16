"""
Image generation view — DALL-E 3 image generation via OpenRouter.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_04.services.image_service import generate_image

# Valid sizes supported by DALL-E 3
VALID_SIZES = ["1024x1024", "1792x1024", "1024x1792"]


@require_GET
def image_view(request: HttpRequest) -> HttpResponse:
    """Workspace partial — renders the image generation form."""
    return render(request, "lesson_04/image.html", {"sizes": VALID_SIZES})


@require_POST
def image_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — generate an image from a text prompt.

    Expects form fields:
      - prompt (str): image description
      - size   (str): one of VALID_SIZES (default 1024x1024)
    """
    prompt = request.POST.get("prompt", "").strip()
    size   = request.POST.get("size", "1024x1024")

    if not prompt:
        return render(request, "lesson_04/partials/image_result.html",
                      {"error": "Please enter a prompt."})

    if size not in VALID_SIZES:
        size = "1024x1024"

    try:
        data = generate_image(prompt, size)
        return render(request, "lesson_04/partials/image_result.html",
                      {"data": data, "prompt": prompt})
    except Exception as exc:
        return render(request, "lesson_04/partials/image_result.html",
                      {"error": str(exc)})
