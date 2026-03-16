# Session Progress — Coding Agent Handover

> **Purpose**: Tells the next coding agent exactly where we are so it can
> continue without re-analysing the full codebase from scratch.
> Read this alongside `implementation_plan.md`, `general_architecture.md`,
> and `tech_stack.md`.

---

## Current Status: Phases 0–6 Complete ✅

| Phase | Description | Status |
|---|---|---|
| 0 | Project scaffold (settings, urls, dirs, .env) | ✅ Done |
| 1 | `core` app — base template, nav, dashboard view | ✅ Done |
| 2 | `lesson_01` — chat (interaction), structured output, RAG grounding | ✅ Done |
| 3 | `lesson_03` — MCP (core, native, translator, upload) | ✅ Done |
| 4 | `lesson_04` — Media (audio, video-gen, image, PDF report) | ✅ Done |
| **6** | **`lesson_05` — LangGraph confirmation + master orchestrator** | ✅ Done (this session) |
| **Final** | **Wiring check — all URLs resolve, `manage.py check` = 0** | ✅ Done (this session) |

> **Note**: The implementation plan calls lesson_02 "Phase 3" and lesson_03
> "Phase 4", but the Django apps follow `lesson_0X` naming. The numbering
> above uses phase numbers from `implementation_plan.md`.
> Lesson_02 (Tool Use) was completed in a prior session.

---

## What Was Built This Session

### lesson_03 (MCP)

```
lesson_03/
├── services/
│   └── mcp_service.py          # async MCP helpers + sync wrappers + LangChain translator
├── views/
│   ├── mcp_core.py             # list tools + direct call
│   ├── mcp_native.py           # raw ClientSession demo (no LangChain)
│   ├── mcp_translator.py       # LangChain agent backed by MCP tools
│   └── upload_mcp.py           # file upload → sandbox → MCP agent summary
├── urls.py                     # all 4 modules wired up
└── templates/lesson_03/
    ├── mcp_core.html
    ├── mcp_native.html
    ├── mcp_translator.html
    ├── upload_mcp.html
    └── partials/
        ├── tool_list.html
        ├── tool_result.html
        └── agent_result.html
```

**Key URLs** (prefixed `/03/`):
- `mcp-core/`, `mcp-core/api/`
- `mcp-native/`, `mcp-native/api/`
- `mcp-translator/`, `mcp-translator/api/`
- `upload-mcp/`, `upload-mcp/api/`

### lesson_04 (Media)

```
lesson_04/
├── models.py                   # VideoGenerationJob (migrated ✅)
├── services/
│   ├── audio_service.py        # Whisper + OpenRouter summary
│   ├── video_generation_service.py  # mock video gen + HTMX polling
│   ├── image_service.py        # DALL-E 3 via OpenRouter
│   └── report_service.py       # WeasyPrint PDF generation
├── views/
│   ├── audio.py
│   ├── video_gen.py            # + video_status polling endpoint
│   ├── image.py
│   └── report.py               # preview (HTMX) + download (direct POST)
├── urls.py
└── templates/lesson_04/
    ├── audio.html
    ├── video_gen.html
    ├── image.html
    ├── report.html
    └── partials/
        ├── audio_result.html
        ├── video_status.html   # contains hx-trigger="every 5s" while pending
        ├── image_result.html
        ├── report_preview.html
        └── report_document.html  # WeasyPrint source (full HTML doc)
```

**Key URLs** (prefixed `/04/`):
- `audio/`, `audio/api/`
- `video/`, `video/api/`, `video/status/<task_id>/`
- `image/`, `image/api/`
- `report/`, `report/preview/`, `report/download/`

---

## Dependencies Added to requirements.txt

```
langgraph>=0.2
openai>=1.0        # Whisper
mcp>=1.0           # MCP Python SDK
weasyprint         # PDF generation
```

These were installed in the active `.venv` during this session.

---

## What Remains: Phase 5 & 6 — Lesson 05 (Orchestration)

See `implementation_plan.md` sections **Phase 6** and the lesson_05 detail file
`.ai_specs/01_05_modules.md` for full spec.

### What to build

```
lesson_05/
├── services/
│   ├── confirmation_service.py   # LangGraph graph with interrupt_before
│   └── orchestrator_service.py   # Supervisor: intent classify → delegate
├── views/
│   ├── confirmation.py           # start + resume views (human-in-the-loop)
│   └── agent.py                  # master orchestrator agent view
├── urls.py
└── templates/lesson_05/
    ├── confirmation.html
    ├── agent.html
    └── partials/
        ├── confirm_prompt.html   # pending action + approve/reject buttons
        ├── confirm_done.html     # final result after resume
        └── agent_result.html
```

**Nav registry** (`core/nav_registry.py`) already has lesson_05 entries:
```python
{"slug": "confirmation", "label": "Human-in-the-Loop", "url_name": "l05_confirmation"},
{"slug": "agent",        "label": "Master Orchestrator", "url_name": "l05_agent"},
```

**lesson_05/urls.py** exists but is empty — needs to be filled.

### Confirmation service key pattern (from implementation_plan.md §6.2–6.3)

```python
# Build graph with interrupt_before=["send_email_node"]
# View 1 (start):  invoke graph → halts → return confirm_prompt.html with thread_id
# View 2 (resume): graph.invoke(Command(resume=True), config) → confirm_done.html
```

Uses `SqliteSaver` from `langgraph.checkpoint.sqlite` pointing at `db.sqlite3`.

### Orchestrator service key pattern (from implementation_plan.md §6)

A "supervisor" LLM that:
1. Classifies the user's intent
2. Routes to a specialist sub-agent (e.g. re-uses lesson_01 interaction, lesson_02 FS agent)
3. Returns the combined result

---

## Useful Context for Next Agent

- `python manage.py check` → **0 issues** (verified end of this session)
- `OPENROUTER_API_KEY` env var name in settings is read from `OPENROUTERKEY` (note: no underscore in env key — see `settings.py` line 102)
- `OPENAI_API_KEY` needed only for Whisper (lesson_04/audio)
- `MCP_SERVER_SCRIPT` needed only for lesson_03 (e.g. `npx -y @modelcontextprotocol/server-filesystem /tmp`)
- All lesson templates are **partials** (no `<html>/<body>` wrapper) — HTMX injects them into `#workspace-container`
- Video generation is **mocked** — real Kling/Luma integration left as TODO comment in `video_generation_service.py`
- Setup helper script `setup_phases_3_4.py` in project root can be deleted — it was one-time use

---

## Final Phase After Lesson 05

After lesson_05 is complete, do a **Final wiring check** (implementation_plan.md §"Final"):
- Verify all `url_name` values in `core/nav_registry.py` resolve correctly
- Run `python manage.py check` and `python manage.py migrate`
- Smoke-test each nav item loads without 500 errors
