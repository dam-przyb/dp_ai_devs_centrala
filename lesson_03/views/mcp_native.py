"""
MCP Native view — demonstrates calling MCP tools directly (no LangChain).

Educational goal: show students the raw MCP client API (ClientSession,
initialize, call_tool) without any LangChain abstraction layer.
The LLM is NOT involved here — the user picks the tool and args manually.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_03.services.mcp_service import call_mcp_tool, list_mcp_tools


@require_GET
def mcp_native_view(request: HttpRequest) -> HttpResponse:
    """
    Workspace partial — renders the native MCP call demo page.

    Pre-loads the tool list so the template can build a <select> dropdown
    and show the input schema for each tool.
    """
    context: dict = {"tools": [], "error": None}
    try:
        context["tools"] = list_mcp_tools()
    except Exception as exc:
        context["error"] = str(exc)
    return render(request, "lesson_03/mcp_native.html", context)


@require_POST
def mcp_native_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — executes a direct MCP tool call and returns a raw-output partial.

    This is intentionally low-level: no LLM, no routing, just the MCP wire call.
    Expects the same form fields as mcp_core_api (tool_name, tool_args).
    """
    import json

    tool_name = request.POST.get("tool_name", "").strip()
    args_raw  = request.POST.get("tool_args", "").strip()

    if not tool_name:
        return render(request, "lesson_03/partials/tool_result.html",
                      {"error": "Select a tool first."})

    try:
        tool_args = json.loads(args_raw) if args_raw else {}
    except ValueError as exc:
        return render(request, "lesson_03/partials/tool_result.html",
                      {"error": f"Invalid JSON: {exc}"})

    try:
        output = call_mcp_tool(tool_name, tool_args)
        return render(request, "lesson_03/partials/tool_result.html",
                      {"tool_name": tool_name, "tool_args": tool_args, "output": output})
    except Exception as exc:
        return render(request, "lesson_03/partials/tool_result.html",
                      {"error": str(exc)})
