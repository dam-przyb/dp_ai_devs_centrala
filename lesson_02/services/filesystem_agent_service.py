from pathlib import Path
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

SANDBOX = settings.SANDBOX_DIR.resolve()


# ── Path security helper ───────────────────────────────────────────────────────

def _safe_path(subpath: str) -> Path:
    """Resolve and assert path stays within the sandbox."""
    resolved = (SANDBOX / subpath).resolve()
    if not str(resolved).startswith(str(SANDBOX)):
        raise PermissionError(
            f"Access denied: '{subpath}' resolves outside the sandbox directory."
        )
    return resolved


# ── Filesystem tools ───────────────────────────────────────────────────────────

@tool
def list_directory(subpath: str = ".") -> str:
    """List files and directories inside the sandbox. Pass '.' for root."""
    try:
        target = _safe_path(subpath)
        if not target.exists():
            return f"Directory '{subpath}' does not exist."
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
        lines = [
            f"{'[DIR] ' if e.is_dir() else '[FILE]'} {e.name}"
            for e in entries
        ]
        return "\n".join(lines) if lines else "(empty directory)"
    except PermissionError as exc:
        return str(exc)


@tool
def read_file(subpath: str) -> str:
    """Read the text content of a file inside the sandbox."""
    try:
        target = _safe_path(subpath)
        if not target.is_file():
            return f"'{subpath}' is not a file or does not exist."
        return target.read_text(encoding="utf-8")
    except PermissionError as exc:
        return str(exc)


@tool
def write_file(subpath: str, content: str) -> str:
    """Write (or overwrite) a text file inside the sandbox."""
    try:
        target = _safe_path(subpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Written {len(content)} characters to '{subpath}'."
    except PermissionError as exc:
        return str(exc)


# ── Agent runner ───────────────────────────────────────────────────────────────

_TOOLS = [list_directory, read_file, write_file]

_SYSTEM_PROMPT = (
    "You are a filesystem assistant with access to a sandboxed directory. "
    "Use the available tools to complete the user's objective step by step. "
    "When the task is done, give a concise final summary of what you did."
)


def run_filesystem_agent(objective: str) -> dict:
    """
    Run the filesystem agent (LangChain 1.x create_agent API).
    Returns: {"output": str, "steps": list[{"tool": str, "input": dict, "output": str}]}
    """
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    agent  = create_agent(llm, tools=_TOOLS, system_prompt=_SYSTEM_PROMPT)
    result = agent.invoke({"messages": [HumanMessage(content=objective)]})

    messages = result["messages"]

    # Extract tool-call steps from the message thread
    steps = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_output = next(
                    (
                        m.content
                        for m in messages
                        if isinstance(m, ToolMessage) and m.tool_call_id == tc["id"]
                    ),
                    "(no output)",
                )
                steps.append({
                    "tool":   tc["name"],
                    "input":  tc["args"],
                    "output": tool_output,
                })

    # Final answer: last AIMessage with no tool calls
    final_answer = next(
        (
            msg.content
            for msg in reversed(messages)
            if isinstance(msg, AIMessage) and not msg.tool_calls
        ),
        "Task completed.",
    )

    return {"output": final_answer, "steps": steps}
