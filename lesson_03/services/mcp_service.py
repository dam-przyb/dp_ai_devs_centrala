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
                "input_schema": t.inputSchema if hasattr(t, "inputSchema") else {},
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
    Run a LangChain tool-calling agent whose tools are sourced from the MCP server.

    Each tool call opens a fresh MCP session so the agent can be used with
    standard LangChain AgentExecutor (which is not async-session-aware).

    Args:
        user_query: Natural-language task for the agent.

    Returns:
        {"output": str, "steps": list[{tool, input, output}]}
    """
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain.tools import StructuredTool
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    # 1. Get tool definitions from MCP
    tools_meta = await list_mcp_tools_async()

    # 2. Wrap each MCP tool as a LangChain StructuredTool.
    #    Each call opens its own MCP session — simple but correct.
    def _make_lc_tool(name: str, description: str) -> StructuredTool:
        """Create a StructuredTool whose coroutine delegates to call_mcp_tool_async."""
        async def _fn(**kwargs):
            return await call_mcp_tool_async(name, kwargs)

        _fn.__name__ = name  # needed by StructuredTool introspection

        return StructuredTool.from_function(
            coroutine=_fn,
            name=name,
            description=description or f"MCP tool: {name}",
        )

    lc_tools = [_make_lc_tool(t["name"], t["description"]) for t in tools_meta]

    # 3. Set up LangChain agent
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful filesystem agent. "
                   "Use the available MCP tools to complete the user's request step by step."),
        ("human",  "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent    = create_tool_calling_agent(llm, lc_tools, prompt)
    executor = AgentExecutor(agent=agent, tools=lc_tools, return_intermediate_steps=True)

    # 4. Run
    result = await executor.ainvoke({"input": user_query})

    steps = [
        {
            "tool":   action.tool,
            "input":  action.tool_input,
            "output": str(observation),
        }
        for action, observation in result.get("intermediate_steps", [])
    ]

    return {"output": result["output"], "steps": steps}
