# Season 2 — Implementation Plan

**Target:** 5 new Django apps (`module_02_01` → `module_02_05`) for the "Advanced Agents" season.  
**Stack:** Django 5.x · LangGraph · HTMX · OpenRouter (`openai/gpt-5-mini` via `OPENROUTER_API_KEY`) · SQLite · `quickjs` Python binding · NetworkX (Graph RAG fallback — no Neo4j required).  
**Approach:** Season 2 is developed in parallel with any remaining `lesson_05` work. All Season 2 apps live alongside Season 1 apps in the same Django project root.

---

## Decisions Log

| Question | Decision |
|---|---|
| App naming | Spec naming: `module_02_01` … `module_02_05` |
| lesson_05 dependency | Develop in parallel |
| Neo4j | NetworkX + SQLite fallback (no external graph DB) |
| LLM model | OpenRouter · `openai/gpt-5-mini` (use `openai/gpt-4o-mini` as fallback if needed) |
| JS sandbox | `quickjs` Python binding (`pip install quickjs`) |

---

## URL Naming Convention

Season 2 apps use the prefix `m02XX_` to avoid collision with Season 1's `l01_`…`l05_` prefix.

| App | URL prefix | Example names |
|---|---|---|
| `module_02_01` | `m0201_` | `m0201_rag_agent` |
| `module_02_02` | `m0202_` | `m0202_chunking`, `m0202_embeddings`, `m0202_hybrid_rag` |
| `module_02_03` | `m0203_` | `m0203_graph_rag` |
| `module_02_04` | `m0204_` | `m0204_daily_ops` |
| `module_02_05` | `m0205_` | `m0205_memory_chat`, `m0205_sandbox` |

---

## Phase 0 — Project Scaffold & Cross-Cutting Setup

### Step 0.1 — Install new dependencies

Add to `requirements.txt`:

```
quickjs>=1.19.4          # JS sandbox for module_02_05
networkx>=3.4            # Graph RAG fallback for module_02_03
sqlite-vec>=0.1.6        # Vector search extension for modules 02_02 and 02_03
```

Run:
```
pip install quickjs networkx sqlite-vec
```

### Step 0.2 — Register apps in `operation_center/settings.py`

Append to `INSTALLED_APPS`:
```python
"module_02_01",
"module_02_02",
"module_02_03",
"module_02_04",
"module_02_05",
```

### Step 0.3 — Wire URL prefixes in `operation_center/urls.py`

```python
path("s2/01/", include("module_02_01.urls")),
path("s2/02/", include("module_02_02.urls")),
path("s2/03/", include("module_02_03.urls")),
path("s2/04/", include("module_02_04.urls")),
path("s2/05/", include("module_02_05.urls")),
```

### Step 0.4 — Update `core/nav_registry.py` Season 2 entries

Once each Phase creates its URL names, update the Season 2 `url_name` fields in `nav_registry.py`.  
Specific updates are listed at the end of each Phase below.

---

## Phase 1 — `module_02_01`: Agentic RAG (File Tools)

**Goal:** An agentic chat that explores local course materials via list/search/read tools before answering.

### Step 1.1 — Create app skeleton

```
module_02_01/
  __init__.py
  apps.py                  # Module02_01Config, name="module_02_01"
  urls.py
  schemas.py               # FileListing, SearchMatch, SearchResult, ToolCall, ToolResult, AgentReply
  prompts.py               # SYSTEM_PROMPT (verbatim from spec)
  graphs.py                # LangGraph: llm_step → tool_step → llm_step | finalize
  services.py              # run_agentic_rag(query, history) + file tools
  views.py                 # IndexView (GET), ChatView (POST HTMX), ClearView (POST HTMX)
  templates/module_02_01/
    index.html
    partials/
      _chat_result.html
      _history.html
      _error.html
```

### Step 1.2 — File tools (scoped to `_lessons_texts/`)

Implement in `services.py`:
- `list_dir(path: str) -> FileListing` — directory listing, path must be inside root.
- `search_text(query: str) -> SearchResult` — recursive grep-like scan returning file + line ranges.
- `read_file(path: str, start_line: int, end_line: int) -> str` — returns lines slice; enforces root scope.
- Security: reject any path that escapes the document root (`os.path.abspath` + `startswith` check).

### Step 1.3 — LangGraph design

**State:** `messages`, `tool_calls`, `tool_results`, `sources`, `step`, `max_steps` (50), `final_answer`.  
**Nodes:** `llm_step` · `tool_step` · `finalize`.  
**Edges:** `llm_step → tool_step` (tool calls present) | `llm_step → finalize` (no calls) · `tool_step → llm_step`.

### Step 1.4 — LLM config

```python
model = "openai/gpt-5-mini"   # via OpenRouter
max_tokens = 16384
# reasoning effort not available on gpt-5-mini; omit
```

Use `OPENROUTER_API_KEY` env var.

### Step 1.5 — HTMX UI

- `index.html`: token-usage warning, document-root display, chat input, source list.
- `_chat_result.html`: final answer + source citations (file + line range).
- `_history.html`: previous turns rendered as chat bubbles.
- Session state: store `history` and `usage` in `request.session` (keyed by view slug).
- "Clear" button: POST to `ClearView` which wipes session key and returns empty chat fragment.

### Step 1.6 — URLs

```python
# module_02_01/urls.py
path("",       IndexView.as_view(),  name="m0201_rag_agent"),
path("chat/",  ChatView.as_view(),   name="m0201_rag_chat"),
path("clear/", ClearView.as_view(),  name="m0201_rag_clear"),
```

### Step 1.7 — Update nav_registry.py

```python
# Season 2 → "06 — Agentic RAG" → module slug "rag_agent"
"url_name": "m0201_rag_agent",
```

---

## Phase 2 — `module_02_02`: Chunking, Embeddings, Hybrid RAG

**Goal:** Three interactive demos — chunking strategies, embedding similarity matrix, hybrid RAG chat.

### Step 2.1 — Create app skeleton

```
module_02_02/
  __init__.py
  apps.py
  urls.py
  schemas.py               # Chunk, ChunkMetadata, SearchResult, HybridAnswer, EmbeddingEntry
  prompts.py               # Context-enriched prompt, topic-based prompt, hybrid RAG system prompt
  graphs.py                # LangGraph: hybrid RAG agent loop
  services.py              # run_chunking_demo, embed_texts, run_hybrid_rag
  db.py                    # SQLite schema init: documents, chunks, FTS5, sqlite-vec
  indexer.py               # Chunk → embed → insert; SHA256 dedup; prune stale docs
  search.py                # FTS search, vector search, RRF fusion (k=60)
  views.py                 # ChunkingView, EmbeddingView, HybridRagView + HTMX partials
  templates/module_02_02/
    index.html             # Tab-based layout for three demos
    partials/
      _chunking_result.html
      _embedding_matrix.html
      _rag_result.html
  workspace/
    example.md             # Sample markdown file for chunking demo
```

### Step 2.2 — Four chunking strategies

All implemented in `services.py → run_chunking_demo(path)`:

1. **Characters** — fixed size 1000, overlap 200.
2. **Separators** — recursive split on `\n## `, `\n### `, `\n\n`, `\n`, `. `, ` ` — with heading-level section metadata.
3. **Context-enriched** — call LLM per chunk with the context prompt; store `context` field alongside `content`.
4. **Topic-based** — single LLM call returning JSON array of `{topic, content}`; preserve original text.

Output: JSONL written to `workspace/example-<strategy>.jsonl`; return JSONL previews + chunk counts.

### Step 2.3 — Embedding demo

- Use `text-embedding-3-small` (via OpenAI SDK, `OPENAI_API_KEY` or OpenRouter).
- Cosine similarity matrix: green ≥ 0.60, yellow ≥ 0.35, red below.
- Render matrix as an HTML table with Tailwind color classes.

### Step 2.4 — Hybrid RAG + SQLite

- `db.py`: initialize `documents`, `chunks` tables + FTS5 virtual table + `sqlite-vec` extension.
- `indexer.py`: chunk → embed (`text-embedding-3-small`, dim 1536) → insert; skip if SHA256 unchanged.
- `search.py`: FTS BM25 search, vector cosine search, RRF fusion (`k=60`); graceful fallback to FTS-only if vector fails.
- LangGraph agent: single `search` tool requiring both `keywords` and `semantic` inputs.

### Step 2.5 — URLs

```python
path("chunking/",   ChunkingView.as_view(),  name="m0202_chunking"),
path("embeddings/", EmbeddingView.as_view(), name="m0202_embeddings"),
path("hybrid-rag/", HybridRagView.as_view(), name="m0202_hybrid_rag"),
# HTMX action endpoints
path("chunking/run/",    chunking_run_api,    name="m0202_chunking_run"),
path("embeddings/run/",  embeddings_run_api,  name="m0202_embeddings_run"),
path("hybrid-rag/chat/", hybrid_rag_chat_api, name="m0202_hybrid_rag_chat"),
path("hybrid-rag/clear/",hybrid_rag_clear_api,name="m0202_hybrid_rag_clear"),
path("hybrid-rag/reindex/", hybrid_rag_reindex_api, name="m0202_hybrid_rag_reindex"),
```

### Step 2.6 — Update nav_registry.py

```python
"url_name": "m0202_chunking",     # Chunking Demo
"url_name": "m0202_embeddings",   # Embeddings Demo
"url_name": "m0202_hybrid_rag",   # Hybrid RAG
```

---

## Phase 3 — `module_02_03`: Graph RAG Agents (NetworkX + SQLite fallback)

**Goal:** Graph-based RAG using NetworkX + SQLite instead of Neo4j (same agent tools, local storage).

### Step 3.1 — Create app skeleton

```
module_02_03/
  __init__.py
  apps.py
  urls.py
  schemas.py               # Chunk, Entity, Relationship, SearchResponse, PathResult, GraphAnswer
  prompts.py               # Agent system prompt, entity/relationship extraction prompt
  graphs.py                # LangGraph agent loop with all graph tools
  graph/
    __init__.py
    store.py               # NetworkX DiGraph + SQLite persistence (load/save on startup/shutdown)
    schema.py              # SQLite table definitions: documents, chunks, entities, relationships
    indexer.py             # read → chunk → embed → extract entities → embed entities → write
    search.py              # FTS search, vector search (sqlite-vec), RRF + NetworkX traversal
  services.py              # run_graph_rag(query, history), index_workspace()
  views.py                 # IndexView, ChatView, ReindexView, LearnView, ForgetView
  templates/module_02_03/
    index.html
    partials/
      _chat_result.html
      _error.html
  workspace/               # Default document root for indexing
```

### Step 3.2 — NetworkX graph as Neo4j substitute

- On startup, load all entity/relationship rows from SQLite into a `networkx.DiGraph` instance (app-level singleton via `AppConfig.ready()`).
- Persist changes back to SQLite after each `learn` / `forget` / `merge_entities`.
- Tool mapping:
  - `search` → FTS + sqlite-vec RRF on chunks, annotate with entities mentioned.
  - `explore` → `nx.neighbors(entity)` — return N-hop subgraph as structured JSON.
  - `connect` → `nx.shortest_path(source, target)` — return path as entity chain.
  - `cypher` → **disabled / not applicable**; replace with a `graph_stats` tool returning counts and top-connected nodes.
  - `learn` → index a file or raw text; update SQLite + NetworkX graph.
  - `forget` → delete all chunks/entities for a source from SQLite + NetworkX.
  - `merge_entities` → merge duplicate entity nodes in NetworkX + update SQLite refs.
  - `audit` → return health metrics (orphan nodes, duplicate names, unconnected chunks).

### Step 3.3 — Entity/relationship extraction

- Model: `openai/gpt-5-mini` via OpenRouter.
- Use verbatim extraction prompt from spec.
- Validate output: remove self-relations, enforce allowed relationship types.

### Step 3.4 — URLs

```python
path("",        IndexView.as_view(),   name="m0203_graph_rag"),
path("chat/",   ChatView.as_view(),    name="m0203_graph_chat"),
path("reindex/",ReindexView.as_view(), name="m0203_reindex"),
path("learn/",  LearnView.as_view(),   name="m0203_learn"),
path("forget/", ForgetView.as_view(),  name="m0203_forget"),
```

### Step 3.5 — Update nav_registry.py

```python
"url_name": "m0203_graph_rag",
```

---

## Phase 4 — `module_02_04`: Daily Ops Multi-Agent Workflow

**Goal:** Multi-agent orchestrator that reads file-based workspace sources and generates a daily note.

### Step 4.1 — Create app skeleton

```
module_02_04/
  __init__.py
  apps.py
  urls.py
  schemas.py               # MailItem, CalendarEvent, TaskItem, NoteItem, DailyOpsResult
  prompts.py               # Orchestrator, mail, calendar, tasks, notes agent prompts + workflow template
  graphs.py                # Orchestrator LangGraph loop (max 15 turns, depth 3)
  services.py              # run_orchestrator(date), delegate(agent, task), tool handlers
  views.py                 # IndexView, GenerateView (HTMX POST)
  templates/module_02_04/
    index.html
    partials/
      _result.html
      _error.html
  workspace/
    agents/
      orchestrator.agent.md
      mail.agent.md
      calendar.agent.md
      tasks.agent.md
      notes.agent.md
    workflows/
      daily-ops.md         # Workflow template (7 steps, from spec)
    goals/
      goals.md             # Sample goals document
    history/
      2026-02-12.md        # Sample yesterday output for dedup
    memory/
      preferences.md       # Sample preferences
    sources/
      mail.json            # Sample inbox data
      calendar.json        # Sample calendar data
      tasks.json           # Sample task list
      notes.json           # Sample notes
    output/                # Generated daily notes land here
```

### Step 4.2 — LangGraph orchestrator design

**Max turns:** 15 (orchestrator loop) · **Delegation depth:** 3 (subagent loops capped at 5 turns each).  
**Tools available to orchestrator:** `read_file`, `write_file`, `delegate`.  
**Tools available to subagents:** `get_mail`, `get_calendar`, `get_tasks`, `get_notes`.

All `read_file` / `write_file` paths are relative to the `workspace/` directory and must not escape it.

### Step 4.3 — Subagent delegation

`delegate(agent: str, task: str) -> str` spawns a synchronous nested LangGraph run:
- Load agent config from `workspace/agents/<agent>.agent.md`.
- Run a mini-loop (max 5 turns) with the agent's tools.
- Return the agent's final text output.

### Step 4.4 — URLs

```python
path("",         IndexView.as_view(),    name="m0204_daily_ops"),
path("generate/",GenerateView.as_view(), name="m0204_generate"),
```

### Step 4.5 — Update nav_registry.py

```python
"url_name": "m0204_daily_ops",
```

---

## Phase 5 — `module_02_05`: Observational Memory + Sandbox Agent

**Goal:** Session-based agent with observer/reflector memory compression + a quickjs-powered JS sandbox agent.

### Step 5.1 — Create app skeleton

```
module_02_05/
  __init__.py
  apps.py
  models.py                # Session, Message (optional — or use Django sessions)
  urls.py
  schemas.py               # Message, FunctionCall, FunctionCallOutput, Session, MemoryState
                           # ObserverResult, ReflectorResult, SandboxResult
  prompts.py               # Alice agent, observer system prompt, reflector system prompt, sandbox agent prompt
  graphs.py                # Memory agent LangGraph + sandbox agent LangGraph
  services.py              # run_memory_agent(session, user_message), process_memory(), run_sandbox_agent(task)
  sandbox.py               # quickjs execution wrapper with time + memory limits
  tools.py                 # Memory tools (read_file, write_file workspace-scoped)
                           # Sandbox tools (list_servers, list_tools, get_tool_schema, execute_code)
  views.py                 # MemoryChatView, SessionListView, FlushMemoryView, SandboxView
  templates/module_02_05/
    memory_chat.html
    sandbox.html
    partials/
      _memory_message.html
      _memory_stats.html
      _sandbox_result.html
  workspace/
    agents/
      alice.agent.md
      sandbox.agent.md
    notes/
      example.md
    memory/                # Observer/reflector logs written here at runtime
```

### Step 5.2 — Observational memory cycle

Thresholds (from spec):
- **Observation trigger:** accumulated conversation since last observation ≥ 400 tokens → run observer.
- **Reflection trigger:** observation XML size ≥ 400 tokens → run reflector to compress.

Observer node: call LLM with observer prompt; parse `<observations>` XML; append to `MemoryState.observations`.  
Reflector node: call LLM with reflector prompt; replace `MemoryState.observations` with compressed output.

Session storage: Django `request.session` — store `messages`, `memory` as JSON; session key = `memory_chat_<session_id>`.

### Step 5.3 — quickjs sandbox

`sandbox.py`:
```python
import quickjs

def execute_js(code: str, timeout_ms: int = 5000) -> dict:
    """
    Execute JS code in a QuickJS context.

    Returns {"result": ..., "logs": [...], "error": str | None}.
    Enforces time limit via quickjs timeout; memory limit via context options.
    Console.log calls are captured and returned as logs list.
    """
```

- Console output captured by injecting a `console` shim before execution.
- Any unhandled exception is returned as `error` string — does not crash Django worker.
- Execution is synchronous (quickjs is not async).

### Step 5.4 — Sandbox agent tools

Simulated MCP discovery (no live MCP server needed for demo):
- `list_servers()` → return static list from `workspace/agents/sandbox.agent.md`.
- `list_tools(server)` → return tool metadata from the agent config file.
- `get_tool_schema(server, tool)` → return JSON schema from agent config.
- `execute_code(code)` → call `sandbox.execute_js(code)`.

### Step 5.5 — URLs

```python
path("memory/",        MemoryChatView.as_view(),   name="m0205_memory_chat"),
path("memory/chat/",   memory_chat_api,             name="m0205_memory_api"),
path("memory/flush/",  FlushMemoryView.as_view(),  name="m0205_flush"),
path("memory/sessions/",SessionListView.as_view(), name="m0205_sessions"),
path("sandbox/",       SandboxView.as_view(),       name="m0205_sandbox"),
path("sandbox/run/",   sandbox_run_api,             name="m0205_sandbox_run"),
```

### Step 5.6 — Update nav_registry.py

```python
"url_name": "m0205_memory_chat",   # Observational Memory Chat
"url_name": "m0205_sandbox",       # MCP Sandbox Agent
```

---

## Phase 6 — Wiring & Smoke Tests

### Step 6.1 — Migrations

```bash
python manage.py makemigrations module_02_01 module_02_02 module_02_03 module_02_04 module_02_05
python manage.py migrate
```

(Most Season 2 apps use session/file storage; only `module_02_05` may need a `Session`/`Message` model migration.)

### Step 6.2 — Nav registry final update

Verify all 10 Season 2 `url_name` values in `core/nav_registry.py` resolve without Django errors:

```bash
python manage.py shell -c "from django.urls import reverse; [reverse(n) for n in ['m0201_rag_agent', 'm0202_chunking', 'm0202_embeddings', 'm0202_hybrid_rag', 'm0203_graph_rag', 'm0204_daily_ops', 'm0205_memory_chat', 'm0205_sandbox']]"
```

### Step 6.3 — Smoke test checklist

| Module | Smoke test |
|---|---|
| `module_02_01` | Ask a question; verify agent calls list/search tools before answering |
| `module_02_02` | Run chunking on `example.md`; see 4 JSONL outputs; embed 3 phrases; get green cell for identical phrases |
| `module_02_02` | Ask hybrid RAG a question about indexed content; get cited answer |
| `module_02_03` | Index workspace; ask relational question; verify `explore` tool fires |
| `module_02_04` | Click "Generate Daily Ops"; verify markdown note written to `output/YYYY-MM-DD.md` |
| `module_02_05` | Send 3 messages; flush memory; verify observer XML appears in session; send follow-up |
| `module_02_05` | Submit sandbox task; verify JS executes and console logs appear |

### Step 6.4 — session_progress.md update

After each Phase completes, update `.ai_specs/session_progress.md` to mark the module done.

---

## Environment Variables Required (Season 2)

| Variable | Used by | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | all modules | Primary LLM gateway |
| `OPENAI_API_KEY` | 02_02 embeddings | `text-embedding-3-small` (or proxy via OpenRouter) |

No new secrets beyond what Season 1 already uses.

---

## Dependency Summary

```
# Season 2 additions to requirements.txt
quickjs>=1.19.4
networkx>=3.4
sqlite-vec>=0.1.6
```

---

## Implementation Order

```
Phase 0  →  Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6
 Scaffold    Agentic     Chunking/    Graph       Daily Ops   Memory +    Wiring
             RAG         Embeddings   RAG                     Sandbox
```

Each Phase is self-contained and can be merged independently.  
Season 2 does not block or depend on completing `lesson_05`.
