"""
graphs.py — LangGraph definition for the Agentic RAG agent (module 02_01).

Graph topology (compiled once, reused across requests):

    START → llm_node ──(tool calls present)──→ tool_node ──→ llm_node
                     └──(no tool calls)───────→ END

State:
    messages    — accumulated chat messages (auto-appended via add_messages).
    step        — number of LLM calls made so far; guards against infinite loops.

The `max_steps` limit is enforced inside `llm_node`: when the step count reaches
the cap, a final AIMessage is returned without tool calls, causing the graph to
exit at the next conditional edge evaluation.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


# =============================================================================
# State definition
# =============================================================================

class RagState(TypedDict):
    """
    Mutable state threaded through every node of the RAG graph.

    Attributes:
        messages: Full message history (system + conversation + tool results).
                  The `add_messages` reducer handles appending automatically.
        step:     Number of LLM invocations so far; used to enforce max_steps.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    step: int


# =============================================================================
# Graph factory
# =============================================================================

def build_rag_graph(tools: list, llm: ChatOpenAI, max_steps: int) -> object:
    """
    Compile and return the agentic RAG LangGraph.

    This function is called once per process and the result is cached in
    services.py. Separating the graph definition from the tool/LLM
    construction avoids circular imports.

    Args:
        tools:     List of LangChain tool objects bound to the LLM.
        llm:       ChatOpenAI instance already configured with bind_tools().
        max_steps: Hard cap on LLM calls; enforced inside llm_node.

    Returns:
        A compiled LangGraph StateGraph ready to invoke.
    """

    # ── Node: llm_node ────────────────────────────────────────────────────────
    def llm_node(state: RagState) -> dict:
        """
        Invoke the LLM with the current message history.

        If max_steps has been reached, return a graceful degradation message
        instead of calling the LLM again. This prevents runaway loops from
        exhausting token budgets.
        """
        step = state.get("step", 0)

        if step >= max_steps:
            # Graceful exit: return a plain AIMessage so tools_condition routes to END.
            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"⚠ I reached the maximum search depth ({max_steps} steps) "
                            "without finding a conclusive answer. Based on the fragments "
                            "I did read, here is a partial summary — please narrow the "
                            "question or add more files to the knowledge base."
                        )
                    )
                ],
                "step": step,
            }

        response = llm.invoke(state["messages"])
        return {"messages": [response], "step": step + 1}

    # ── Node: tool_node ───────────────────────────────────────────────────────
    # ToolNode automatically routes all tool calls in the last AIMessage,
    # executes them in order, and appends ToolMessage results to state.
    tool_node = ToolNode(tools)

    # ── Graph assembly ────────────────────────────────────────────────────────
    graph = StateGraph(RagState)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "llm")

    # tools_condition: if last message has tool_calls → "tools", else → END
    graph.add_conditional_edges("llm", tools_condition, {"tools": "tools", END: END})

    # After tools execute, loop back to the LLM for the next reasoning step.
    graph.add_edge("tools", "llm")

    return graph.compile()
