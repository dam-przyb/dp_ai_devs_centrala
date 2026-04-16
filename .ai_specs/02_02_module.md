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

# Module 02_02 — Chunking, Embeddings, Hybrid RAG

## Module Overview
- Compare four chunking strategies side-by-side (characters, separators, context-enriched, topic-based).
- Demonstrate embeddings with an interactive similarity matrix.
- Build a hybrid RAG agent over SQLite FTS5 + vector search with Reciprocal Rank Fusion.

## What to Build
- A Django app `module_02_02` with three sections (or three pages):
  - **Chunking demo**: run 4 chunking strategies on a markdown file and show JSONL output.
  - **Embedding demo**: input multiple phrases and visualize cosine similarity matrix.
  - **Hybrid RAG**: index documents, then answer questions using a search tool (BM25 + vectors).

## User Interaction Flow
- Chunking
  - User selects a markdown file (default `workspace/example.md`) and clicks Run.
  - UI runs all four strategies and shows chunk counts + JSONL previews.
  - If LLM strategies are used (context, topics), show a token usage warning.
- Embeddings
  - User submits multiple short phrases (one per line).
  - UI displays the embedding preview (dim count) and a color-coded similarity matrix.
- Hybrid RAG
  - User enters a question; agent performs hybrid search and replies with citations.
  - UI provides buttons to `clear` conversation and `reindex` workspace files.

## Architecture
- `module_02_02/schemas.py`
  - `Chunk`, `ChunkMetadata`, `SearchResult`, `HybridAnswer`, `EmbeddingEntry`.
- `module_02_02/prompts.py`
  - Chunking prompts (context-enriched, topic-based).
  - Hybrid RAG system prompt (verbatim from JS config).
- `module_02_02/graphs.py`
  - LangGraph loop for the hybrid RAG agent.
- `module_02_02/services.py`
  - `run_chunking_demo(path)` — runs all four strategies and returns JSONL.
  - `embed_texts(entries)` — compute embeddings + cosine similarity matrix.
  - `run_hybrid_rag(query, history)` — agentic loop with search tool.
- `module_02_02/db.py`
  - SQLite schema (documents, chunks, FTS5, vec0) and initialization.
- `module_02_02/indexer.py`
  - Chunk, embed, insert; skip unchanged by SHA256 hash; prune stale docs.
- `module_02_02/search.py`
  - FTS search, vector search, and RRF fusion (k=60).
- `module_02_02/views.py`
  - `ChunkingView`, `EmbeddingView`, `HybridRagView` + HTMX partials.
- `module_02_02/templates/module_02_02/`
  - `index.html` and partials for each demo.

## LangGraph Graph Design
- **State (TypedDict)**
  - `messages: list[dict]`
  - `tool_calls: list[dict]`
  - `tool_results: list[dict]`
  - `step: int`
  - `final_answer: str | None`
- **Nodes**
  - `llm_step` — OpenAI Responses call with `search` tool.
  - `search_tool` — hybrid search (BM25 + vectors).
  - `finalize` — format answer with citations.
- **Edges**
  - `llm_step` → `search_tool` if tool calls exist.
  - `llm_step` → `finalize` if no tool calls.
  - `search_tool` → `llm_step`.

## Prompts

### Context-Enriched Chunking Prompt
```text
Generate a very short (1-2 sentence) context that situates this chunk within the overall document. Return ONLY the context, nothing else.
```

### Topic-Based Chunking Prompt
```text
You are a document chunking expert. Break the provided document into logical topic-based chunks.

Rules:
- Each chunk must contain ONE coherent topic or idea
- Preserve the original text — do NOT summarise or rewrite
- Return a JSON array of objects: [{ "topic": "short topic label", "content": "original text for this topic" }]
- Return ONLY the JSON array, no markdown fences or explanation
```

### Hybrid RAG System Prompt
```text
You are a knowledge assistant that answers questions by searching an indexed document database. You have a single tool — **search** — that performs hybrid retrieval (full-text BM25 + semantic vector similarity) over pre-indexed documents.

## WHEN TO SEARCH

- Use the search tool ONLY when the user asks a question or requests information that could be in the documents.
- Do NOT search for greetings, small talk, or follow-up clarifications that don't need document evidence.
- When in doubt whether to search, prefer searching.

## HOW TO SEARCH

- Start with a broad query, then refine with more specific terms based on what you find.
- Try multiple angles: synonyms, related concepts, specific names, and technical terms.
- If initial results are insufficient, search again with different keywords derived from partial findings.
- Stop searching only when you have enough evidence to answer confidently, or when repeated searches yield no new information.

## RULES

- Ground every claim in search results — cite the source file and section.
- If the information is not found, say so explicitly.
- When multiple chunks are relevant, synthesize across them.
- Be concise but thorough.
- Always mention which source files you consulted.
```

## Environment Variables
- `OPENAI_API_KEY` (required)

## Acceptance Criteria
- Chunking uses these parameters:
  - Characters: size 1000, overlap 200.
  - Separators: `\n## `, `\n### `, `\n\n`, `\n`, `. `, ` `, recursive split.
  - Section metadata uses heading index (markdown + plain-text headings).
- Context strategy calls LLM per chunk and stores a `context` field.
- Topic strategy returns JSON array of `{topic, content}` and preserves original text.
- Chunking outputs are saved as JSONL in `workspace/example-<strategy>.jsonl`.
- Embedding demo uses `text-embedding-3-small` and cosine similarity.
- Similarity matrix colors: >=0.60 green, >=0.35 yellow, else red.
- Hybrid RAG uses SQLite FTS5 + sqlite-vec with embedding dim 1536.
- RRF fusion uses `k = 60`, and vector search failures degrade gracefully to FTS only.
- Hybrid search tool requires both `keywords` and `semantic` inputs.
- REPL actions are mirrored in UI: clear history and reindex.
