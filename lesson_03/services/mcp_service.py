"""
MCP Service — core helpers for interacting with an MCP server via stdio transport.

Provides:
- async primitives (_run_with_mcp, list_mcp_tools_async, call_mcp_tool_async,
  run_langchain_agent_async)
- sync wrappers (list_mcp_tools, call_mcp_tool) for use in sync Django views

All async functions must be called with `await` inside an `async def` Django view,
OR via the sync wrappers which use asyncio.run().
"""

import asyncio
import json
import shlex
from typing import Any, Optional

from django.conf import settings

# =============================================================================
# Low-level MCP helpers
# =============================================================================

async def _run_with_mcp(coro_factory):
    """
    Open a fresh MCP stdio session, run coro_factory(session), then close.

    Args:
        coro_factory: An async callable that accepts a ClientSession and returns
                      the desired result.

    Returns:
        Whatever coro_factory returns.
    """
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    raw = settings.MCP_SERVER_SCRIPT or ""
    if not raw:
        raise RuntimeError(
            "MCP_SERVER_SCRIPT is not set in settings. "
            "Add MCP_SERVER_SCRIPT=<command> to your .env file."
        )

    parts = shlex.split(raw)
    params = StdioServerParameters(command=parts[0], args=parts[1:])

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await coro_factory(session)


async def list_mcp_tools_async() -> list[dict]:
    """
    Fetch all tools exposed by the configured MCP server.

    Returns:
        List of dicts: {name, description, input_schema (dict)}
    """
    async def _fetch(session):
        result = await session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                # Use `or {}` rather than hasattr: inputSchema is always present on
                # the Pydantic Tool model but may be None for argument-free tools.
                # Passing None downstream would crash the schema builder.
                "input_schema": t.inputSchema or {},
            }
            for t in result.tools
        ]
    return await _run_with_mcp(_fetch)


async def call_mcp_tool_async(tool_name: str, tool_args: dict) -> str:
    """
    Call a single MCP tool by name and return its text output.

    Args:
        tool_name: Exact name of the MCP tool (e.g. "read_file").
        tool_args: Dict of arguments matching the tool's input schema.

    Returns:
        The text content returned by the MCP tool, or "(no output)".
    """
    async def _call(session):
        result = await session.call_tool(tool_name, tool_args)
        if result.content:
            return result.content[0].text
        return "(no output)"
    return await _run_with_mcp(_call)


# =============================================================================
# Sync wrappers (safe to call from sync Django views)
# =============================================================================

def list_mcp_tools() -> list[dict]:
    """Sync wrapper — blocks until MCP server returns tool list."""
    return asyncio.run(list_mcp_tools_async())


def call_mcp_tool(tool_name: str, tool_args: dict) -> str:
    """Sync wrapper — blocks until MCP tool call returns."""
    return asyncio.run(call_mcp_tool_async(tool_name, tool_args))


# =============================================================================
# LangChain translator — MCP tools as LangChain StructuredTools
# =============================================================================

async def run_langchain_agent_async(user_query: str) -> dict:
    """
    Run a LangGraph ReAct agent whose tools are sourced from the MCP server.

    AgentExecutor was removed in LangChain 1.x; this implementation uses
    langgraph.prebuilt.create_react_agent, which is the canonical replacement.
    Each tool call opens a fresh MCP session so the agent remains stateless.

    Args:
        user_query: Natural-language task for the agent.

    Returns:
        {"output": str, "steps": list[{tool, input, output}]}
    """
    from langchain_core.tools import StructuredTool
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.prebuilt import create_react_agent

    # 1. Fetch live tool definitions from the MCP server.
    tools_meta = await list_mcp_tools_async()

    # 2. Wrap each MCP tool as a LangChain StructuredTool.
    #    Each invocation opens its own MCP stdio session — straightforward and
    #    correct for a stateless request/response cycle.
    def _make_lc_tool(name: str, description: str, input_schema: dict) -> StructuredTool:
        """
        Build a StructuredTool with a real Pydantic args_schema derived from the
        MCP tool's JSON Schema.  Without args_schema, StructuredTool in LangChain
        1.x infers an empty model from **kwargs, which causes Pydantic to strip
        every argument before the call reaches the MCP server.
        """
        from pydantic import create_model, Field

        # Map JSON Schema primitive types to Python types.
        # All MCP filesystem tool fields are strings; we fall back to Any for
        # unknown types so novel tools don't raise a schema-build error.
        _TYPE_MAP: dict[str, type] = {
            "string":  str,
            "integer": int,
            "number":  float,
            "boolean": bool,
            "array":   list,
            "object":  dict,
        }

        properties: dict = input_schema.get("properties", {})
        required:   set  = set(input_schema.get("required", []))

        # Build field definitions: required fields are plain <type>, optional
        # ones use Optional[<type>] with a default of None.
        field_definitions: dict[str, Any] = {}
        for field_name, field_meta in properties.items():
            py_type = _TYPE_MAP.get(field_meta.get("type", ""), Any)
            field_desc = field_meta.get("description", "")
            if field_name in required:
                field_definitions[field_name] = (py_type, Field(description=field_desc))
            else:
                field_definitions[field_name] = (Optional[py_type], Field(default=None, description=field_desc))

        # Dynamically create the Pydantic model for this specific tool.
        schema_model = create_model(f"{name}_schema", **field_definitions)

        async def _fn(**kwargs):
            # Strip optional fields that Pydantic left as None.
            # Sending null values for unset optional fields causes MCP servers
            # to raise -32602 input validation errors.
            clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            return await call_mcp_tool_async(name, clean_kwargs)

        _fn.__name__ = name  # StructuredTool uses __name__ for schema generation

        return StructuredTool.from_function(
            coroutine=_fn,
            name=name,
            description=description or f"MCP tool: {name}",
            args_schema=schema_model,
        )

    lc_tools = [
        _make_lc_tool(t["name"], t["description"], t.get("input_schema", {}))
        for t in tools_meta
    ]

    # 3. Build the LangGraph ReAct agent.
    #    create_react_agent is the LangChain 1.x replacement for the removed
    #    AgentExecutor + create_tool_calling_agent combination.
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    agent = create_react_agent(
        model=llm,
        tools=lc_tools,
        prompt="You are a helpful filesystem agent. "
               "Use the available MCP tools to complete the user's request step by step.",
    )

    # 4. Run the agent; LangGraph returns a messages list, not intermediate_steps.
    result = await agent.ainvoke({"messages": [("human", user_query)]})

    # 5. Reconstruct steps by pairing AIMessage tool_calls with their ToolMessage replies.
    #    This mirrors what AgentExecutor's intermediate_steps used to expose.
    messages = result.get("messages", [])
    steps: list[dict] = []
    tool_call_index: dict[str, dict] = {}

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            # An AIMessage may request multiple tool calls at once; index each by id.
            for tc in msg.tool_calls:
                tool_call_index[tc["id"]] = {
                    "tool":   tc["name"],
                    "input":  tc["args"],
                    "output": "",  # filled in when the matching ToolMessage arrives
                }
        elif isinstance(msg, ToolMessage) and msg.tool_call_id in tool_call_index:
            # Attach the tool output and flush the completed step.
            # content can be str or list[dict] (multipart) in LangChain 1.x;
            # normalise to str so the template always renders plain text.
            step = tool_call_index.pop(msg.tool_call_id)
            raw_content = msg.content
            step["output"] = raw_content if isinstance(raw_content, str) else str(raw_content)
            steps.append(step)

    # 6. The final output is the last AIMessage that contains no tool calls.
    output = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            output = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    return {"output": output, "steps": steps}
