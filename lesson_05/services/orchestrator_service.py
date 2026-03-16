"""
Orchestrator service — Master Supervisor Agent.

Classifies the user's intent via an OpenRouter LLM call, then delegates to
the appropriate sub-agent or service from earlier lessons.  This is the
culmination module that ties the whole Operation Center together.

Intent categories:
  chat   → Lesson 01 chat service
  tools  → Lesson 02 filesystem agent
  media  → Informational redirect to Lesson 04 modules
  mcp    → Informational redirect to Lesson 03 modules
"""

from __future__ import annotations

import json

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


# =============================================================================
# Constants
# =============================================================================

_INTENT_SYSTEM_PROMPT = """You are a routing assistant for an AI operations center called "Damian's Operation Center".

Given a user's message, classify their intent into exactly one of these categories:
- "chat"  : general conversation, question answering, explanations, writing
- "tools" : filesystem operations, file search, reading/writing files, code execution
- "media" : image generation, audio transcription, video generation, PDF report creation
- "mcp"   : model context protocol, tool discovery, external API via MCP server

Respond with ONLY a JSON object, no markdown fences:
{"intent": "<category>", "reasoning": "<one sentence explanation>"}"""

_INTENT_TO_LABEL: dict[str, str] = {
    "chat":  "💬 Chat Agent (Lesson 01)",
    "tools": "🔧 FS Tool Agent (Lesson 02)",
    "media": "🎨 Media Agent (Lesson 04)",
    "mcp":   "🔌 MCP Agent (Lesson 03)",
}


# =============================================================================
# LLM Helper
# =============================================================================

def _get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at OpenRouter."""
    return ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )


# =============================================================================
# Intent Classifier
# =============================================================================

def _classify_intent(user_input: str) -> tuple[str, str]:
    """
    Call the LLM router to classify the user's intent.

    Args:
        user_input: Raw message text from the user.

    Returns:
        Tuple of (intent_category, reasoning_sentence).
        Falls back to ("chat", "") on any error.
    """
    llm = _get_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=user_input),
        ])
        raw = response.content.strip()
        # Strip accidental markdown code fences
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        data = json.loads(raw)
        return data.get("intent", "chat"), data.get("reasoning", "")
    except Exception:
        # Non-retryable parsing failure — default to generic chat
        return "chat", "Defaulted to chat after classification error."


# =============================================================================
# Sub-Agent Handlers
# =============================================================================

def _handle_chat(user_input: str) -> str:
    """
    Delegate to a direct LLM chat completion.

    Mirrors lesson_01 interaction without storing the conversation in the
    ChatMessage model (the orchestrator provides a stateless one-shot answer).
    """
    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content="You are a helpful assistant named Damian's Assistant."),
        HumanMessage(content=user_input),
    ])
    return response.content


def _handle_tools(user_input: str) -> str:
    """
    Delegate to the lesson_02 filesystem agent.

    Reuses the agent service directly — no HTTP round-trip needed since we
    share the same Django process.  Returns a markdown-formatted result.
    """
    try:
        from lesson_02.services.filesystem_agent_service import run_filesystem_agent
        result = run_filesystem_agent(user_input)
        output = result.get("output", "Task completed.")
        steps  = result.get("steps", [])
        if steps:
            steps_md = "\n".join(
                f"- **{s['tool']}**: {s['output']}" for s in steps
            )
            return f"{output}\n\n**Steps taken:**\n{steps_md}"
        return output
    except Exception as exc:
        return f"⚠️ FS Agent error: {exc}"


def _handle_media(user_input: str) -> str:
    """
    Return a helpful redirect message for media-related requests.

    Full media generation requires file uploads or long-running jobs that
    must be accessed through their dedicated sidebar modules.
    """
    return (
        "🎨 **Media request detected.**\n\n"
        "Please use the dedicated modules in the sidebar for media tasks:\n"
        "- **Audio Transcription** → 04 — Media › Audio\n"
        "- **Image Generation** → 04 — Media › Image\n"
        "- **Video Generation** → 04 — Media › Video\n"
        "- **PDF Report** → 04 — Media › Report\n\n"
        f"*Your request:* {user_input}"
    )


def _handle_mcp(user_input: str) -> str:
    """
    Return a helpful redirect message for MCP-related requests.

    MCP requires an active MCP server process; use the dedicated modules.
    """
    return (
        "🔌 **MCP request detected.**\n\n"
        "Please use the MCP modules in the sidebar:\n"
        "- **MCP Core** → 03 — MCP › MCP Core\n"
        "- **MCP Translator** → 03 — MCP › MCP Translator\n"
        "- **Upload MCP** → 03 — MCP › Upload MCP\n\n"
        f"*Your request:* {user_input}"
    )


_HANDLERS = {
    "chat":  _handle_chat,
    "tools": _handle_tools,
    "media": _handle_media,
    "mcp":   _handle_mcp,
}


# =============================================================================
# Public API
# =============================================================================

def orchestrate(user_input: str) -> dict:
    """
    Master orchestrator entry point.

    Classifies the user's intent via LLM, then delegates to the appropriate
    sub-agent or service, and returns a unified response envelope.

    Args:
        user_input: The raw text message from the user.

    Returns:
        dict with keys:
            intent      (str)  — classified category
            agent_label (str)  — human-readable label of the agent used
            reasoning   (str)  — one-sentence LLM reasoning for the routing
            response    (str)  — the final answer / output text
    """
    intent, reasoning = _classify_intent(user_input)

    # Fall back gracefully for any unrecognised category
    handler  = _HANDLERS.get(intent, _handle_chat)
    response = handler(user_input)

    return {
        "intent":      intent,
        "agent_label": _INTENT_TO_LABEL.get(intent, "💬 Chat Agent"),
        "reasoning":   reasoning,
        "response":    response,
    }
