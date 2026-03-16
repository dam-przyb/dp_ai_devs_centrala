"""
Report service — generate a PDF from user-supplied content using WeasyPrint.

Flow:
  1. Build an HTML string from a Django template fragment.
  2. Pass it through WeasyPrint to produce a PDF byte-stream.
  3. Return the bytes so the view can serve them as a file download.

WeasyPrint converts HTML+CSS to PDF, meaning any styling applied via
inline styles or embedded <style> blocks appears in the output.
"""

from django.template.loader import render_to_string


def build_report_html(title: str, sections: list[dict]) -> str:
    """
    Render the report data into an HTML string suitable for WeasyPrint.

    Args:
        title:    Report title shown at the top.
        sections: List of {"heading": str, "body": str} dicts.

    Returns:
        A complete HTML document as a string.
    """
    return render_to_string(
        "lesson_04/partials/report_document.html",
        {"title": title, "sections": sections},
    )


def generate_pdf(title: str, sections: list[dict]) -> bytes:
    """
    Generate a PDF document from the provided report data.

    Args:
        title:    Report title.
        sections: List of {"heading": str, "body": str} dicts.

    Returns:
        Raw PDF bytes ready to be served as a file download.

    Raises:
        ImportError: If WeasyPrint is not installed.
    """
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise ImportError(
            "WeasyPrint is required for PDF generation. "
            "Install it with: pip install weasyprint"
        ) from exc

    html_string = build_report_html(title, sections)
    pdf_bytes   = HTML(string=html_string).write_pdf()
    return pdf_bytes
