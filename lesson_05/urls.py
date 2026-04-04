"""
Lesson 05 URL configuration — Agent Orchestration.

Module          URL                                    View
-----------     ------------------------------------   ---------------------------
Confirmation    /05/confirmation/                      confirmation_view  (GET)
                /05/confirmation/start/                confirmation_start (POST)
                /05/confirmation/resume/               confirmation_resume (POST)
Agent           /05/agent/                             agent_view         (GET)
                /05/agent/api/                         agent_api          (POST)
Railway         /05/railway/                           railway_view       (GET)
                /05/railway/api/                       railway_api        (POST)
                /05/railway/stream/<task_id>/          railway_stream     (GET/SSE)
"""

from django.urls import path

from lesson_05.views.confirmation import (
    confirmation_resume,
    confirmation_start,
    confirmation_view,
)
from lesson_05.views.agent import agent_api, agent_view
from lesson_05.views.railway import railway_api, railway_stream, railway_view

urlpatterns = [
    # ── Human-in-the-Loop ─────────────────────────────────────────────────────
    path("confirmation/",         confirmation_view,   name="l05_confirmation"),
    path("confirmation/start/",   confirmation_start,  name="l05_confirmation_start"),
    path("confirmation/resume/",  confirmation_resume, name="l05_confirmation_resume"),

    # ── Master Orchestrator ───────────────────────────────────────────────────
    path("agent/",                agent_view,          name="l05_agent"),
    path("agent/api/",            agent_api,           name="l05_agent_api"),

    # ── Railway X-01 Quest ────────────────────────────────────────────────────
    path("railway/",                         railway_view,   name="l05_railway"),
    path("railway/api/",                     railway_api,    name="l05_railway_api"),
    path("railway/stream/<str:task_id>/",    railway_stream, name="l05_railway_stream"),
]
