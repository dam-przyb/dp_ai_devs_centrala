"""
MCP Translator view — runs a LangChain agent whose tools come from MCP.

Educational goal: show the "translation" layer — MCP tools are discovered at
runtime and wrapped as LangChain StructuredTools so a standard AgentExecutor
can call them transparently.  The agent decides WHICH tool to call; the
translator layer handles the MCP wire protocol behind the scenes.
"""

import asyncio

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from lesson_03.services.mcp_service import (
    list_mcp_tools,
    run_langchain_agent_async,
)


@require_GET
def mcp_translator_view(request: HttpRequest) -> HttpResponse:
    """
    Workspace partial — renders the translator agent page.

    Shows a query input and a sidebar listing current MCP tools so students
    can see which tools the agent has available.
    """
    context: dict = {"tools": [], "error": None}
    try:
        context["tools"] = list_mcp_tools()
    except Exception as exc:
        context["error"] = str(exc)
    return render(request, "lesson_03/mcp_translator.html", context)


@require_POST
def mcp_translator_api(request: HttpRequest) -> HttpResponse:
    """
    HTMX POST — runs the LangChain+MCP agent for a user query.

    Uses asyncio.run() to drive the async agent from a sync Django view.
    Returns an agent_result partial showing steps + final output.
    """
    query = request.POST.get("query", "").strip()
    if not query:
        return render(request, "lesson_03/partials/agent_result.html",
                      {"error": "Please enter a query."})

    try:
        data = asyncio.run(run_langchain_agent_async(query))
        return render(request, "lesson_03/partials/agent_result.html", {"data": data})
    except Exception as exc:
        return render(request, "lesson_03/partials/agent_result.html",
                      {"error": str(exc)})
