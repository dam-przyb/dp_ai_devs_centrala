# Project Memory: dp_ai_devs_centrala

## Project Overview
"Damian's Operation Center" — Django 5.x monolith with HTMX + Tailwind CSS.
Educational AI Devs course app showcasing LLM patterns (chat, RAG, tool use, MCP, media, agents).

## Key Files
- `.ai_specs/implementation_plan.md` — Full implementation plan (phases 0-8)
- `.ai_specs/general_architecture.md` — Dashboard layout, HTMX routing strategy
- `.ai_specs/tech_stack.md` — Django 5.x, OpenRouter via langchain-openai, SQLite, HTMX, Tailwind CDN
- `.ai_specs/01_01_modules.md` — Lesson 01: interaction (chat), structured output, grounding (RAG)
- `.ai_specs/01_02_modules.md` — Lesson 02: minimal tool (@tool weather), filesystem agent (sandboxed)
- `.ai_specs/01_03_modules.md` — Lesson 03: MCP core/native/translator/upload
- `.ai_specs/01_04_modules.md` — Lesson 04: audio/video transcription, video gen polling, image gen, PDF reports
- `.ai_specs/01_05_modules.md` — Lesson 05: LangGraph human-in-the-loop, master orchestrator

## App Structure
- `operation_center/` — Django project package (settings, urls)
- `core/` — shell: base.html, nav sidebar, nav_registry.py
- `lesson_01/` through `lesson_05/` — one Django app per lesson group
- Each lesson app: `views/`, `services/`, `templates/lesson_XX/`, `urls.py`

## LLM Setup
- Provider: OpenRouter only (`https://openrouter.ai/api/v1`)
- Library: `langchain-openai` (ChatOpenAI with custom base_url)
- Default model: `openai/gpt-4o-mini` (cheap/fast)
- Embeddings: `OpenAIEmbeddings` pointed at OpenRouter model `openai/text-embedding-3-small`
- Whisper: standard `openai` SDK (separate OPENAI_API_KEY)

## HTMX Conventions
- Nav clicks: `hx-get="<url>" hx-target="#workspace-container" hx-swap="innerHTML"`
- All module templates are partials (no html/body wrapper)
- Chat: `hx-swap="beforeend"` on `#chat-history` div
- Long polls: `hx-trigger="every 5s"` — stop by returning HTML without the trigger attribute

## Key Constraints
- No DRF/Django Ninja — pure Django views return HTML partials
- No Celery/Redis — synchronous or Django async views
- Tailwind via CDN (no build step)
- Filesystem sandbox: always assert resolved path starts with SANDBOX_DIR
- SQLite default; pgvector only if explicitly needed
