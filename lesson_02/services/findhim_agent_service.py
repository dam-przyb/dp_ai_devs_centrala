"""
findhim_agent_service.py
========================
Supervisor-driven tool agent for the S01E02 "findhim" quest.
"""

import json
import math
from pathlib import Path
from typing import Any

import httpx
from django.conf import settings
from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

# =============================================================================
# Module configuration
# =============================================================================

# Set explicit model here for this module only.
# Keep empty string to use the module default below.
FINDHIM_MODEL_OVERRIDE = ""
DEFAULT_FINDHIM_MODEL = "openai/gpt-5.4-mini"
MAX_AGENT_ITERATIONS = 12

_TASK_DIR = Path(__file__).resolve().parent.parent / "0102task_context"
_HUB_BASE = "https://hub.ag3nts.org"

_PLANT_COORDS: dict[str, tuple[float, float]] = {
    "Grudziądz": (53.4836, 18.7536),
    "Zabrze": (50.3249, 18.7857),
    "Piotrków Trybunalski": (51.4060, 19.7041),
    "Tczew": (54.0952, 18.7774),
    "Radom": (51.4027, 21.1471),
    "Chelmno": (53.3511, 18.4238),
    "Żarnowiec": (54.7039, 18.1408),
}


# =============================================================================
# Data and HTTP helpers
# =============================================================================

def _api_key() -> str:
    """Return AI Devs API key or raise a clear configuration error."""
    key = getattr(settings, "AIDEVS_API_KEY", "")
    if not key:
        raise RuntimeError("AIDEVS_API_KEY is not set. Configure AIDEVSKEY in .env.")
    return key


def _resolve_model(model: str | None = None) -> str:
    """Resolve model with explicit module override, then argument, then default."""
    return (FINDHIM_MODEL_OVERRIDE or model or DEFAULT_FINDHIM_MODEL).strip()


def _safe_json(resp: httpx.Response) -> Any:
    """Parse JSON safely; return None for non-JSON responses."""
    try:
        return resp.json()
    except Exception:
        return None


def _post_json(
    *,
    endpoint: str,
    payload: dict,
    timeout: int,
    api_log: list[dict],
) -> tuple[int, Any, str]:
    """POST JSON, append structured API log entry, and return status/body."""
    try:
        resp = httpx.post(f"{_HUB_BASE}{endpoint}", json=payload, timeout=timeout)
        parsed = _safe_json(resp)
        text = resp.text
        api_log.append(
            {
                "endpoint": endpoint,
                "request": payload,
                "status_code": resp.status_code,
                "response_json": parsed,
                "response_text": text,
            }
        )
        return resp.status_code, parsed, text
    except Exception as exc:
        api_log.append(
            {
                "endpoint": endpoint,
                "request": payload,
                "status_code": None,
                "response_json": None,
                "response_text": "",
                "error": str(exc),
            }
        )
        raise RuntimeError(f"Request to {endpoint} failed: {exc}") from exc


def _load_suspects() -> list[dict]:
    """Load suspect list from S01E01 output file."""
    data = json.loads((_TASK_DIR / "suspect_list.json").read_text(encoding="utf-8"))
    suspects = data.get("answer", data) if isinstance(data, dict) else data
    if not isinstance(suspects, list):
        raise RuntimeError("suspect_list.json must contain a list of suspects.")
    return suspects


def _load_plants() -> dict[str, dict]:
    """Load power plant list and enrich each item with configured coordinates."""
    raw = json.loads((_TASK_DIR / "powerplants.json").read_text(encoding="utf-8"))
    plants_raw = raw.get("power_plants", {})
    if not isinstance(plants_raw, dict):
        raise RuntimeError("powerplants.json must contain 'power_plants' object.")
    out: dict[str, dict] = {}
    for city, info in plants_raw.items():
        lat, lon = _PLANT_COORDS.get(city, (None, None))
        out[city] = {**info, "lat": lat, "lon": lon}
    return out


def _extract_coords(location_payload: Any) -> list[tuple[float, float]]:
    """
    Normalize location response to [(lat, lon), ...].

    Supports both key variants:
    - lat/lon
    - latitude/longitude
    """
    if isinstance(location_payload, list):
        records = location_payload
    elif isinstance(location_payload, dict):
        records = location_payload.get("locations", [])
    else:
        records = []

    coords: list[tuple[float, float]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        lat = item.get("lat", item.get("latitude"))
        lon = item.get("lon", item.get("longitude"))
        if lat is None or lon is None:
            continue
        try:
            coords.append((float(lat), float(lon)))
        except (TypeError, ValueError):
            continue
    return coords


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers."""
    earth_radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# =============================================================================
# Main runner
# =============================================================================

def run_findhim_agent(model: str | None = None) -> dict:
    """
    Run supervisor-driven tool loop for findhim.

    Returns:
        dict with output, steps, answer_path, search_summary, api_log.
    """
    suspects = _load_suspects()
    plants = _load_plants()
    api_log: list[dict] = []
    runtime: dict[str, Any] = {"search_summary": ""}

    @tool
    def identify_closest_suspect() -> str:
        """
        Find suspect closest to any known power plant using location API and Haversine.

        Returns JSON:
        {
          "name": str,
          "surname": str,
          "birthYear": int,
          "powerPlant": str,
          "plantCity": str,
          "distanceKm": float
        }
        """
        best: dict[str, Any] = {"distanceKm": float("inf")}
        total_points = 0

        for suspect in suspects:
            payload = {
                "apikey": _api_key(),
                "name": suspect["name"],
                "surname": suspect["surname"],
            }
            status, data, body = _post_json(
                endpoint="/api/location",
                payload=payload,
                timeout=15,
                api_log=api_log,
            )
            if status >= 400:
                raise RuntimeError(
                    f"/api/location failed for {suspect['name']} {suspect['surname']} "
                    f"(status {status}): {body}"
                )

            coords = _extract_coords(data)
            total_points += len(coords)

            for lat, lon in coords:
                for city, plant in plants.items():
                    if plant["lat"] is None or plant["lon"] is None:
                        continue
                    distance_km = _haversine(lat, lon, plant["lat"], plant["lon"])
                    if distance_km < best["distanceKm"]:
                        best = {
                            "name": suspect["name"],
                            "surname": suspect["surname"],
                            "birthYear": int(suspect["born"]),
                            "powerPlant": plant["code"],
                            "plantCity": city,
                            "distanceKm": round(distance_km, 4),
                        }

        if best["distanceKm"] == float("inf"):
            raise RuntimeError(
                "No valid GPS coordinates from /api/location. "
                "Check API response format (lat/lon vs latitude/longitude)."
            )

        runtime["search_summary"] = (
            f"Closest match: {best['name']} {best['surname']} — "
            f"{best['distanceKm']:.2f} km from plant {best['powerPlant']} "
            f"({best['plantCity']}); parsed points: {total_points}"
        )
        return json.dumps(best, ensure_ascii=False)

    @tool
    def get_access_level(name: str, surname: str, birth_year: int) -> str:
        """Get suspect access level from /api/accesslevel and return JSON response."""
        payload = {
            "apikey": _api_key(),
            "name": name,
            "surname": surname,
            "birthYear": int(birth_year),
        }
        status, data, body = _post_json(
            endpoint="/api/accesslevel",
            payload=payload,
            timeout=15,
            api_log=api_log,
        )
        if status >= 400:
            raise RuntimeError(f"/api/accesslevel failed (status {status}): {body}")
        if not isinstance(data, dict):
            raise RuntimeError(f"/api/accesslevel returned non-JSON body: {body}")
        return json.dumps(data, ensure_ascii=False)

    @tool
    def submit_answer(name: str, surname: str, access_level: int, power_plant: str) -> str:
        """Submit final payload to /verify and return response text."""
        payload = {
            "apikey": _api_key(),
            "task": "findhim",
            "answer": {
                "name": name,
                "surname": surname,
                "accessLevel": int(access_level),
                "powerPlant": power_plant,
            },
        }
        answer_path = _TASK_DIR / "answer.json"
        answer_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        status, _, body = _post_json(
            endpoint="/verify",
            payload=payload,
            timeout=20,
            api_log=api_log,
        )
        if status >= 400:
            return (
                f"ERROR {status} from /verify. "
                f"Payload sent: {json.dumps(payload['answer'], ensure_ascii=False)}. "
                f"Server response: {body}"
            )
        return body

    tools = [identify_closest_suspect, get_access_level, submit_answer]
    tool_map = {t.name: t for t in tools}

    supervisor_prompt = (
        "You are the FindHim supervisor agent.\n"
        "Your task is to solve quest 'findhim' strictly via tools.\n"
        "You must execute exactly this sequence:\n"
        "1) Call identify_closest_suspect once.\n"
        "2) From its JSON result, call get_access_level(name, surname, birth_year) once.\n"
        "3) From both results, call submit_answer(name, surname, access_level, power_plant) once.\n"
        "Rules:\n"
        "- Do not invent or modify suspect identity, birth year, or power plant code.\n"
        "- Use access level exactly as returned by get_access_level.\n"
        "- After submit_answer, return only a short final status with flag or error.\n"
    )

    llm = ChatOpenAI(
        model=_resolve_model(model),
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0,
    ).bind_tools(tools)

    messages: list[Any] = [
        {"role": "system", "content": supervisor_prompt},
        HumanMessage(content="Start solving findhim now."),
    ]
    steps: list[dict] = []
    final_output = "Task completed."

    for iteration in range(MAX_AGENT_ITERATIONS):
        response = llm.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            final_output = str(response.content)
            break

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            tool_obj = tool_map.get(tool_name)
            if not tool_obj:
                tool_output = f"Unknown tool requested: {tool_name}"
            else:
                try:
                    tool_output = tool_obj.invoke(tool_args)
                except Exception as exc:
                    tool_output = f"ERROR executing {tool_name}: {exc}"

            steps.append(
                {
                    "iteration": iteration + 1,
                    "tool": tool_name,
                    "input": tool_args,
                    "output": tool_output,
                }
            )
            messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))
    else:
        final_output = f"Agent reached max iterations ({MAX_AGENT_ITERATIONS})."

    return {
        "output": final_output,
        "steps": steps,
        "answer_path": str(_TASK_DIR / "answer.json"),
        "search_summary": runtime["search_summary"],
        "api_log": api_log,
    }
