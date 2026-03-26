"""
Quest views for Lesson 03 package proxy mission.

This phase wires:
- workspace UI shell,
- local probe endpoint for manual testing,
- public JSON proxy endpoint contract required by the task.
"""

from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from lesson_03.services.azyl_tunnel_service import (
    get_tunnel_snapshot,
    start_tunnel,
    stop_tunnel,
)
from lesson_03.services.package_agent_service import (
    get_conversation_snapshot,
    get_recent_runtime_events,
    get_runtime_snapshot,
    run_package_agent_turn,
)
from lesson_03.services.proxy_verify_service import get_verify_state, submit_proxy_verify

logger = logging.getLogger(__name__)


@require_GET
def quest_view(request: HttpRequest) -> HttpResponse:
    """Render Lesson 03 Quest workspace."""
    proxy_path = reverse("l03_proxy_endpoint")
    tunnel_snapshot = get_tunnel_snapshot()
    context = {
        "proxy_path": proxy_path,
        "proxy_url_preview": request.build_absolute_uri(proxy_path),
        "snapshot": get_runtime_snapshot(),
        "tunnel": tunnel_snapshot,
        "verify": get_verify_state(),
        "agent_events": get_recent_runtime_events(),
        "conversations": get_conversation_snapshot(),
    }
    return render(request, "lesson_03/quest.html", context)


@require_GET
def quest_status_api(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint returning runtime snapshot for the Quest panel."""
    return render(
        request,
        "lesson_03/partials/quest_status.html",
        {
            "snapshot": get_runtime_snapshot(),
            "tunnel": get_tunnel_snapshot(),
            "verify": get_verify_state(),
            "agent_events": get_recent_runtime_events(),
            "conversations": get_conversation_snapshot(),
        },
    )


@require_POST
def quest_tunnel_start_api(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint: start Azyl tunnel and re-render status panel."""
    defaults = get_tunnel_snapshot().get("defaults", {})

    user = request.POST.get("user", str(defaults.get("user", "")).strip()).strip()
    host = request.POST.get("host", str(defaults.get("host", "")).strip()).strip()
    verify_session_id = request.POST.get("verify_session_id", "proxy-session-001").strip()

    try:
        ssh_port = int(request.POST.get("ssh_port", defaults.get("ssh_port", 5022)))
        remote_port = int(request.POST.get("remote_port", defaults.get("remote_port", 50005)))
        local_port = int(request.POST.get("local_port", defaults.get("local_port", 8000)))
    except ValueError:
        return render(
            request,
            "lesson_03/partials/quest_status.html",
            {
                "snapshot": get_runtime_snapshot(),
                "tunnel": get_tunnel_snapshot(),
                "status_message": "Port values must be integers.",
                "verify": get_verify_state(),
                "agent_events": get_recent_runtime_events(),
                "conversations": get_conversation_snapshot(),
            },
        )

    start_tunnel(
        user=user,
        host=host,
        ssh_port=ssh_port,
        remote_port=remote_port,
        local_port=local_port,
    )

    tunnel = get_tunnel_snapshot()
    tunnel_state = tunnel.get("state", {})
    if tunnel_state.get("status") == "running" and tunnel_state.get("public_url"):
        endpoint_url = f"{str(tunnel_state.get('public_url')).rstrip('/')}{reverse('l03_proxy_endpoint')}"
        submit_proxy_verify(
            public_url=endpoint_url,
            session_id=verify_session_id,
        )

    return render(
        request,
        "lesson_03/partials/quest_status.html",
        {
            "snapshot": get_runtime_snapshot(),
            "tunnel": get_tunnel_snapshot(),
            "verify": get_verify_state(),
            "agent_events": get_recent_runtime_events(),
            "conversations": get_conversation_snapshot(),
        },
    )


@require_POST
def quest_tunnel_stop_api(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint: stop Azyl tunnel and re-render status panel."""
    stop_tunnel()
    return render(
        request,
        "lesson_03/partials/quest_status.html",
        {
            "snapshot": get_runtime_snapshot(),
            "tunnel": get_tunnel_snapshot(),
            "verify": get_verify_state(),
            "agent_events": get_recent_runtime_events(),
            "conversations": get_conversation_snapshot(),
        },
    )


@require_POST
def quest_verify_retry_api(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint: manually re-run proxy verify with current URL/session."""
    tunnel_state = get_tunnel_snapshot().get("state", {})
    public_url = request.POST.get("public_url", "").strip()
    if not public_url and tunnel_state.get("public_url"):
        public_url = f"{str(tunnel_state.get('public_url')).rstrip('/')}{reverse('l03_proxy_endpoint')}"
    session_id = request.POST.get("verify_session_id", "proxy-session-001").strip()

    if public_url:
        submit_proxy_verify(public_url=public_url, session_id=session_id)

    return render(
        request,
        "lesson_03/partials/quest_status.html",
        {
            "snapshot": get_runtime_snapshot(),
            "tunnel": get_tunnel_snapshot(),
            "verify": get_verify_state(),
            "agent_events": get_recent_runtime_events(),
            "conversations": get_conversation_snapshot(),
        },
    )


@require_POST
def quest_probe_api(request: HttpRequest) -> HttpResponse:
    """
HTMX probe endpoint for manual local testing from the Quest UI.

    Expected POST fields:
        session_id (str)
        msg (str)
    """
    session_id = request.POST.get("session_id", "").strip()
    message = request.POST.get("msg", "").strip()
    if not session_id or not message:
        return render(
            request,
            "lesson_03/partials/quest_probe_result.html",
            {"error": "Provide both session_id and msg."},
        )

    try:
        result = run_package_agent_turn(session_id=session_id, operator_message=message, source="probe")
        return render(
            request,
            "lesson_03/partials/quest_probe_result.html",
            {"data": result},
        )
    except Exception as exc:
        logger.exception("quest_probe_api failed: %s", exc)
        return render(
            request,
            "lesson_03/partials/quest_probe_result.html",
            {"error": str(exc)},
        )


@csrf_exempt
@require_POST
def proxy_endpoint_api(request: HttpRequest) -> JsonResponse:
    """
Public proxy endpoint contract required by the task.

Input JSON:
    {
      "sessionID": "any-session-id",
      "msg": "operator message"
    }

Output JSON:
    {
      "msg": "assistant response"
    }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse(
            {"msg": "Invalid JSON payload."},
            status=400,
        )

    session_id = str(payload.get("sessionID", "")).strip()
    message = str(payload.get("msg", "")).strip()

    if not session_id or not message:
        return JsonResponse(
            {"msg": "Both sessionID and msg are required."},
            status=400,
        )

    try:
        result = run_package_agent_turn(session_id=session_id, operator_message=message, source="proxy")
        return JsonResponse({"msg": result.reply})
    except Exception as exc:
        logger.exception("proxy_endpoint_api failed: %s", exc)
        return JsonResponse(
            {"msg": "Temporary processing error. Please retry."},
            status=500,
        )
