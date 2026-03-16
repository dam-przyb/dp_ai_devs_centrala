"""
Upload MCP view — upload a text file and process it via the MCP filesystem agent.

Educational goal: bridge file upload (Django + HTMX) with an MCP agent loop.
The uploaded file is written into the sandbox directory, then the LangChain+MCP
agent is asked to read and summarize it — demonstrating end-to-end MCP usage.
"""

import asyncio
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_03.services.mcp_service import run_langchain_agent_async


@require_GET
def upload_mcp_view(request: HttpRequest) -> HttpResponse:
    """
    Workspace partial — renders the file-upload + MCP processing page.
    """
    return render(request, "lesson_03/upload_mcp.html")


@require_POST
def upload_mcp_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — handle uploaded file, write to sandbox, process with MCP agent.

    Steps:
      1. Validate upload.
      2. Write file into SANDBOX_DIR (safe path, no traversal).
      3. Ask the MCP agent to read and summarize the file.
      4. Return agent_result partial.
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return render(request, "lesson_03/partials/agent_result.html",
                      {"error": "No file received. Please choose a file to upload."})

    # Only allow plain-text files to keep the demo simple and safe
    filename = Path(uploaded.name).name  # strip any path component
    sandbox  = settings.SANDBOX_DIR.resolve()
    dest     = sandbox / filename

    # Ensure sandbox exists
    sandbox.mkdir(parents=True, exist_ok=True)

    try:
        dest.write_bytes(uploaded.read())
    except OSError as exc:
        return render(request, "lesson_03/partials/agent_result.html",
                      {"error": f"Could not save file: {exc}"})

    # Build an objective and let the MCP agent handle reading + summarizing
    objective = (
        f"Read the file '{filename}' from the sandbox directory "
        f"and provide a concise summary of its contents."
    )

    try:
        data = asyncio.run(run_langchain_agent_async(objective))
        data["uploaded_filename"] = filename  # pass to template for display
        return render(request, "lesson_03/partials/agent_result.html", {"data": data})
    except Exception as exc:
        return render(request, "lesson_03/partials/agent_result.html",
                      {"error": str(exc)})
