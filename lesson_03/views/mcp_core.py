"""
MCP Core view — lists all MCP tools exposed by the configured server.

Educational goal: show students what MCP "looks like" under the hood —
the tool registry with names, descriptions, and JSON schemas.
"""

import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_03.services.mcp_service import call_mcp_tool, list_mcp_tools


@require_GET
def mcp_core_view(request: HttpRequest) -> HttpResponse:
    """
    Workspace partial — renders the MCP Core tool-explorer page.

    Loads the tool list from the live MCP server so the UI shows real data.
    Handles MCP connection errors gracefully so a missing server doesn't crash
    the whole dashboard.
    """
    context: dict = {"tools": [], "error": None}
    try:
        context["tools"] = list_mcp_tools()
    except Exception as exc:
        context["error"] = str(exc)
    return render(request, "lesson_03/mcp_core.html", context)


@require_POST
def mcp_core_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — calls a single MCP tool with caller-supplied arguments.

    Expects form fields:
      - tool_name (str): the MCP tool to invoke
      - tool_args (str): JSON-encoded dict of arguments, or empty string
    """
    tool_name = request.POST.get("tool_name", "").strip()
    args_raw  = request.POST.get("tool_args", "").strip()

    if not tool_name:
        return render(request, "lesson_03/partials/tool_result.html",
                      {"error": "tool_name is required."})

    # Parse JSON args; default to empty dict if blank
    try:
        tool_args = json.loads(args_raw) if args_raw else {}
    except ValueError as exc:
        return render(request, "lesson_03/partials/tool_result.html",
                      {"error": f"Invalid JSON in tool_args: {exc}"})

    try:
        output = call_mcp_tool(tool_name, tool_args)
        return render(request, "lesson_03/partials/tool_result.html",
                      {"tool_name": tool_name, "tool_args": tool_args, "output": output})
    except Exception as exc:
        return render(request, "lesson_03/partials/tool_result.html",
                      {"error": str(exc)})
