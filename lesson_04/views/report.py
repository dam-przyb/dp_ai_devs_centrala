"""
Report view — build and download a PDF report from user-supplied content.

Two actions:
  - report_view       : renders the authoring form (GET)
  - report_preview_api: generates HTML preview in-page (POST, HTMX)
  - report_download   : streams a PDF download (POST, direct form submit)
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_04.services.report_service import generate_pdf


def _parse_sections(post_data) -> list[dict]:
    """
    Extract report sections from POST data.

    Expects repeating fields:
      section_heading_0, section_body_0
      section_heading_1, section_body_1
      ...

    Returns:
        List of {"heading": str, "body": str}, skipping empty entries.
    """
    sections = []
    i = 0
    while True:
        heading = post_data.get(f"section_heading_{i}", "").strip()
        body    = post_data.get(f"section_body_{i}",    "").strip()
        if not heading and not body:
            break  # no more sections
        if heading or body:
            sections.append({"heading": heading, "body": body})
        i += 1
    return sections


@require_GET
def report_view(request: HttpRequest) -> HttpResponse:
    """Workspace partial — renders the report authoring form."""
    return render(request, "lesson_04/report.html")


@require_POST
def report_preview_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — renders a live HTML preview of the report inside the page.
    """
    title    = request.POST.get("title", "Untitled Report").strip()
    sections = _parse_sections(request.POST)
    return render(request, "lesson_04/partials/report_preview.html",
                  {"title": title, "sections": sections})


@require_POST
def report_download(request: HttpRequest) -> HttpResponse:
    """
    Direct POST — generate a PDF and return it as a file download.

    Returns an application/pdf response that triggers a browser download.
    """
    title    = request.POST.get("title", "Untitled Report").strip()
    sections = _parse_sections(request.POST)

    try:
        pdf_bytes = generate_pdf(title, sections)
    except Exception as exc:
        # Fallback: return error as plain text so the user sees something useful
        return HttpResponse(f"PDF generation failed: {exc}", status=500,
                            content_type="text/plain")

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.pdf"'
    return response
