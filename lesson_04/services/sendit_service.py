"""
sendit_service.py
=================
LLM agent that fills and submits the SPK (System Przesyłek Konduktorskich)
transport declaration for the "sendit" AI Devs challenge.

Flow:
  1. Parse index.md locally and extract all [include file="..."] references.
  2. For each referenced file:
     - Text files (.md) → fetched from https://hub.ag3nts.org/dane/doc/{filename}
     - Image files (.png etc.) → fetched as bytes + analyzed by gpt-4o vision
  3. Build full documentation context (index.md + all fetched companion files).
  4. Run a tool-calling LLM agent that:
       a. Uses the full context to fill the exact declaration template.
       b. POSTs to /verify with the filled declaration.
       c. On hub rejection: reads the error message and retries (max 3 attempts).
  5. Log all actions to 0104task_context/log.json for debugging and audit.
  6. Return a structured result dict consumed by the view/template.

Key design decisions:
  - Vision model (gpt-4o) is used only for extracting text from image attachments;
    the main reasoning agent also uses gpt-4o for strong instruction-following.
  - Submission retry loop is driven by the agent itself: after each rejection the
    hub's error message is fed back so the LLM can self-correct.
  - The log.json is written after every action, so it reflects partial state even
    if the agent crashes mid-run — useful for manual investigation.
"""

import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from django.conf import settings
from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

# =============================================================================
# Configuration
# =============================================================================

# gpt-4o is used for both reasoning and vision — strong instruction following
# required for exact template formatting
SENDIT_MODEL = "openai/gpt-4o"
VISION_MODEL = "openai/gpt-4o"

MAX_SUBMISSION_ATTEMPTS = 3
MAX_AGENT_ITERATIONS = 25

_TASK_DIR = Path(__file__).resolve().parent.parent / "0104task_context"
_INDEX_PATH = _TASK_DIR / "index.md"
_LOG_PATH = _TASK_DIR / "log.json"

_HUB_BASE = "https://hub.ag3nts.org"
_DOC_BASE_URL = f"{_HUB_BASE}/dane/doc"

# Fixed shipment parameters from the task specification
_SHIPMENT: dict[str, Any] = {
    "sender_id": "450202122",
    "origin": "Gdańsk",
    "destination": "Żarnowiec",
    "weight_kg": 2800,
    "content": "kasety z paliwem do reaktora",
    "special_notes": None,   # explicitly forbidden - do not add any
    "budget_pp": 0,
}


# =============================================================================
# Internal helpers
# =============================================================================

def _api_key() -> str:
    """
    Return the AI Devs API key from Django settings.

    Raises:
        RuntimeError: If AIDEVS_API_KEY / AIDEVSKEY env var is not configured.
    """
    key = getattr(settings, "AIDEVS_API_KEY", "")
    if not key:
        raise RuntimeError("AIDEVS_API_KEY is not set. Configure AIDEVSKEY in .env.")
    return key


def _llm(model: str = SENDIT_MODEL) -> ChatOpenAI:
    """
    Construct a LangChain ChatOpenAI client pointing at OpenRouter.

    Args:
        model: OpenRouter model identifier (e.g. 'openai/gpt-4o').

    Returns:
        Configured ChatOpenAI instance ready for invocation.
    """
    return ChatOpenAI(
        model=model,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0,  # deterministic output for exact template matching
    )


def _extract_include_files(text: str) -> list[str]:
    """
    Extract filenames from [include file="..."] directives in the documentation.

    The SPK index.md embeds companion file references in the format:
        [include file="zalacznik-E.md"]
    We collect all of them to fetch the complete documentation set.

    Args:
        text: Raw markdown content to scan.

    Returns:
        Ordered list of unique filenames referenced by include directives.
    """
    # Use a list to preserve document order while deduplicating
    seen: set[str] = set()
    result: list[str] = []
    for match in re.finditer(r'\[include file="([^"]+)"\]', text):
        fname = match.group(1)
        if fname not in seen:
            seen.add(fname)
            result.append(fname)
    return result


def _is_image(filename: str) -> bool:
    """Return True if the filename extension indicates a binary image format."""
    return Path(filename).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _fetch_text_doc(filename: str) -> str:
    """
    Fetch a text-based companion document from the hub.

    Constructs the URL as: {_DOC_BASE_URL}/{filename}

    Args:
        filename: Companion file name only (e.g. 'zalacznik-E.md').

    Returns:
        Raw UTF-8 text content on success, or an error description string.
    """
    url = f"{_DOC_BASE_URL}/{filename}"
    try:
        resp = httpx.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        return f"[ERROR fetching {filename} from {url}: {exc}]"


def _analyze_image_doc(filename: str) -> str:
    """
    Fetch an image companion document from the hub and extract its content
    using the gpt-4o vision model via OpenRouter.

    The image is base64-encoded and sent directly in the message payload so no
    separate storage or URL is needed.

    Args:
        filename: Image filename (e.g. 'trasy-wylaczone.png').

    Returns:
        Extracted text/table content from the image, or an error description.
    """
    url = f"{_DOC_BASE_URL}/{filename}"
    try:
        resp = httpx.get(url, timeout=20)
        resp.raise_for_status()
        image_bytes = resp.content
    except Exception as exc:
        return f"[ERROR fetching image {filename} from {url}: {exc}]"

    # Base64-encode for inline data URL in the message payload
    b64 = base64.b64encode(image_bytes).decode()
    suffix = Path(filename).suffix.lower()
    media_type = f"image/{suffix.lstrip('.')}" if suffix != ".jpg" else "image/jpeg"

    vision_llm = _llm(model=VISION_MODEL)
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    "This image is part of the SPK (System Przesyłek Konduktorskich) "
                    "railway transport system documentation. Please extract ALL visible "
                    "content: text, tables, route codes, station names, numbers, and any "
                    "other data. Preserve the structure as faithfully as possible using "
                    "markdown tables for tabular data and lists for enumerated items. "
                    "Do not summarise — extract everything verbatim."
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64}"},
            },
        ]
    )
    try:
        response = vision_llm.invoke([message])
        return f"[Content extracted from image: {filename}]\n\n{response.content}"
    except Exception as exc:
        return f"[ERROR running vision model on {filename}: {exc}]"


def _append_log(log: list[dict], entry: dict) -> None:
    """
    Append a timestamped entry to the in-memory action log.

    Args:
        log: Mutable log list accumulated throughout the run.
        entry: Dict of fields describing the action taken.
    """
    log.append({**entry, "ts": datetime.now(timezone.utc).isoformat()})


def _save_log(log: list[dict]) -> None:
    """
    Persist the full action log to log.json in the task context folder.

    Written after every significant event so partial logs exist even on crash.
    """
    _LOG_PATH.write_text(
        json.dumps(log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# =============================================================================
# Main runner
# =============================================================================

def run_sendit_agent() -> dict:
    """
    Execute the full SPK declaration workflow: fetch docs → fill form → submit.

    The agent is given the complete SPK documentation as context in its system
    prompt. Its only tool is submit_declaration(), which POSTs to the hub and
    returns the raw response. The agent reads that response and either stops
    (on success/flag) or self-corrects and retries up to MAX_SUBMISSION_ATTEMPTS.

    Returns:
        dict with the following keys:
          - flag (str | None): extracted {FLG:...} token if discovered
          - declaration (str | None): the last submitted declaration text
          - steps (list[dict]): per-iteration agent step summaries
          - fetched_docs (dict[str, str]): previews of companion files fetched
          - submissions (list[dict]): per-attempt submission details
          - log_path (str): absolute path to log.json
          - action_log (list[dict]): full in-memory log (for template rendering)
          - success (bool): True only if a flag was received
    """
    action_log: list[dict] = []

    # ─── Phase 1: Load local index.md ────────────────────────────────────────
    index_content = _INDEX_PATH.read_text(encoding="utf-8")
    _append_log(action_log, {
        "action": "load_local_index",
        "file": str(_INDEX_PATH),
        "char_count": len(index_content),
    })

    # ─── Phase 2: Discover all companion files referenced by [include] ────────
    include_files = _extract_include_files(index_content)
    _append_log(action_log, {
        "action": "discovered_includes",
        "files": include_files,
        "count": len(include_files),
    })

    # ─── Phase 3: Fetch each companion file (text or vision) ─────────────────
    fetched_docs: dict[str, str] = {}
    for filename in include_files:
        if _is_image(filename):
            _append_log(action_log, {"action": "fetching_image", "filename": filename})
            content = _analyze_image_doc(filename)
        else:
            _append_log(action_log, {"action": "fetching_text", "filename": filename})
            content = _fetch_text_doc(filename)

        fetched_docs[filename] = content
        _append_log(action_log, {
            "action": "fetched_ok",
            "filename": filename,
            "char_count": len(content),
            "preview": content[:120].replace("\n", " "),
        })

    # ─── Phase 4: Assemble complete documentation context ─────────────────────
    doc_sections = [f"=== MAIN DOCUMENTATION: index.md ===\n\n{index_content}"]
    for fname, fcontent in fetched_docs.items():
        doc_sections.append(f"\n\n{'=' * 60}\n=== COMPANION FILE: {fname} ===\n{'=' * 60}\n\n{fcontent}")
    full_docs = "\n".join(doc_sections)

    # ─── Phase 5: Build agent system prompt ───────────────────────────────────
    system_prompt = f"""You are a precise document-filling agent for the SPK (System Przesyłek Konduktorskich) railway transport system.

YOUR TASK: Fill and submit a transport declaration with the following exact shipment parameters:
  - Sender identifier (nadawca): {_SHIPMENT["sender_id"]}
  - Origin point (punkt nadawczy): {_SHIPMENT["origin"]}
  - Destination point (punkt docelowy): {_SHIPMENT["destination"]}
  - Weight: {_SHIPMENT["weight_kg"]} kg (2.8 tons)
  - Contents (zawartość): {_SHIPMENT["content"]}
  - Special notes (uwagi specjalne): NONE — leave blank or mark as "brak", never add any notes
  - Budget: {_SHIPMENT["budget_pp"]} PP — the shipment must cost zero or be System-funded

STEP-BY-STEP INSTRUCTIONS:
1. Find Załącznik E in the documentation — it contains the EXACT declaration template format.
   You MUST preserve the template's formatting, separators, field order, and all structural elements.

2. Determine the correct CATEGORY:
   - Read section 4 (Klasyfikacja przesyłek) carefully.
   - Reactor fuel cassettes ("kasety z paliwem do reaktora" / "ogniwa paliwowe") fall under Category A — Strategic.
   - Category A is funded by the System (0 PP base cost) — this meets the zero-budget requirement.
   - Only Category A and B units have authorisation to use normally blocked routes.

3. Determine the correct ROUTE CODE for Gdańsk → Żarnowiec:
   - Section 8.3 confirms that Żarnowiec routes are blocked under Directive 7.7.
   - However, section 8.3 explicitly states: "Trasy wyłączone mogą zostać wykorzystane jedynie
     przy realizacji przesłek kategorii A oraz B" — Category A MAY use blocked routes.
   - The blocked route codes are listed in the trasy-wylaczone.png companion file (extracted above).
   - Find the route code for the Gdańsk–Żarnowiec segment from that extracted content.

4. Calculate the fee:
   - Category A: base fee = 0 PP (paid by System).
   - With base fee 0, the total is 0 PP regardless of weight/distance surcharges.

5. Fill every field in the template from Załącznik E with the correct values.
   Do NOT add special notes — leave that field blank or write "brak" as the template directs.

6. Call submit_declaration with the complete filled declaration text.

7. If the hub returns an error:
   - Read it carefully — it will indicate exactly what is wrong.
   - Correct ONLY the identified issue and resubmit.
   - You have {MAX_SUBMISSION_ATTEMPTS} total submission attempts.

8. When the hub returns a flag ({"{FLG:...}"}), your task is complete.

COMPLETE SPK DOCUMENTATION:
{full_docs}
"""

    # ─── Phase 6: Set up submission tool and shared state ─────────────────────
    submissions: list[dict] = []
    flag_found: str | None = None
    final_declaration: str | None = None
    submission_state: dict[str, Any] = {"attempts": 0}

    @tool
    def submit_declaration(declaration: str) -> str:
        """
        Submit the filled SPK transport declaration to the verification hub.

        Posts the declaration to https://hub.ag3nts.org/verify as the 'answer.declaration'
        field. Returns the full hub response text — read it carefully to check for success
        or error details before retrying.

        Args:
            declaration: Complete text of the filled declaration, formatted exactly
                         as the template in Załącznik E. Must be a plain string with
                         original line breaks and separators preserved.

        Returns:
            Hub response as a plain string. Success responses contain {FLG:...}.
            Error responses describe what needs to be corrected.
        """
        nonlocal flag_found, final_declaration

        attempt_num = submission_state["attempts"] + 1
        submission_state["attempts"] = attempt_num

        payload = {
            "apikey": _api_key(),
            "task": "sendit",
            "answer": {"declaration": declaration},
        }

        log_entry: dict[str, Any] = {
            "action": "submit_declaration",
            "attempt": attempt_num,
            "declaration_char_count": len(declaration),
            "declaration_preview": declaration[:300].replace("\n", "↵"),
        }

        try:
            resp = httpx.post(f"{_HUB_BASE}/verify", json=payload, timeout=30)
            body = resp.text
            try:
                parsed = resp.json()
            except Exception:
                parsed = None

            log_entry.update({
                "status_code": resp.status_code,
                "response_json": parsed,
                "response_text": body[:600],
            })
            _append_log(action_log, log_entry)
            _save_log(action_log)

            submissions.append({
                "attempt": attempt_num,
                "declaration": declaration,
                "status_code": resp.status_code,
                "response": parsed or body,
                "response_text": body,
            })

            final_declaration = declaration

            # Search for the flag in the response body
            flag_match = re.search(r"\{FLG:[^}]+\}", body)
            if flag_match:
                flag_found = flag_match.group(0)

            return f"[Attempt {attempt_num}/{MAX_SUBMISSION_ATTEMPTS}] HTTP {resp.status_code}: {body}"

        except Exception as exc:
            log_entry.update({"error": str(exc), "status_code": None})
            _append_log(action_log, log_entry)
            _save_log(action_log)
            return f"[Attempt {attempt_num}/{MAX_SUBMISSION_ATTEMPTS}] Request failed: {exc}"

    # ─── Phase 7: Run the agent reasoning loop ────────────────────────────────
    tool_map = {"submit_declaration": submit_declaration}
    llm = _llm(model=SENDIT_MODEL).bind_tools([submit_declaration])

    messages: list[Any] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            "Please read the SPK documentation, determine the correct category and route code "
            "for the given shipment, fill the Załącznik E declaration template exactly, and "
            f"submit it. You have up to {MAX_SUBMISSION_ATTEMPTS} submission attempts. "
            "Start by locating Załącznik E in the documentation."
        )),
    ]

    _append_log(action_log, {"action": "agent_loop_start", "model": SENDIT_MODEL, "max_iterations": MAX_AGENT_ITERATIONS})
    _save_log(action_log)

    steps: list[dict] = []
    iteration = 0

    while iteration < MAX_AGENT_ITERATIONS:
        iteration += 1
        response = llm.invoke(messages)
        messages.append(response)

        # Summarise this reasoning step for the UI
        content_preview = ""
        if isinstance(response.content, str):
            content_preview = response.content[:300]
        elif isinstance(response.content, list):
            # Some models return structured content blocks
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    content_preview = block.get("text", "")[:300]
                    break

        step_entry: dict[str, Any] = {
            "iteration": iteration,
            "has_tool_calls": bool(response.tool_calls),
            "tool_calls": [tc["name"] for tc in (response.tool_calls or [])],
            "content_preview": content_preview,
        }
        steps.append(step_entry)
        _append_log(action_log, {"action": "agent_step", **step_entry})

        # Agent finished without requesting more tools — natural end
        if not response.tool_calls:
            _append_log(action_log, {"action": "agent_finished_naturally", "iteration": iteration})
            break

        # Stop if max attempts reached and no flag yet (avoid wasting API tokens)
        if submission_state["attempts"] >= MAX_SUBMISSION_ATTEMPTS and not flag_found:
            _append_log(action_log, {
                "action": "max_attempts_reached",
                "attempts": submission_state["attempts"],
            })
            break

        # Dispatch each tool call
        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn is None:
                tool_result = f"[ERROR] Unknown tool requested: {tc['name']}"
            else:
                tool_result = tool_fn.invoke(tc["args"])

            messages.append(
                ToolMessage(content=str(tool_result), tool_call_id=tc["id"])
            )

        # Exit early once the flag is confirmed
        if flag_found:
            _append_log(action_log, {"action": "flag_confirmed", "flag": flag_found})
            break

    # ─── Phase 8: Finalise log and return ─────────────────────────────────────
    _append_log(action_log, {
        "action": "run_complete",
        "total_iterations": iteration,
        "total_submissions": submission_state["attempts"],
        "flag_found": flag_found,
        "success": flag_found is not None,
    })
    _save_log(action_log)

    # Truncate fetched doc content for the response dict (full content is in log)
    fetched_docs_preview = {
        fname: (content[:600] + "\n…[truncated]" if len(content) > 600 else content)
        for fname, content in fetched_docs.items()
    }

    return {
        "flag": flag_found,
        "declaration": final_declaration,
        "steps": steps,
        "fetched_docs": fetched_docs_preview,
        "submissions": submissions,
        "log_path": str(_LOG_PATH),
        "action_log": action_log,
        "success": flag_found is not None,
    }
