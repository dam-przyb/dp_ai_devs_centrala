"""
Image service — DALL-E 3 generation via OpenRouter.

OpenRouter exposes the OpenAI image API at its standard endpoint, so we can
use the official `openai` SDK pointed at OPENROUTER_BASE_URL.

Lessons demonstrated:
- Calling a multimodal endpoint (image generation)
- Handling the response URL vs. base64 data
"""

import openai
from django.conf import settings


def generate_image(prompt: str, size: str = "1024x1024") -> dict:
    """
    Generate an image from a text prompt using DALL-E 3 via OpenRouter.

    Args:
        prompt: Natural-language description of the desired image.
        size:   One of "1024x1024", "1792x1024", "1024x1792".

    Returns:
        {"url": str, "revised_prompt": str | None}
        `url` is a temporary CDN link valid for ~60 minutes.

    Raises:
        RuntimeError: On API error or missing configuration.
    """
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    client = openai.OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )

    response = client.images.generate(
        model="openai/dall-e-3",
        prompt=prompt,
        size=size,
        n=1,
        response_format="url",
    )

    image   = response.data[0]
    return {
        "url":            image.url,
        "revised_prompt": getattr(image, "revised_prompt", None),
    }
