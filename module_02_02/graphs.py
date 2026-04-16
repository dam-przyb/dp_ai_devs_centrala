"""
LangGraph agent graph for module_02_02 Hybrid RAG.

Graph topology
--------------

    START
      │
      ▼
  llm_step  ──(tool_calls present)──▶  search_tool
      ▲                                      │
      └──────────────────────────────────────┘
      │
      └──(no tool_calls)──▶  END

The graph uses the standard LangChain/LangGraph `add_messages` reducer so
the full message history is available to the LLM on each turn.  A `step`
counter guards against runaway loops (hard cap at 20 iterations).

Usage
-----
    from module_02_02.graphs import build_hybrid_rag_graph
    graph = build_hybrid_rag_graph(tools=[search_tool], llm=llm)
    result = graph.invoke({"messages": messages, "step": 0})
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AnyMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from typing_extensions import TypedDict

# Maximum reasoning steps before the agent is forced to stop
_MAX_STEPS = 20


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class HybridRagState(TypedDict):
    """
    Shared state threaded through every node in the Hybrid RAG graph.

    Attributes:
        messages: Full conversation history; managed by the add_messages reducer.
        step:     Current iteration count — guards against infinite tool loops.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    step: int


# ---------------------------------------------------------------------------
# Node definitions
# ---------------------------------------------------------------------------

def _make_llm_node(llm_with_tools: ChatOpenAI, system_prompt: str):
    """
    Build the LLM reasoning node.

    The node prepends the system prompt on the first step, increments the
    step counter, and hard-stops the agent if max_steps is exceeded by
    injecting a final text response rather than another tool call.

    Args:
        llm_with_tools: LLM instance with the search tool bound.
        system_prompt:  System-level instruction injected at step 0.

    Returns:
        Callable node function compatible with StateGraph.
    """

    def llm_node(state: HybridRagState) -> dict[str, Any]:
        messages = list(state["messages"])
        step = state["step"]

        # Prepend system message on the very first step
        if step == 0:
            messages = [SystemMessage(content=system_prompt)] + messages

        if step >= _MAX_STEPS:
            # Force a graceful stop to avoid infinite loops
            stop_msg = AIMessage(
                content=(
                    "I have reached the maximum number of search iterations. "
                    "Based on the information gathered so far, here is my answer."
                )
            )
            return {"messages": [stop_msg], "step": step + 1}

        response = llm_with_tools.invoke(messages)
        return {"messages": [response], "step": step + 1}

    return llm_node


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_hybrid_rag_graph(
    tools: list[BaseTool],
    llm: ChatOpenAI,
    system_prompt: str,
) -> Any:
    """
    Compile and return the Hybrid RAG LangGraph.

    The graph follows the standard ReAct pattern:
        llm_step → (tool_calls?) → search_tool → llm_step → … → END

    Args:
        tools:         List of LangChain tools the LLM may call.
        llm:           ChatOpenAI instance (without tools bound).
        system_prompt: System prompt injected at the start of each conversation.

    Returns:
        A compiled LangGraph runnable.
    """
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    graph = StateGraph(HybridRagState)

    graph.add_node("llm_step", _make_llm_node(llm_with_tools, system_prompt))
    graph.add_node("search_tool", tool_node)

    graph.add_edge(START, "llm_step")
    graph.add_conditional_edges("llm_step", tools_condition, {
        "tools": "search_tool",
        END: END,
    })
    graph.add_edge("search_tool", "llm_step")

    return graph.compile()
