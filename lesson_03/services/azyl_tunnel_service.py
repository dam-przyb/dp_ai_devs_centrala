"""
azyl_tunnel_service.py
======================
In-memory tunnel lifecycle manager for Azyl reverse SSH exposure.

This service controls a single tunnel process for the local Django server.
State and logs are intentionally process-local for this educational dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import shutil
import subprocess
import threading
import time
from typing import Any

from django.conf import settings


# =============================================================================
# Constants and runtime state
# =============================================================================

_DEFAULT_AZYL_HOST = "azyl.ag3nts.org"
_DEFAULT_AZYL_PORT = 5022
_DEFAULT_AZYL_USER = "agent17194"
_DEFAULT_LOCAL_PORT = 8000
_DEFAULT_REMOTE_PORT = 50005
_DEFAULT_AZYL_HOSTKEY = "SHA256:7bCukO6qZRas8bmQUVdYoobQJ0tXQ+HVh75aDUKtNrM"

_LOCK = threading.RLock()
_PROCESS: subprocess.Popen | None = None


@dataclass
class TunnelEvent:
    """Single tunnel event row for UI diagnostics."""

    level: str
    message: str
    at: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class TunnelState:
    """Current in-memory tunnel lifecycle snapshot."""

    status: str = "stopped"
    public_url: str = ""
    user: str = ""
    host: str = ""
    ssh_port: int = _DEFAULT_AZYL_PORT
    remote_port: int = _DEFAULT_REMOTE_PORT
    local_port: int = _DEFAULT_LOCAL_PORT
    pid: int | None = None
    started_at: str = ""
    last_error: str = ""
    command_preview: str = ""


_STATE = TunnelState(
    user=_DEFAULT_AZYL_USER,
    host=_DEFAULT_AZYL_HOST,
)
_EVENTS: list[TunnelEvent] = []


# =============================================================================
# Helpers
# =============================================================================

def _now_iso() -> str:
    """Return UTC ISO timestamp for audit rows."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _push_event(*, level: str, message: str, payload: dict[str, Any] | None = None) -> None:
    """Append bounded event log entry for UI observability."""
    _EVENTS.append(
        TunnelEvent(
            level=level,
            message=message,
            at=_now_iso(),
            payload=payload or {},
        )
    )
    if len(_EVENTS) > 100:
        del _EVENTS[:-100]


def _env_or_default(name: str, default: str) -> str:
    """Read optional settings attribute with fallback default string."""
    val = getattr(settings, name, "")
    if val:
        return str(val).strip()
    env_val = os.getenv(name, "").strip()
    return env_val if env_val else default


def _build_public_url(remote_port: int) -> str:
    """Build Azyl HTTPS URL for chosen remote port."""
    return f"https://azyl-{remote_port}.ag3nts.org"


def _build_tunnel_command(*, user: str, host: str, ssh_port: int, remote_port: int, local_port: int) -> list[str]:
    """
    Build process command for reverse tunnel.

    Preference order:
    1) `plink` in batch mode + password from env (Windows password auth).
    2) plain `ssh` in non-interactive mode (key-based auth only).
    """
    azyl_password = _env_or_default("AZYL_PASSWORD", "")
    azyl_hostkey = _env_or_default("AZYL_HOSTKEY", _DEFAULT_AZYL_HOSTKEY)
    plink_path = shutil.which("plink")

    if plink_path and azyl_password:
        cmd = [
            plink_path,
            "-batch",
            "-N",
            "-ssh",
            "-P",
            str(ssh_port),
            "-pw",
            azyl_password,
            "-hostkey",
            azyl_hostkey,
            "-R",
            f"{remote_port}:127.0.0.1:{local_port}",
            f"{user}@{host}",
        ]
        return cmd

    return [
        "ssh",
        "-N",
        "-o",
        "BatchMode=yes",
        "-o",
        "NumberOfPasswordPrompts=0",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ExitOnForwardFailure=yes",
        "-R",
        f"{remote_port}:127.0.0.1:{local_port}",
        f"{user}@{host}",
        "-p",
        str(ssh_port),
    ]


def _state_to_dict() -> dict[str, Any]:
    """Convert state dataclass to plain dict for templates and APIs."""
    return {
        "status": _STATE.status,
        "public_url": _STATE.public_url,
        "user": _STATE.user,
        "host": _STATE.host,
        "ssh_port": _STATE.ssh_port,
        "remote_port": _STATE.remote_port,
        "local_port": _STATE.local_port,
        "pid": _STATE.pid,
        "started_at": _STATE.started_at,
        "last_error": _STATE.last_error,
        "command_preview": _STATE.command_preview,
    }


# =============================================================================
# Public API
# =============================================================================

def get_tunnel_defaults() -> dict[str, Any]:
    """Return UI defaults for tunnel start form."""
    return {
        "user": _env_or_default("AZYL_USER", _DEFAULT_AZYL_USER),
        "host": _env_or_default("AZYL_HOST", _DEFAULT_AZYL_HOST),
        "ssh_port": int(_env_or_default("AZYL_SSH_PORT", str(_DEFAULT_AZYL_PORT))),
        "remote_port": int(_env_or_default("AZYL_REMOTE_PORT", str(_DEFAULT_REMOTE_PORT))),
        "local_port": int(_env_or_default("AZYL_LOCAL_PORT", str(_DEFAULT_LOCAL_PORT))),
    }


def get_tunnel_snapshot() -> dict[str, Any]:
    """Return current tunnel state with last 20 events."""
    with _LOCK:
        # Auto-heal status when process exits unexpectedly.
        global _PROCESS
        if _PROCESS is not None and _PROCESS.poll() is not None:
            _STATE.status = "stopped"
            _STATE.pid = None
            _PROCESS = None
        return {
            "state": _state_to_dict(),
            "events": [
                {
                    "level": e.level,
                    "message": e.message,
                    "at": e.at,
                    "payload": e.payload,
                }
                for e in _EVENTS[-20:]
            ],
            "defaults": get_tunnel_defaults(),
        }


def start_tunnel(*, user: str, host: str, ssh_port: int, remote_port: int, local_port: int) -> dict[str, Any]:
    """
    Start reverse SSH tunnel process.

    Returns:
        Latest tunnel snapshot dict.
    """
    with _LOCK:
        global _PROCESS

        if _PROCESS is not None and _PROCESS.poll() is None:
            _push_event(level="warn", message="Tunnel start ignored: already running", payload={"pid": _PROCESS.pid})
            return get_tunnel_snapshot()

        cmd = _build_tunnel_command(
            user=user,
            host=host,
            ssh_port=ssh_port,
            remote_port=remote_port,
            local_port=local_port,
        )

        if shutil.which("plink") is None and _env_or_default("AZYL_PASSWORD", ""):
            _push_event(
                level="warn",
                message="AZYL_PASSWORD is configured but plink is not available; ssh fallback requires key-based auth.",
            )

        _STATE.status = "starting"
        _STATE.user = user
        _STATE.host = host
        _STATE.ssh_port = ssh_port
        _STATE.remote_port = remote_port
        _STATE.local_port = local_port
        _STATE.public_url = _build_public_url(remote_port)
        _STATE.last_error = ""
        # Never expose raw password in UI/diagnostics.
        preview_parts: list[str] = []
        skip_next = False
        for idx, token in enumerate(cmd):
            if skip_next:
                skip_next = False
                continue
            if token in {"-pw", "--password"}:
                preview_parts.extend([token, "***"])
                skip_next = True
                continue
            preview_parts.append(token)
        _STATE.command_preview = " ".join(preview_parts)

        _push_event(
            level="info",
            message="Starting Azyl tunnel",
            payload={
                "user": user,
                "host": host,
                "ssh_port": ssh_port,
                "remote_port": remote_port,
                "local_port": local_port,
            },
        )

        try:
            _PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
            )
        except Exception as exc:
            _PROCESS = None
            _STATE.status = "error"
            _STATE.pid = None
            _STATE.last_error = str(exc)
            _push_event(level="error", message="Tunnel process failed to start", payload={"error": str(exc)})
            return get_tunnel_snapshot()

        time.sleep(1.5)
        if _PROCESS.poll() is None:
            _STATE.status = "running"
            _STATE.pid = _PROCESS.pid
            _STATE.started_at = _now_iso()
            _push_event(level="info", message="Azyl tunnel running", payload={"pid": _PROCESS.pid, "public_url": _STATE.public_url})
        else:
            stderr = ""
            if _PROCESS.stderr:
                try:
                    stderr = (_PROCESS.stderr.read() or "").strip()
                except Exception:
                    stderr = ""
            _STATE.status = "error"
            _STATE.pid = None
            _STATE.last_error = stderr or "Tunnel process exited immediately"
            _push_event(level="error", message="Tunnel exited during startup", payload={"stderr": _STATE.last_error})
            _PROCESS = None

        return get_tunnel_snapshot()


def stop_tunnel() -> dict[str, Any]:
    """Stop running tunnel process if active and return latest snapshot."""
    with _LOCK:
        global _PROCESS

        if _PROCESS is None or _PROCESS.poll() is not None:
            _PROCESS = None
            _STATE.status = "stopped"
            _STATE.pid = None
            _push_event(level="warn", message="Tunnel stop ignored: no running process")
            return get_tunnel_snapshot()

        pid = _PROCESS.pid
        _push_event(level="info", message="Stopping Azyl tunnel", payload={"pid": pid})

        try:
            _PROCESS.terminate()
            _PROCESS.wait(timeout=5)
        except Exception:
            try:
                _PROCESS.kill()
            except Exception:
                pass

        _PROCESS = None
        _STATE.status = "stopped"
        _STATE.pid = None
        _STATE.started_at = ""
        _push_event(level="info", message="Azyl tunnel stopped", payload={"pid": pid})

        return get_tunnel_snapshot()
