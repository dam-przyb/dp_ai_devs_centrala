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

# Module 02_05 — Observational Memory + Sandbox Agent

## Module Overview
- Build an agent with Observational Memory (observer/reflector compression cycle).
- Expose session-based chat endpoints and memory summaries.
- Add a second demo: MCP sandbox agent that discovers tools and runs JS in a sandbox.

## What to Build
- A Django app `module_02_05` with two sections:
  1. **Observational Memory Chat** — session-based agent with memory compression logs.
  2. **MCP Sandbox** — agent that discovers a todo MCP server and executes JS code.
- Provide a minimal workspace directory inside the app with agent templates and notes.

## User Interaction Flow
- Observational Memory
  - User opens the chat page, sends a message, gets a response.
  - UI shows session id and memory summary (observations token count, generation count).
  - User can call “Flush memory” to force observation compression.
  - Optional: view a list of sessions with message counts.
- Sandbox
  - User enters a task (default shopping list demo).
  - Agent uses list_servers → list_tools → get_tool_schema → execute_code.
  - Result and captured console logs are shown in the UI.

## Architecture
- `module_02_05/schemas.py`
  - `Message`, `FunctionCall`, `FunctionCallOutput`, `Session`, `MemoryState`.
  - `ObserverResult`, `ReflectorResult`, `SandboxResult`.
- `module_02_05/prompts.py`
  - Alice agent system prompt.
  - Observer system prompt + reflector system prompt.
  - Sandbox agent system prompt.
- `module_02_05/graphs.py`
  - LangGraph loop for memory agent.
  - LangGraph loop for sandbox agent.
- `module_02_05/services.py`
  - `run_memory_agent(session, user_message)` with memory processing.
  - `process_memory()` implementing observer/reflector thresholds.
  - `run_sandbox_agent(task)` with tool discovery + execute_code.
- `module_02_05/sandbox.py`
  - JS execution environment using QuickJS (or equivalent) with time + memory limits.
- `module_02_05/tools.py`
  - Memory agent tools: `read_file`, `write_file` (workspace-scoped).
  - Sandbox tools: `list_servers`, `list_tools`, `get_tool_schema`, `execute_code`.
- `module_02_05/views.py` + templates
  - `MemoryChatView`, `SessionListView`, `FlushMemoryView`, `SandboxView`.
- Workspace structure inside the app:
  - `workspace/agents/alice.agent.md`
  - `workspace/agents/sandbox.agent.md`
  - `workspace/notes/*.md`
  - `workspace/memory/` (observer/reflector logs written here)

## LangGraph Graph Design

### Observational Memory Agent
- **State (TypedDict)**
  - `messages: list[Message]`
  - `memory: MemoryState`
  - `tool_calls: list[FunctionCall]`
  - `tool_results: list[FunctionCallOutput]`
  - `final_answer: str | None`
- **Nodes**
  - `prepare_context` — applies observer/reflector logic, builds system prompt.
  - `llm_step` — OpenAI Responses call with tools.
  - `tool_step` — executes read/write tools.
  - `finalize` — return answer + usage summary.
- **Edges**
  - `llm_step` → `tool_step` if tool calls exist.
  - `llm_step` → `finalize` if no tool calls.
  - `tool_step` → `prepare_context`.

### Sandbox Agent
- **State (TypedDict)**
  - `messages: list[dict]`
  - `tool_calls: list[dict]`
  - `tool_results: list[dict]`
  - `final_answer: str | None`
- **Nodes**
  - `llm_step` — OpenAI chat completions with tool calling.
  - `tool_step` — list_servers/list_tools/get_tool_schema/execute_code.
  - `finalize` — return result and logs.

## Prompts

### Alice Agent Prompt
```text
You are Alice, a helpful AI assistant with persistent memory.

You remember details about the user across conversations through your observation memory system. When observations are available in the system prompt, use them to maintain continuity and personalize your responses.

Guidelines:
- Be concise but thorough. Use the fewest words possible, and prefer short-to-medium responses (a few sentences max).
- Reference specific details you remember about the user when relevant
- If the user corrects something, acknowledge and update your understanding
- Use tools when the user asks to read or write files in the workspace
```

### Observer System Prompt
```text
You are the memory consciousness of an AI assistant.
Your observations will be the ONLY information the assistant has about past interactions.

Extract high-fidelity observations from conversation history.
Do not chat. Do not explain. Output only structured XML.

Rules:
1) Every observation MUST be tagged with its source: [user], [assistant], or [tool:name].
   - [user]: facts, preferences, decisions explicitly stated by the user.
   - [assistant]: actions taken, commitments made, or content generated by the assistant.
   - [tool:name]: outcomes of tool calls (e.g. [tool:write_file], [tool:read_file]).
2) Priority markers:
   - 🔴 high: explicit user facts, preferences, decisions, completed goals.
   - 🟡 medium: active work, project details, tool outcomes, unresolved blockers.
   - 🟢 low: tentative or minor details, assistant elaborations.
3) Preserve concrete details: names, numbers, dates, file paths, quoted phrasing.
4) Capture state changes explicitly ("updating previous preference").
5) Keep observations concise but information-dense.
6) Do NOT repeat observations that already exist in previous observations.

Output format (strict):
<observations>
* 🔴 [user] ...
* 🟡 [assistant] ...
* 🟡 [tool:write_file] ...
</observations>

<current-task>
Primary: ...
</current-task>

<suggested-response>
...
</suggested-response>
```

### Reflector System Prompt
```text
You are the observation reflector — part of the memory consciousness.

You must reorganize and compress observations while preserving continuity.

Rules:
1) Your output is the ENTIRE memory. Anything omitted is forgotten.
2) Preserve source tags ([user], [assistant], [tool:name]) on every observation.
3) [user] observations are highest priority — never drop them unless contradicted by a newer [user] observation.
4) [assistant] elaborations are lowest priority — condense or drop them first.
5) [tool:*] outcomes should be kept as concise action records.
6) Condense older details first. Preserve recent details more strongly.
7) Resolve contradictions by preferring newer observations.
8) Use the same bullet format as input. Do NOT restructure into XML attributes or other schemas.

Output format:
<observations>
* 🔴 [user] ...
* 🟡 [tool:write_file] ...
</observations>
```

### Sandbox Agent Prompt
```text
You are a helpful assistant that accomplishes tasks by discovering and using tools through code execution.

## Workflow

1. Use **list_servers** to see available MCP server capabilities
2. Use **list_tools** to explore a server's tools (names + descriptions)
3. Use **get_tool_schema** to load the full TypeScript definition for tools you need
4. Use **execute_code** to write and run JavaScript code using the loaded tools

## Rules

- Only load schemas for tools you actually need (saves context)
- Code runs in a QuickJS sandbox — isolated from the host system, no filesystem or network access
- Only `console.log()` output is returned to you — **always console.log your results**
- Be efficient: batch operations in a single execute_code call when possible
- **Tool calls are synchronous** — call them directly: `const result = todo.create({title: "Buy milk"})`. Do NOT use `async/await`.
- Write top-level code directly — do NOT wrap in functions. Just write statements.
- Data stays in the sandbox — process and filter results before logging
- MCP server state persists between execute_code calls within a session
```

## Environment Variables
- `OPENAI_API_KEY` (required)

## Acceptance Criteria
- Observational memory uses these defaults:
  - `observationThresholdTokens = 400`
  - `reflectionThresholdTokens = 400`
  - `reflectionTargetTokens = 200`
  - `observerModel = gpt-4.1-mini`
  - `reflectorModel = gpt-4.1-mini`
- Observer runs at most once per request and appends observations to system prompt.
- Reflector compresses observations when threshold exceeded and writes logs to `workspace/memory/`.
- Agent model for Alice is `gpt-5.4-mini`.
- `read_file` and `write_file` tools are workspace-scoped and block path traversal.
- `/sessions` list and `/sessions/:id/flush` equivalents exist in Django views.
- Sandbox tools expose `list_servers`, `list_tools`, `get_tool_schema`, `execute_code`.
- `execute_code` runs JS in a sandbox with time limit (5s) and memory limit (128MB).
- Todo MCP server supports create/get/list/update/delete with in-memory state.
