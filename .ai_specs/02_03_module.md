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

# Module 02_03 — Graph RAG Agents

## Module Overview
- Build a graph-based RAG system that indexes documents into Neo4j.
- Extract entities and relationships via LLM and expose graph exploration tools.
- Provide hybrid retrieval (full-text + vector) plus graph traversal for answers.

## What to Build
- A Django app `module_02_03` that:
  - Indexes `.md/.txt` files from a workspace directory into Neo4j.
  - Provides an agentic chat UI that uses `search`, `explore`, `connect`, `cypher`, `learn`, `forget`, `merge_entities`, `audit` tools.
  - Displays citations (source + section) and optional graph path summaries.

## User Interaction Flow
- User opens the page and runs initial indexing (auto or via button).
- User asks a question; agent starts with `search` and may explore entities/paths.
- User can reindex or force-clear the graph.
- Optional UI actions for `learn` (index a file or raw text) and `forget`.

## Architecture
- `module_02_03/schemas.py`
  - `Chunk`, `Entity`, `Relationship`, `SearchResponse`, `PathResult`, `GraphAnswer`.
- `module_02_03/prompts.py`
  - Agent system prompt (from JS config).
  - Entity/relationship extraction prompt (verbatim below).
- `module_02_03/graphs.py`
  - LangGraph agent loop with all graph tools.
- `module_02_03/graph/driver.py`
  - Neo4j driver helpers for read/write transactions.
- `module_02_03/graph/schema.py`
  - Constraints + indexes (full-text + vector) with embedding dim 1536.
- `module_02_03/graph/indexer.py`
  - Pipeline: read → chunk → embed chunks → extract entities/relationships → embed entities → write nodes/edges.
- `module_02_03/graph/search.py`
  - FTS search, vector search, RRF fusion, plus graph traversal helpers.
- `module_02_03/services.py`
  - High-level indexing and agent execution helpers.
- `module_02_03/views.py` + templates
  - Chat UI, reindex controls, optional learn/forget forms.

## LangGraph Graph Design
- **State (TypedDict)**
  - `messages: list[dict]`
  - `tool_calls: list[dict]`
  - `tool_results: list[dict]`
  - `step: int`
  - `final_answer: str | None`
- **Nodes**
  - `llm_step` — OpenAI Responses call with all graph tools.
  - `tool_step` — executes tool calls (search/explore/connect/cypher/learn/forget/merge_entities/audit).
  - `finalize` — format answer with citations and path summaries.
- **Edges**
  - `llm_step` → `tool_step` if tool calls exist.
  - `llm_step` → `finalize` if no tool calls.
  - `tool_step` → `llm_step`.

## Prompts

### Agent System Prompt
```text
You are a knowledge assistant that answers questions by searching and exploring a graph-based knowledge base. Documents are chunked, indexed, and connected through a graph of entities and relationships.

## TOOLS

1. **search** — Hybrid retrieval (full-text + semantic). Returns matching text chunks AND the entities mentioned in those chunks. Always start here.
2. **explore** — Expand one entity from search results to see its neighbors and relationship types.
3. **connect** — Find the shortest path(s) between two entities to discover how they relate.
4. **cypher** — Read-only Cypher for structural/aggregate queries the other tools can't express.
5. **learn** / **forget** — Add or remove documents from the knowledge graph.
6. **merge_entities** / **audit** — Curate graph quality (fix duplicates, check health).

## RETRIEVAL STRATEGY

1. **Always start with search.** It returns both text evidence and entity names you can explore further.
2. **Use explore** when search results mention an interesting entity and you want to see what connects to it.
3. **Use connect** when the question asks about the relationship between two specific things.
4. **Use cypher** only for questions about graph structure (counts, types, most-connected, etc).
5. **Don't search** for greetings, small talk, or clarifications that don't need evidence.

## ANSWERING

- Ground every claim in evidence — cite the source file and section.
- If information is not found, say so explicitly.
- When multiple chunks are relevant, synthesize across them.
- When graph paths reveal connections, explain the chain.
- Be concise but thorough. Always mention which sources you consulted.
```

### Entity + Relationship Extraction Prompt
```text
You are an entity and relationship extractor. Given a text chunk, extract structured knowledge.

## OUTPUT FORMAT
Return ONLY valid JSON matching this schema — no markdown fences, no explanation:

{
  "entities": [
    { "name": "Exact Name", "type": "concept|person|technology|organization|technique|other", "description": "One-sentence description" }
  ],
  "relationships": [
    { "source": "Entity A name", "target": "Entity B name", "type": "relates_to|uses|part_of|created_by|influences|contrasts_with|example_of|depends_on", "description": "Brief description of the relationship" }
  ]
}

## RULES
- Extract concrete, meaningful entities — not vague terms like "the model" or "the example"
- Normalize entity names: use canonical/full form (e.g. "GPT-4" not "gpt4", "Chain of Thought" not "CoT")
- Use SINGULAR form for entity names (e.g. "Token" not "Tokens", "Large Language Model" not "Large Language Models")
- Each relationship MUST reference entities that appear in the entities array
- Source and target in a relationship MUST be DIFFERENT entities — no self-references
- ONLY use relationship types from the allowed list above — do not invent new ones
- Prefer specific relationship types over generic "relates_to"
- If the chunk has no meaningful entities, return {"entities":[],"relationships":[]}
- Keep descriptions concise — max 20 words each
- Extract 3-15 entities per chunk (skip trivial ones)
- Every relationship needs both source and target in the entities list
```

### Extraction Model
- Use `gpt-5-mini` for entity/relationship extraction.

## Environment Variables
- `OPENAI_API_KEY` (required)
- `NEO4J_URI` (required)
- `NEO4J_USERNAME` (required)
- `NEO4J_PASSWORD` (required)

## Acceptance Criteria
- Chunking uses size 4000, overlap 500, with heading-based section metadata.
- Embedding model is `text-embedding-3-small` (dimension 1536).
- Graph schema includes:
  - Document nodes with `source` and `hash`.
  - Chunk nodes with `content`, `section`, `chunkIndex`, `embedding`.
  - Entity nodes with `name`, `type`, `description`, `embedding`.
  - Relationships `HAS_CHUNK`, `MENTIONS`, `RELATED_TO`.
- Hybrid search uses full-text index + vector index with RRF `k = 60`.
- `search` returns chunks + entities; `explore` and `connect` expose evidence sources.
- `cypher` is read-only and enforces a LIMIT if not present.
- `learn` can index a file or raw text; `forget` removes all data for a source.
- Entity/relationship extraction follows allowed types and removes self-relations.
