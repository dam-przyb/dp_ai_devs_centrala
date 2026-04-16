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

# Module 02_01 — Agentic RAG (File Tools)

## Module Overview
- Build an agentic RAG assistant that explores local course materials with list/search/read tools.
- Emphasize multi-phase search (synonyms, related terms) before reading file fragments.
- Preserve conversation history for follow-up questions and show which files were consulted.

## What to Build
- A Django app `module_02_01` with a single interactive chat page (or one section on a page) for agentic RAG.
- The agent uses file tools to explore a document root (default: `_lessons_texts/`) and answers in English.
- The UI warns about token usage and provides a clear/reset button for the conversation state.
- Responses show the final answer plus a concise list of sources (file + section/line range).

## User Interaction Flow
- User opens the page and sees a short token-usage warning plus the document root being searched.
- User submits a question.
- The agent runs a multi-step tool loop (list/search/read) and returns an answer in English with sources.
- User submits a follow-up; the agent uses conversation history to avoid re-asking.
- User clicks “Clear conversation” to reset state and token stats.

## Architecture
- `module_02_01/schemas.py`
  - `FileListing`, `SearchMatch`, `SearchResult`, `ToolCall`, `ToolResult`, `AgentReply`.
- `module_02_01/prompts.py`
  - `SYSTEM_PROMPT` (verbatim from JS config).
  - `SEARCH_GUIDANCE` extracted for readability.
- `module_02_01/graphs.py`
  - LangGraph loop that alternates LLM → tool execution until no tool calls or `max_steps` reached.
- `module_02_01/services.py`
  - `run_agentic_rag(query, history)` executes the graph and returns `AgentReply`.
  - File tools: `list_dir(path)`, `search_text(query)`, `read_file(path, start_line, end_line)` scoped to a root directory.
  - Normalize tool outputs as JSON strings for tool-call outputs.
- `module_02_01/views.py`
  - `IndexView` renders the UI.
  - `ChatView` handles HTMX submit and returns `_chat_result.html`.
  - `ClearView` resets conversation + usage counters.
- `module_02_01/templates/module_02_01/`
  - `index.html`, partials `_chat_result.html`, `_history.html`, `_error.html`.

## LangGraph Graph Design
- **State (TypedDict)**
  - `messages: list[dict]`
  - `tool_calls: list[dict]`
  - `tool_results: list[dict]`
  - `sources: list[dict]`
  - `step: int`
  - `max_steps: int`
  - `final_answer: str | None`
- **Nodes**
  - `llm_step` — call OpenAI Responses with tools; extract tool calls or final text.
  - `tool_step` — execute list/search/read tools; append `function_call_output` items.
  - `finalize` — build `AgentReply` with `answer` + `sources`.
- **Edges**
  - `llm_step` → `tool_step` if tool calls exist.
  - `llm_step` → `finalize` if no tool calls.
  - `tool_step` → `llm_step` (loop).
- **Guardrails**
  - Abort with a friendly error when `step >= max_steps` (50).

## Prompts

### Agent System Prompt
Use the exact system prompt from the JS config:

```text
You are an agent that answers questions by searching and reading available documents. You have tools to explore file structures, search content, and read specific fragments. Use them to find evidence before answering.

## SEARCH GUIDANCE

- **Scan:** If no specific path is given, start by exploring the resource structure — scan folder hierarchies, file names, and headings of potentially relevant documents.
- **Deepen (multi-phase):** This is an iterative process, not a single step:
  1. Search with initial keywords, synonyms, and related terms (at least 3–5 angles).
  2. Read the most promising fragments from search results.
  3. While reading, collect new terminology, concepts, section names, and proper names you did not know before.
  4. Run follow-up searches using these newly discovered terms to find sections you would have missed.
  5. Repeat steps 2–4 until no significant new terms emerge.
- **Explore:** Look for related aspects arising from the topic — cause/effect, part/whole, problem/solution, limitations/workarounds, requirements/configuration — investigating each as a separate lead.
- **Verify coverage:** Before answering, check whether you have enough knowledge to address key questions (definitions, numbers/limits, edge cases, steps, exceptions, etc.). If gaps remain, go back to the Deepen phase with new search terms.

## EFFICIENCY

- NEVER read entire files upfront. Always search for relevant content first using keywords, synonyms, and related terms.
- Do NOT jump to reading fragments after just one or two searches. Exhaust your keyword variations first — the goal is to discover all relevant sections across documents before loading any content.
- Use search results (file paths + matching lines) to identify which fragments matter, then read only those specific line ranges.
- Reading a full file is a last resort — only justified when search results suggest the entire document is relevant and short enough to warrant it.

## RULES

- Ground your answers in the actual content of files — cite specific documents and fragments
- If the information is not found in available resources, say so explicitly
- When multiple documents are relevant, synthesize information across them
- Report which files you consulted so the user can verify

## CONTEXT

Your knowledge base consists of AI_devs course materials stored as S01*.md files. The content is written in Polish — use Polish keywords when searching. Always respond in English.
```

### OpenAI Settings
- Model: `gpt-5.2`
- `max_output_tokens`: 16384
- `reasoning`: `{ "effort": "medium", "summary": "auto" }`

## Environment Variables
- `OPENAI_API_KEY` (required)

## Acceptance Criteria
- The agent performs multi-phase search before reading any file fragments.
- Tooling is limited to list/search/read and is scoped to the configured root directory.
- Responses are grounded in file content with explicit source references.
- When no evidence is found, the agent says so explicitly.
- Follow-up questions reuse conversation history until cleared.
- Clear action resets history and usage counters.
- Responses are in English and use Polish keywords in searches.
- Agent loop stops at 50 steps with a graceful error message.
