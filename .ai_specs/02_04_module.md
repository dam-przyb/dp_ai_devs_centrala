<details>
<summary>rules.md</summary>

```md
---
trigger: always_on
---

# IDE — Agent Rules

## Project Purpose

You are a coding agent working on **IDE** — a Python web application that is a faithful, pedagogically complete translation of JavaScript educational tools from the **AI Devs 4** course. The original course teaches how to build and manage AI agents. Your job is to re-implement each lesson's tools and demos in Python so learners who prefer Python can follow the same concepts using the same mental models.

You work inside **Visual Studio Code**. You receive per-module instruction files (e.g. `01_01_module.md`). Each file is fully self-contained — it describes what to build, why, and how. You do not have access to the original JavaScript source.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.12+ | Type hints required everywhere |
| Web framework | Django 5.x | Use class-based views where it makes sense |
| Frontend reactivity | HTMX 2.x | No separate JS framework; JS only for unavoidable interactivity |
| Agent framework | LangGraph | For all multi-step agent and pipeline logic |
| LLM client | `anthropic` / `openai` SDK | Follow what the module specifies |
| Async | `asyncio` + Django async views | Use `async def` views when calling LLMs or external APIs |
| Package manager | `uv` | Lock file required (`uv.lock`) |
| Settings | `python-decouple` | All secrets via `.env`, never hardcoded |
| Database | SQLite (dev) / PostgreSQL-ready | Use Django ORM, no raw SQL unless unavoidable |
| Styling | Tailwind CSS (CDN in templates) | Keep it utility-first, no custom CSS files unless required |
| Task queue | Django Q2 or Celery (module-specific) | Only add if the module requires background jobs |

---

## Project Structure

All code lives under one Django project root called `antigravity/`. Each course module becomes a **Django app** inside it.

```
antigravity/
├── manage.py
├── pyproject.toml
├── uv.lock
├── .env.example
├── antigravity/              # Django project settings package
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/                     # Shared utilities app (registered as Django app)
│   ├── llm.py                # LLM client factory (Anthropic, OpenAI)
│   ├── graph.py              # LangGraph helpers / base graph builders
│   ├── htmx.py               # HTMX response helpers (HX-Trigger, partial renders)
│   └── templates/core/
│       ├── base.html         # Base template with HTMX + Tailwind CDN
│       └── partials/         # Shared HTMX partials
├── module_01_01/             # One app per lesson group (see naming below)
│   ├── apps.py
│   ├── views.py
│   ├── urls.py
│   ├── graphs.py             # LangGraph definitions for this module
│   ├── prompts.py            # All prompt strings, no prompts in views
│   ├── schemas.py            # Pydantic models for structured outputs
│   ├── models.py             # Django models if persistence needed
│   ├── services.py           # Business logic, LLM calls, agent runs
│   └── templates/module_01_01/
│       ├── index.html
│       └── partials/
└── static/
    └── js/
        └── htmx.min.js       # Local copy of HTMX
```

### App Naming Convention

| Lesson group in JS repo | Django app name |
|---|---|
| `01_01_grounding`, `01_01_interaction`, `01_01_structured` | `module_01_01` |
| `01_02_tools`, `01_02_tool_use` | `module_01_02` |
| `01_03_mcp_*` | `module_01_03` |
| `01_04_*` (audio, image, video…) | `module_01_04` |
| `01_05_*` | `module_01_05` |
| `02_01_*` | `module_02_01` |
| … and so on | … |

Each module instruction file will specify exactly which sub-topics belong to the app.

---

## Coding Standards

### General
- Use **type hints** on all function signatures, including return types.#rules
- Use **Pydantic v2** for all data validation and structured LLM output schemas (`BaseModel`, `model_validate`, `model_dump`).
- Never put business logic in views. Views handle HTTP only; logic goes in `services.py`.
- Never put prompt strings inline in `services.py` or views. All prompts live in `prompts.py` as module-level constants or factory functions.
- Prefer `async def` services when they perform I/O (LLM calls, HTTP requests, file reads).

### Django Views
- Use `django.views.generic.View` or `django.views.generic.TemplateView` as base.
- For HTMX partials, check `request.htmx` (via `django-htmx` middleware) and return `TemplateResponse` with the partial template path.
- Add `django-htmx` to installed apps — it provides `request.htmx` and the `HtmxResponseMixin`.
- Streaming LLM responses: use `StreamingHttpResponse` with an async generator.

### LangGraph Patterns
- Define each graph in `graphs.py` as a compiled `StateGraph`.
- State schemas are `TypedDict` classes defined at the top of `graphs.py`.
- Nodes are plain `async def` functions (or sync if no I/O).
- Expose a single entry-point coroutine per graph, e.g. `async def run_graph(input: InputSchema) -> OutputSchema`.
- Never build graphs inside a request/response cycle — compile them at module import time.
- Use `langgraph.checkpoint.memory.MemorySaver` for in-process state; swap to `langgraph-checkpoint-postgres` for persistence if the module requires it.

### Templates & HTMX
- All templates extend `core/base.html`.
- Partial templates go in `templates/<app>/partials/` and are named `_<thing>.html` (leading underscore).
- Use `hx-get`, `hx-post`, `hx-target`, `hx-swap` attributes to wire UI to views.
- Use `hx-indicator` with a shared spinner partial for loading states.
- HTMX triggers from the server (`HX-Trigger` response header) go through `core/htmx.py` helper: `trigger_client_event(response, event_name, detail)`.
- Use server-sent events (`hx-ext="sse"`) for streaming output where the module requires it.

### Error Handling
- All LLM calls must be wrapped in `try/except` with specific exception types from the SDK.
- Return structured error partials to HTMX (`hx-swap="outerHTML"` on an error container) — never let uncaught exceptions bubble to a 500 page in UI flows.
- Log errors with `logging.getLogger(__name__)` — never use `print()`.

### Environment Variables
All secrets and config go in `.env`. Required keys per module will be listed in the module instruction file. Common ones:

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DJANGO_SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## LLM Client Factory (`core/llm.py`)

Always use this factory — never instantiate clients directly in module code.

```python
# core/llm.py
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from decouple import config

def get_anthropic() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=config("ANTHROPIC_API_KEY"))

def get_openai() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=config("OPENAI_API_KEY"))
```

Default model names:
- Anthropic: `claude-sonnet-4-20250514`
- OpenAI: `gpt-4o`

Override per-module only if the module instruction file explicitly specifies a different model.

---

## Structured Output Pattern

Use Pydantic models + LLM structured output (tool use / `response_format`). Define schemas in `schemas.py`:

```python
# schemas.py
from pydantic import BaseModel, Field

class ExtractionResult(BaseModel):
    answer: str = Field(description="The extracted answer")
    confidence: float = Field(ge=0.0, le=1.0)
```

For Anthropic, use tool calling to enforce schema. For OpenAI, use `response_format={"type": "json_schema", ...}` or the `parse()` helper on the beta client.

---

## Template Base (`core/base.html`)

Every page template extends this. It loads HTMX and Tailwind:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}AI Devs 4 — Python{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="{% static 'js/htmx.min.js' %}"></script>
  {% block extra_head %}{% endblock %}
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen">
  <nav class="border-b border-gray-800 px-6 py-3 text-sm text-gray-400">
    IDE — <span class="text-white">{% block module_name %}{% endblock %}</span>
  </nav>
  <main class="p-6">
    {% block content %}{% endblock %}
  </main>
  {% block extra_scripts %}{% endblock %}
</body>
</html>
```

---

## Module Instruction File Format

Each module instruction file you receive (`NN_NN_module.md`) will contain:

1. **Module Overview** — what concepts the lesson teaches
2. **What to Build** — a description of the tool/demo to implement
3. **User Interaction Flow** — how the user interacts with it in the browser
4. **Architecture** — which files to create, what each does
5. **LangGraph Graph Design** (if applicable) — nodes, edges, state
6. **Prompts** — exact prompts or prompt shapes to use
7. **Environment Variables** — which keys are required
8. **Acceptance Criteria** — what "done" looks like, edge cases to handle

Follow the instruction file exactly. Do not add features not described. Do not skip described features.

---

## Workflow for Each Module

1. **Read** the module instruction file fully before writing any code.
2. **Create** the Django app: `python manage.py startapp module_NN_NN`.
3. **Register** the app in `antigravity/settings.py` → `INSTALLED_APPS`.
4. **Wire** the URL: include `module_NN_NN.urls` in `antigravity/urls.py`.
5. **Implement** in this order: `schemas.py` → `prompts.py` → `graphs.py` → `services.py` → `views.py` → templates.
6. **Test** manually by running `python manage.py runserver` and exercising the UI flow described in the instruction file.
7. **Do not** run migrations unless the module instruction file specifies Django models are needed.

---

## What to Avoid

- Do not use Django REST Framework — this is an HTMX app, not an API.
- Do not use React, Vue, or Alpine.js unless the module instruction file explicitly requires it.
- Do not use `requests` (sync HTTP) inside async views — use `httpx` with `AsyncClient`.
- Do not use `os.environ` directly — use `decouple.config`.
- Do not commit `.env` files.
- Do not write tests unless the module instruction file asks for them.
- Do not refactor other modules while working on the current one.
```
</details>

# Module 02_04 — Daily Ops Multi-Agent Workflow

## Module Overview
- Build a multi-agent workflow that generates a daily operations note.
- The orchestrator delegates to specialist agents (mail, calendar, tasks, notes) and synthesizes results.
- Demonstrates file-based workflows, agent templates, and delegation rules.

## What to Build
- A Django app `module_02_04` that runs the Daily Ops workflow from file templates and writes an output note.
- A single page with a “Generate Daily Ops” action and a results panel.
- Use a file-based workspace directory inside the app for agents, workflows, sources, goals, history, and preferences.

## User Interaction Flow
- User opens the page and clicks “Generate Daily Ops”.
- Orchestrator agent:
  - Reads the workflow file.
  - Delegates to mail/calendar/tasks/notes agents.
  - Reads goals, history, and preferences.
  - Synthesizes final note and writes to `output/YYYY-MM-DD.md`.
- UI shows the final markdown note and the output file path.

## Architecture
- `module_02_04/schemas.py`
  - `MailItem`, `CalendarEvent`, `TaskItem`, `NoteItem`, `DailyOpsResult`.
- `module_02_04/prompts.py`
  - Agent system prompts for orchestrator, mail, calendar, tasks, notes.
  - Workflow template text for `daily-ops.md`.
- `module_02_04/graphs.py`
  - LangGraph loop for the orchestrator and subagents (max turns 15, depth 3).
- `module_02_04/services.py`
  - `run_orchestrator(date)` returns the rendered markdown.
  - `delegate(agent, task)` spawns a subagent with its own loop.
  - Tool handlers: `get_mail`, `get_calendar`, `get_tasks`, `get_notes`, `read_file`, `write_file`.
- `module_02_04/views.py` + templates
  - `IndexView` and `GenerateView` with HTMX partials.
- Workspace structure (ship these files in the app, not in global root):
  - `workspace/agents/*.agent.md`
  - `workspace/workflows/daily-ops.md`
  - `workspace/goals/goals.md`
  - `workspace/history/2026-02-12.md`
  - `workspace/memory/preferences.md`
  - `workspace/sources/*.json`
  - `workspace/output/`

## LangGraph Graph Design
- **State (TypedDict)**
  - `messages: list[dict]`
  - `tool_calls: list[dict]`
  - `tool_results: list[dict]`
  - `step: int`
  - `final_answer: str | None`
- **Nodes**
  - `llm_step` — OpenAI chat completion with agent tools.
  - `tool_step` — executes tools; `delegate` runs a nested subagent.
  - `finalize` — return final markdown.
- **Edges**
  - `llm_step` → `tool_step` if tool calls exist.
  - `llm_step` → `finalize` if no tool calls.
  - `tool_step` → `llm_step`.

## Prompts

### Orchestrator Agent Prompt
```text
You are the Daily Ops orchestrator. Your job is to prepare a daily operations note by following the workflow instructions.

You MUST:

1. **First read the workflow** from `workflows/daily-ops.md` using read_file
2. **Delegate data gathering** to specialist agents (mail, calendar, tasks, notes) — use separate delegate calls for each
3. **Read goals, history, and preferences** using read_file:
   - `goals/goals.md`
   - `history/2026-02-12.md` (yesterday's output for dedup)
   - `memory/preferences.md`
4. **Synthesize everything** into a daily ops note following the template in the workflow
5. **Write the final note** using write_file to `output/YYYY-MM-DD.md`

All file paths for read_file and write_file are relative to the workspace root (no `workspace/` prefix).

Be thorough but concise. Surface overdue and escalated items prominently. Apply dedup: remove items already in yesterday's note with no change; escalate items that appeared yesterday and weren't done.
```

### Mail Agent Prompt
```text
You scan the inbox and return a structured summary.

Focus on:
- Actionable items (replies needed, follow-ups, decisions)
- Flag urgent messages prominently
- Note low-priority items (newsletters) separately

Return as structured text with:
- Sender
- Subject
- Action needed (or "FYI" / "Low priority")
- Urgency flag if applicable
```

### Calendar Agent Prompt
```text
You review calendar events for today and the next 48 hours.

Focus on:
- Flag cancelled events — note what was cancelled and any impact
- Flag shifted/rescheduled events
- Note scheduling conflicts or back-to-back meetings
- Identify protected blocks (e.g. deep work)

Return as structured summary with:
- Event title, time, duration
- Status (confirmed / cancelled / tentative)
- Attendees (if relevant)
- Notes on conflicts or changes
```

### Tasks Agent Prompt
```text
You review the task list and return a structured summary.

Focus on:
- **Surface open and overdue tasks first** — they are highest priority
- Note blocked items — include what is blocking them
- Group by priority (high, medium, low)
- Note completed items briefly (for context)

Return as structured summary with:
- Overdue (with due date)
- Due today
- Blocked (with blocker)
- Upcoming
- Completed (if relevant)
```

### Notes Agent Prompt
```text
You review open notes and loops.

Focus on:
- Drafts needing attention (e.g. pricing model, proposals)
- Open questions requiring decisions
- Personal reminders
- Research notes with actionable follow-ups

Return as structured summary with:
- Note title
- Type (draft / open-question / reminder / research)
- Key content or action needed
- Relevance to today's priorities
```

### Workflow Template (daily-ops.md)
```text
# Daily Ops Workflow

This workflow produces a daily operations note by aggregating mail, calendar, tasks, and notes, then synthesizing them against goals and history.

---

## Steps

### Step 1: Delegate data gathering
Delegate to specialist agents. Use **separate delegate calls** for each:
- **mail** agent — gather inbox summary
- **calendar** agent — gather events (today + next 48h)
- **tasks** agent — gather open/overdue tasks
- **notes** agent — gather notes and open loops

### Step 2: Read goals
Read `goals/goals.md` using read_file. Use these goals to align the Direction section.

### Step 3: Read yesterday's output (dedup)
Read `history/2026-02-12.md` using read_file. This is used for:
- **Deduplication** — remove items already in yesterday's note that haven't changed
- **Escalation** — items that appeared yesterday and weren't done get escalated (increase priority, add to Escalated section with day count)

### Step 4: Read preferences
Read `memory/preferences.md` using read_file for output format, communication style, and priority rules.

### Step 5: Filter
- Remove items already in yesterday's note (no new info)
- Escalate repeated items — if something was in yesterday's Action Items or Escalated and is still open, add to Escalated with (Nd) where N = days since first appearance
- Apply priority rules from preferences (overdue first, 2+ day skip = escalate)

### Step 6: Synthesize
Compose a daily ops note with these sections (in order):
1. **Direction** — aligned with goals, what to focus on today
2. **Escalated** — overdue + items skipped 2+ days, with (Nd) suffix
3. **Shifted** — cancelled events, rescheduled meetings, calendar changes
4. **Action Items** — prioritized list with checkboxes
5. **Protection** — any guardrails (e.g. no meetings before 12:00)

### Step 7: Write output
Write the final note to `output/YYYY-MM-DD.md` using the write_file tool. Use today's date (e.g. `2026-02-13.md`).

**IMPORTANT**: All file paths for read_file and write_file are relative to the workspace root. Do NOT include a `workspace/` prefix.

---

## Output Template

```markdown
# Daily Ops — YYYY-MM-DD (DayOfWeek)

## Direction
[1-2 sentences: focus for today, aligned with goals]

## Escalated
- **[item] (Nd)** — [brief context]. [Action needed].

## Shifted
- [Cancelled/rescheduled events and changes]

## Action Items
- [ ] [Highest priority — overdue first]
- [ ] [Due today]
- [ ] [Blocked — note blocker]
- [ ] [Upcoming]

## Protection
[Guardrails, e.g. no meetings before 12:00]
```
```

## Environment Variables
- `OPENAI_API_KEY` (required)

## Acceptance Criteria
- Orchestrator reads `workflows/daily-ops.md` before any delegation.
- Delegation uses four separate delegate calls (mail, calendar, tasks, notes).
- Orchestrator reads goals, history, and preferences files as specified.
- Dedup and escalation rules are applied exactly as in workflow + preferences.
- Output file is written to `workspace/output/YYYY-MM-DD.md`.
- Actions list uses `- [ ]` checkboxes and ISO dates.
- Max depth = 3, max turns = 15 per agent.
