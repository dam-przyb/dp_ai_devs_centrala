# Damian's Operation Center

An educational Django application covering the core AI-engineering patterns from the **AI Devs 4 — Builders** course. Each lesson is a fully working module accessible from a unified sidebar, demonstrating a different LLM integration technique.

---

## What the app can do

| Module | Path | Capability |
|---|---|---|
| **Interaction (Chat)** | `01 — Basics › Interaction` | Persistent multi-turn chat powered by an OpenRouter LLM. Conversation history is stored in SQLite. |
| **Structured Output** | `01 — Basics › Structured Output` | Prompts the LLM to return typed JSON (via Pydantic schemas) and displays the parsed result. |
| **Grounding (RAG)** | `01 — Basics › Grounding` | Retrieval-Augmented Generation: indexes Markdown files from `knowledge_base/` into a FAISS vector store, then answers questions using only grounded context. |
| **Minimal Tool** | `02 — Tool Use › Minimal Tool` | Shows the bare-minimum pattern for giving an LLM a single callable tool. |
| **FS Agent** | `02 — Tool Use › FS Agent` | A LangChain agent with filesystem tools (list, read, write, search) sandboxed to the `sandbox/` directory. |
| **MCP Core** | `03 — MCP › MCP Core` | Lists tools exposed by an MCP server and calls them directly via the MCP Python SDK. |
| **MCP Native** | `03 — MCP › MCP Native` | Raw `ClientSession` demo — shows the MCP wire protocol without LangChain. |
| **MCP Translator** | `03 — MCP › MCP Translator` | Wraps MCP tools as LangChain `StructuredTool` objects and runs a ReAct agent over them. |
| **Upload MCP** | `03 — MCP › Upload MCP` | Upload a file → send it to an MCP-backed agent → get an AI summary. |
| **Audio Transcription** | `04 — Media › Audio` | Upload an audio file → Whisper transcribes it → OpenRouter summarises the transcript. |
| **Video Generation** | `04 — Media › Video` | Submit a prompt → background job tracks generation status with HTMX polling (mocked; swap in Kling/Luma API key to go live). |
| **Image Generation** | `04 — Media › Image` | Generate images from a text prompt via DALL-E 3 through OpenRouter. |
| **PDF Report** | `04 — Media › Report` | Compose a multi-section report in the browser, preview it live, and download as PDF (WeasyPrint). |
| **Human-in-the-Loop** | `05 — Orchestration › Human-in-the-Loop` | LangGraph graph with `interrupt_before` — the LLM drafts an email action, pauses, and waits for your approval before executing. State is checkpointed in SQLite across HTTP requests. |
| **Master Orchestrator** | `05 — Orchestration › Master Orchestrator` | Supervisor agent that classifies your intent (chat / filesystem / media / MCP) via an LLM router and delegates to the appropriate sub-agent from previous lessons. |

---

## Tech stack

- **Backend**: Python 3.12 · Django 5 · SQLite
- **LLM**: [OpenRouter](https://openrouter.ai) (OpenAI-compatible endpoint) via `langchain-openai`
- **Agents / Graphs**: LangChain · LangGraph
- **Vector store**: FAISS (`faiss-cpu`)
- **Frontend**: Django Templates · [HTMX](https://htmx.org) · Tailwind CSS (CDN)
- **Audio**: OpenAI Whisper (`openai` SDK)
- **PDF**: WeasyPrint
- **MCP**: `mcp` Python SDK

---

## Setup

### 1. Clone & create a virtual environment

```bash
git clone <repo-url>
cd dp_ai_devs_centrala
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
OPENROUTERKEY=sk-or-...          # required — all LLM calls go here

# Optional — only needed for specific lessons:
OPENAI_API_KEY=sk-...            # Lesson 04 Audio (Whisper)
MCP_SERVER_SCRIPT=npx -y @modelcontextprotocol/server-filesystem /tmp
                                 # Lesson 03 MCP modules
```

> **Note**: The env key for OpenRouter is `OPENROUTERKEY` (no underscore), not `OPENROUTER_API_KEY`.

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Start the development server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Project layout

```
dp_ai_devs_centrala/
├── core/                  # Shared shell: base template, nav registry, dashboard
├── lesson_01/             # Basics: chat, structured output, RAG
├── lesson_02/             # Tool use: minimal tool, filesystem agent
├── lesson_03/             # MCP: core, native, translator, file upload
├── lesson_04/             # Media: audio, video, image, PDF report
├── lesson_05/             # Orchestration: human-in-the-loop, master orchestrator
├── knowledge_base/        # Markdown files indexed for RAG (Lesson 01 Grounding)
├── sandbox/               # Sandboxed filesystem for the FS Agent (Lesson 02)
├── media/                 # Django MEDIA_ROOT (uploaded files)
├── operation_center/      # Django project package (settings, urls, wsgi)
└── manage.py
```

---

## Notes

- **MCP modules** require a running MCP server process. Set `MCP_SERVER_SCRIPT` in `.env` (e.g. `npx -y @modelcontextprotocol/server-filesystem /tmp`). Node.js must be installed.
- **Audio transcription** uses the OpenAI Whisper API directly — an `OPENAI_API_KEY` is required; Whisper is not available via OpenRouter.
- **Video generation** is mocked by default. To use a real provider, implement the client in `lesson_04/services/video_generation_service.py`.
- All LLM calls default to `openai/gpt-4o-mini` via OpenRouter. Change `OPENROUTER_DEFAULT_MODEL` in `operation_center/settings.py` to use a different model.
