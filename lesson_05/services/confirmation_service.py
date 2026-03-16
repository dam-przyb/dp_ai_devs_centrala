"""
Confirmation service — Human-in-the-Loop via LangGraph.

Builds a two-node graph:
  plan_action     → drafts an email action using the LLM
  send_email_node → simulates sending the email (mocked)

The graph is compiled with ``interrupt_before=["send_email_node"]``, so
execution halts after planning and waits for the user to approve or reject
the action via the Django UI.  State is persisted in db.sqlite3 using
``SqliteSaver`` so the thread survives across HTTP requests.
"""

from __future__ import annotations

import uuid
from typing import TypedDict

from django.conf import settings
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# =============================================================================
# State Schema
# =============================================================================

class ConfirmationState(TypedDict):
    """
    Shared state passed between graph nodes.

    Attributes:
        input:          The original task text supplied by the user.
        pending_action: The LLM-drafted email text awaiting approval.
        result:         The final outcome string (set after send_email_node runs).
    """
    input:          str
    pending_action: str
    result:         str


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
# Graph Nodes
# =============================================================================

def plan_action_node(state: ConfirmationState) -> ConfirmationState:
    """
    Ask the LLM to draft a short email based on the user's task.

    This node runs before the interrupt, so the drafted email is available
    for the user to review in the confirmation UI.
    """
    llm      = _get_llm()
    response = llm.invoke([
        HumanMessage(content=(
            f"Draft a short professional email based on this task: {state['input']}\n\n"
            "Format your response exactly as:\n"
            "To: <recipient>\n"
            "Subject: <subject>\n\n"
            "<email body>"
        ))
    ])
    return {**state, "pending_action": response.content}


def send_email_node(state: ConfirmationState) -> ConfirmationState:
    """
    Simulate sending the drafted email.

    In a real system this would call an SMTP or email-API client.
    Here we simply mark the action as completed.
    """
    # --- Mocked send: just return a success message ---
    return {
        **state,
        "result": f"✅ Email sent successfully.\n\n---\n{state['pending_action']}",
    }


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph():
    """
    Build and compile the LangGraph confirmation graph.

    The graph halts before ``send_email_node``, giving the user a chance to
    review the planned action.  The SQLite checkpointer persists the frozen
    state so that resumption across HTTP requests works correctly.

    Returns:
        A compiled LangGraph ``CompiledStateGraph`` instance.
    """
    # Import here to avoid top-level import errors if langgraph is not installed
    from langgraph.graph import END, StateGraph
    from langgraph.checkpoint.sqlite import SqliteSaver

    builder = StateGraph(ConfirmationState)
    builder.add_node("plan_action",     plan_action_node)
    builder.add_node("send_email_node", send_email_node)
    builder.set_entry_point("plan_action")
    builder.add_edge("plan_action",     "send_email_node")
    builder.add_edge("send_email_node", END)

    db_path = str(settings.BASE_DIR / "db.sqlite3")
    memory  = SqliteSaver.from_conn_string(db_path)

    return builder.compile(checkpointer=memory, interrupt_before=["send_email_node"])


# =============================================================================
# Public API
# =============================================================================

def start_confirmation(task: str) -> tuple[str, str]:
    """
    Initiate the graph with a user task.

    Runs the graph until the interrupt point (before send_email_node) and
    returns the thread_id and the LLM-planned action text so the Django view
    can render the approval UI.

    Args:
        task: Natural-language description of what to do (e.g. "Email John about the meeting").

    Returns:
        Tuple of (thread_id, pending_action_text).
    """
    graph     = build_graph()
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}
    state     = graph.invoke({"input": task, "pending_action": "", "result": ""}, config)

    # After interrupt_before the state contains the plan_action output
    pending = state.get("pending_action", "(no action drafted)")
    return thread_id, pending


def resume_confirmation(thread_id: str) -> str:
    """
    Resume the graph after user approval.

    Picks up from the frozen state identified by ``thread_id`` and runs
    ``send_email_node`` to completion.

    Args:
        thread_id: The UUID string returned by ``start_confirmation``.

    Returns:
        The final result string from ``send_email_node``.
    """
    graph  = build_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # Passing None resumes from the last checkpoint (after interrupt_before)
    state = graph.invoke(None, config)
    return state.get("result", "Task completed.")
