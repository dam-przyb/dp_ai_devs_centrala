"""
proxy_verify_service.py
=======================
Automatic verification helper for Lesson 03 proxy mission.

Stores the latest verify attempt state in memory and extracts the final flag
token when present in the hub response payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any

import httpx
from django.conf import settings

from lesson_03.services.package_agent_service import extract_flag


_VERIFY_ENDPOINT = "https://hub.ag3nts.org/verify"
_DEFAULT_VERIFY_SESSION_ID = "proxy-session-001"


@dataclass
class VerifyState:
    """In-memory status of the latest proxy verify attempt."""

    status: str = "idle"
    session_id: str = _DEFAULT_VERIFY_SESSION_ID
    url: str = ""
    last_flag: str = ""
    last_error: str = ""
    attempted_at: str = ""
    response_json: dict[str, Any] = field(default_factory=dict)
    response_text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


_STATE = VerifyState()


def _now_iso() -> str:
    """Return UTC ISO timestamp used by verify state."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_verify_state() -> dict[str, Any]:
    """Return current verify snapshot as plain dict."""
    return {
        "status": _STATE.status,
        "session_id": _STATE.session_id,
        "url": _STATE.url,
        "last_flag": _STATE.last_flag,
        "last_error": _STATE.last_error,
        "attempted_at": _STATE.attempted_at,
        "response_json": _STATE.response_json,
        "response_text": _STATE.response_text,
        "payload": _STATE.payload,
    }


def submit_proxy_verify(*, public_url: str, session_id: str) -> dict[str, Any]:
    """
    Submit the proxy verify payload to hub and update local verify state.

    Args:
        public_url: Public endpoint URL to validate.
        session_id: Session ID sent in verification payload.

    Returns:
        Updated verify snapshot dict.
    """
    api_key = str(getattr(settings, "AIDEVS_API_KEY", "")).strip()
    if not api_key:
        _STATE.status = "error"
        _STATE.last_error = "AIDEVS_API_KEY is not configured."
        _STATE.attempted_at = _now_iso()
        return get_verify_state()

    payload = {
        "apikey": api_key,
        "task": "proxy",
        "answer": {
            "url": public_url,
            "sessionID": session_id,
        },
    }

    _STATE.status = "running"
    _STATE.attempted_at = _now_iso()
    _STATE.session_id = session_id
    _STATE.url = public_url
    _STATE.last_error = ""
    _STATE.last_flag = ""
    _STATE.payload = payload

    try:
        resp = httpx.post(_VERIFY_ENDPOINT, json=payload, timeout=90)
    except Exception as exc:
        _STATE.status = "error"
        _STATE.last_error = str(exc)
        _STATE.response_json = {}
        _STATE.response_text = ""
        return get_verify_state()

    parsed: dict[str, Any] = {}
    raw_text = resp.text
    try:
        parsed = resp.json() if isinstance(resp.json(), dict) else {}
    except Exception:
        parsed = {}

    text_blob = json.dumps(parsed, ensure_ascii=False) if parsed else raw_text
    flag = extract_flag(text_blob)

    _STATE.response_json = parsed
    _STATE.response_text = raw_text
    _STATE.last_flag = flag or ""

    if resp.status_code >= 400:
        _STATE.status = "error"
        _STATE.last_error = f"Verify returned status {resp.status_code}."
        return get_verify_state()

    if flag:
        _STATE.status = "success"
    else:
        _STATE.status = "done"
    return get_verify_state()
