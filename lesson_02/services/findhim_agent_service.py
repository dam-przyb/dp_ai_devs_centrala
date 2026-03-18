"""
findhim_agent_service.py
========================
Hybrid investigation service for the S01E02 "findhim" task.

Architecture
------------
Phase 1 — Pure Python (deterministic):
  • Fetch GPS sightings for ALL suspects via /api/location
  • Calculate Haversine distances to every power plant
  • Identify the (suspect, plant) pair with the minimum distance

Phase 2 — LLM agent (Function Calling):
  • get_access_level  — POST /api/accesslevel for the identified suspect
  • submit_answer     — POST /verify, save answer.json, return flag

Why Python handles Phase 1:
  The LLM must call haversine_distance 5 suspects × 7 plants × N sightings
  times and track a global minimum — a task that small models routinely fail
  by anchoring on the first promising result. Python does it in a tight loop
  with no risk of reasoning drift.

Why coordinates are hardcoded:
  The findhim_locations.json API returns only {code, is_active, power} per
  site — no GPS coordinates. We supply city-centre approximations (±1 km).
"""

import json
import math
from pathlib import Path

import httpx
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage

# =============================================================================
# Constants & static data
# =============================================================================

_TASK_DIR = Path(__file__).resolve().parent.parent / "0102task_context"
_HUB_BASE = "https://hub.ag3nts.org"

# City-centre GPS coordinates for each power plant location.
# Source: findhim_locations.json has NO coordinates — only codes and power
# ratings. These are manually looked-up city-centre approximations (±1 km).
_PLANT_COORDS: dict[str, tuple[float, float]] = {
    "Grudziądz":             (53.4836, 18.7536),
    "Zabrze":                (50.3249, 18.7857),
    "Piotrków Trybunalski":  (51.4060, 19.7041),
    "Tczew":                 (54.0952, 18.7774),
    "Radom":                 (51.4027, 21.1471),
    "Chelmno":               (53.3511, 18.4238),
    "Żarnowiec":             (54.7039, 18.1408),
}

MAX_AGENT_ITERATIONS = 10


# =============================================================================
# Phase 1 — Pure-Python helpers (deterministic, no LLM involved)
# =============================================================================

def _api_key() -> str:
    """Return the AI Devs API key; raise clearly if missing."""
    key = getattr(settings, "AIDEVS_API_KEY", "")
    if not key:
        raise RuntimeError(
            "AIDEVS_API_KEY is not set. "
            "Please configure the AIDEVSKEY environment variable."
        )
    return key


def _load_suspects() -> list[dict]:
    """Load the suspect list saved from S01E01."""
    raw = (_TASK_DIR / "suspect_list.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict) and "answer" in data:
        return data["answer"]
    return data


def _load_plants() -> dict[str, dict]:
    """
    Load powerplants.json and enrich each entry with lat/lon coordinates.

    Returns a dict keyed by city name:
      {city: {code, is_active, power, lat, lon}}
    """
    raw = (_TASK_DIR / "powerplants.json").read_text(encoding="utf-8")
    plants_raw: dict = json.loads(raw).get("power_plants", {})
    result = {}
    for city, info in plants_raw.items():
        lat, lon = _PLANT_COORDS.get(city, (None, None))
        result[city] = {**info, "lat": lat, "lon": lon}
    return result


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two GPS points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fetch_all_sightings(suspects: list[dict]) -> dict[tuple, list[tuple]]:
    """
    POST /api/location for every suspect and return a map of sightings.

    Returns:
        {(name, surname): [(lat, lon), ...]}
    """
    result: dict[tuple, list[tuple]] = {}
    key = _api_key()
    for s in suspects:
        resp = httpx.post(
            f"{_HUB_BASE}/api/location",
            json={"apikey": key, "name": s["name"], "surname": s["surname"]},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # API may return a plain list or a dict like {"locations": [...]}
        raw_locs = data if isinstance(data, list) else data.get("locations", [])
        coords = [
            (float(loc["lat"]), float(loc["lon"]))
            for loc in raw_locs
            if "lat" in loc and "lon" in loc
        ]
        result[(s["name"], s["surname"])] = coords
    return result


def _find_closest_to_plant(
    sightings: dict[tuple, list[tuple]],
    plants: dict[str, dict],
) -> tuple[str, str, str, float]:
    """
    Iterate every sighting × every plant and return the best match.

    Returns:
        (name, surname, plant_code, distance_km)
    """
    best_name = best_surname = best_code = ""
    best_dist = float("inf")

    for (name, surname), coords in sightings.items():
        for lat, lon in coords:
            for city, plant in plants.items():
                if plant["lat"] is None or plant["lon"] is None:
                    continue
                dist = _haversine(lat, lon, plant["lat"], plant["lon"])
                if dist < best_dist:
                    best_dist = dist
                    best_name = name
                    best_surname = surname
                    best_code = plant["code"]

    return best_name, best_surname, best_code, best_dist


# =============================================================================
# Phase 2 — LLM agent tools (access level + submission only)
# =============================================================================

@tool
def get_access_level(name: str, surname: str, birth_year: int) -> str:
    """
    Retrieve the access level for a suspect from the hub access-level API.

    Args:
        name (str): Suspect's first name.
        surname (str): Suspect's surname.
        birth_year (int): Year of birth as an integer (e.g. 1987).

    Returns:
        str: JSON-encoded response containing accessLevel, or an error message.
    """
    try:
        resp = httpx.post(
            f"{_HUB_BASE}/api/accesslevel",
            json={
                "apikey": _api_key(),
                "name": name,
                "surname": surname,
                "birthYear": int(birth_year),
            },
            timeout=15,
        )
        resp.raise_for_status()
        return json.dumps(resp.json())
    except Exception as exc:
        return f"ERROR fetching access level for {name} {surname}: {exc}"


@tool
def submit_answer(name: str, surname: str, access_level: int, power_plant: str) -> str:
    """
    Submit the findhim answer to the verification endpoint.

    answer.json is written BEFORE the POST so the file always reflects exactly
    what was sent, even if the request fails.

    Args:
        name (str): Suspect's first name.
        surname (str): Suspect's surname.
        access_level (int): Access level from /api/accesslevel.
        power_plant (str): Power plant code (format PWR0000PL).

    Returns:
        str: Full server response body (flag if correct, error detail if not).
    """
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

    # Save BEFORE posting — file always matches what was actually sent
    answer_path = _TASK_DIR / "answer.json"
    answer_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        resp = httpx.post(f"{_HUB_BASE}/verify", json=payload, timeout=20)
        body = resp.text
        if resp.status_code >= 400:
            return (
                f"ERROR {resp.status_code} from /verify. "
                f"Payload sent: {json.dumps(payload['answer'])}. "
                f"Server response: {body}"
            )
        return body
    except Exception as exc:
        return (
            f"ERROR submitting answer: {exc}. "
            f"Payload was: {json.dumps(payload['answer'])}"
        )


# =============================================================================
# Main runner
# =============================================================================

_AGENT_TOOLS = [get_access_level, submit_answer]


def run_findhim_agent(model: str | None = None) -> dict:
    """
    Execute the findhim investigation using a hybrid approach.

    Phase 1 (Python): fetch all sightings, calculate all distances, find winner.
    Phase 2 (LLM):    retrieve access level and submit the answer.

    Args:
        model (str | None): OpenRouter model string to use for Phase 2.
            Defaults to settings.FINDHIM_MODEL.

    Returns:
        dict: {
            "output": str,          # final agent answer
            "steps": list[dict],    # tool call trace (Phase 2 only)
            "answer_path": str,     # path to saved answer.json
            "search_summary": str,  # Phase 1 result summary
        }
    """
    suspects = _load_suspects()
    plants = _load_plants()
    chosen_model = model or getattr(settings, "FINDHIM_MODEL", "openai/gpt-4o")

    # ── Phase 1: deterministic search ────────────────────────────────────────
    sightings = _fetch_all_sightings(suspects)
    target_name, target_surname, plant_code, distance_km = _find_closest_to_plant(
        sightings, plants
    )

    # Look up birth year for the winner from the suspects list
    target_suspect = next(
        (s for s in suspects
         if s["name"] == target_name and s["surname"] == target_surname),
        None,
    )
    birth_year = target_suspect["born"] if target_suspect else 0

    search_summary = (
        f"Closest match: {target_name} {target_surname} "
        f"— {distance_km:.2f} km from plant {plant_code} "
        f"(born {birth_year})"
    )

    # ── Phase 2: LLM agent for access level + submission ─────────────────────
    llm = ChatOpenAI(
        model=chosen_model,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0,
    ).bind_tools(_AGENT_TOOLS)

    system_prompt = (
        "You are a reporting assistant. The investigation has already identified "
        "the suspect and the power plant. Your only job is:\n"
        "1. Call get_access_level(name, surname, birth_year) exactly once.\n"
        "2. Call submit_answer(name, surname, access_level, power_plant) with the "
        "result.\n"
        "3. Report the flag or error you received.\n"
        "Do not change the name, surname, or power plant code you are given."
    )

    human_msg = (
        f"Target suspect: {target_name} {target_surname} (born {birth_year}).\n"
        f"Power plant code: {plant_code}.\n"
        "Please retrieve their access level and submit the answer now."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        HumanMessage(content=human_msg),
    ]

    steps: list[dict] = []
    final_answer = "Task completed."

    for iteration in range(MAX_AGENT_ITERATIONS):
        response = llm.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            final_answer = response.content
            break

        for tc in response.tool_calls:
            tool_fn = next((t for t in _AGENT_TOOLS if t.name == tc["name"]), None)
            tool_output = tool_fn.invoke(tc["args"]) if tool_fn else f"Unknown tool: {tc['name']}"

            steps.append({
                "iteration": iteration + 1,
                "tool":      tc["name"],
                "input":     tc["args"],
                "output":    tool_output,
            })
            messages.append(ToolMessage(content=str(tool_output), tool_call_id=tc["id"]))
    else:
        final_answer = (
            f"Agent reached the maximum iteration limit ({MAX_AGENT_ITERATIONS})."
        )

    return {
        "output":         final_answer,
        "steps":          steps,
        "answer_path":    str(_TASK_DIR / "answer.json"),
        "search_summary": search_summary,
    }

