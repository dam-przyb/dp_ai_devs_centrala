from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage


# ── Fake weather backend (no real API needed for the demo) ────────────────────
_WEATHER_DATA = {
    "london":   "Cloudy, 14°C, wind 20 km/h NW",
    "paris":    "Sunny, 22°C, wind 10 km/h S",
    "new york": "Partly cloudy, 18°C, wind 15 km/h NE",
    "tokyo":    "Rainy, 16°C, wind 25 km/h E",
    "warsaw":   "Overcast, 10°C, wind 30 km/h W",
}


@tool
def get_weather(location: str) -> str:
    """Return the current weather for a given city or location."""
    key = location.lower().strip()
    return _WEATHER_DATA.get(key, f"Weather data not available for '{location}'.")


def run_weather_query(user_prompt: str) -> dict:
    """
    Manual tool-call loop:
      1. Call LLM with bound tool.
      2. If the LLM requests the tool, execute it.
      3. Feed result back, get final answer.
    Returns {"answer": str, "tool_called": bool, "tool_args": dict | None}.
    """
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    ).bind_tools([get_weather])

    messages = [HumanMessage(content=user_prompt)]
    response = llm.invoke(messages)

    if not response.tool_calls:
        return {"answer": response.content, "tool_called": False, "tool_args": None}

    # Execute every requested tool call (usually just one for weather)
    tool_call   = response.tool_calls[0]
    tool_result = get_weather.invoke(tool_call["args"])

    messages.append(response)
    messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

    final = llm.invoke(messages)
    return {
        "answer":      final.content,
        "tool_called": True,
        "tool_args":   tool_call["args"],
        "tool_result": tool_result,
    }
