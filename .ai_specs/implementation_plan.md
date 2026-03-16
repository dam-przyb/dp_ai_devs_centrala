# Implementation Plan: Damian's Operation Center (Django)

**Target**: A Django 5.x monolith with HTMX frontend, Tailwind CSS, OpenRouter LLM.
**Structure**: One Django app per lesson group + a `core` app for the shared shell.

---

## Phase 0 — Project Scaffold

### 0.1 File & Directory Layout

```
dp_ai_devs_centrala/
├── manage.py
├── requirements.txt
├── .env.example
├── tailwind.config.js          # (or use Tailwind CDN — see note)
├── sandbox/                    # Hardcoded filesystem sandbox for 01_02
├── knowledge_base/             # Markdown files for 01_01 grounding RAG
│   └── sample.md
├── media/                      # Django MEDIA_ROOT (uploads)
├── operation_center/           # Django project package
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── core/                       # Shared shell: layout, nav, base template
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py
│   ├── views.py
│   ├── nav_registry.py         # Central lesson/module navigation data
│   └── templates/
│       └── core/
│           ├── base.html
│           └── partials/
│               └── nav_menu.html
├── lesson_01/
├── lesson_02/
├── lesson_03/
├── lesson_04/
└── lesson_05/
```

### 0.2 `requirements.txt`

```
django>=5.0
python-dotenv
langchain
langchain-openai
langchain-community
langgraph
openai                  # for Whisper audio transcription
faiss-cpu               # for grounding RAG vector store
mcp                     # official MCP Python SDK
weasyprint              # PDF generation (lesson 04_reports)
httpx                   # for external API calls (video gen)
```

> **Tailwind**: Use the CDN `<script src="https://cdn.tailwindcss.com">` in `base.html` for simplicity (no build step). Add `tailwind.config.js` only if customization is needed.

### 0.3 `.env.example`

```
OPENROUTER_API_KEY=sk-or-...
OPENAI_API_KEY=sk-...           # used for Whisper (lesson 04)
MCP_SERVER_SCRIPT=npx -y @modelcontextprotocol/server-filesystem /tmp
KLING_API_KEY=...               # optional, lesson 04 video gen
REPLICATE_API_TOKEN=...         # optional, lesson 04 image editing
```

### 0.4 `operation_center/settings.py` key entries

```python
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

INSTALLED_APPS = [
    # django defaults ...
    "core",
    "lesson_01",
    "lesson_02",
    "lesson_03",
    "lesson_04",
    "lesson_05",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

SANDBOX_DIR = BASE_DIR / "sandbox"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-4o-mini"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")   # Whisper
MCP_SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT")
```

### 0.5 `operation_center/urls.py`

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("",        include("core.urls")),
    path("01/",     include("lesson_01.urls")),
    path("02/",     include("lesson_02.urls")),
    path("03/",     include("lesson_03.urls")),
    path("04/",     include("lesson_04.urls")),
    path("05/",     include("lesson_05.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## Phase 1 — Core App (Shell & Navigation)

### 1.1 `core/nav_registry.py`

Define a Python list of dicts describing the nav tree. Views use this to render the sidebar and to resolve module slugs.

```python
NAV = [
    {
        "chapter": "01",
        "label": "Lesson 01",
        "lessons": [
            {
                "id": "01_01",
                "label": "01_01 — Basics",
                "modules": [
                    {"slug": "interaction", "label": "Interaction", "url_name": "l01_interaction"},
                    {"slug": "structured",  "label": "Structured",  "url_name": "l01_structured"},
                    {"slug": "grounding",   "label": "Grounding",   "url_name": "l01_grounding"},
                ],
            },
        ],
    },
    { "chapter": "01", "label": "Lesson 02", "lessons": [
        { "id": "01_02", "label": "01_02 — Tool Use", "modules": [
            {"slug": "tools",    "label": "Minimal Tool",   "url_name": "l02_tools"},
            {"slug": "tool_use", "label": "FS Agent",       "url_name": "l02_tool_use"},
        ]},
    ]},
    { "chapter": "01", "label": "Lesson 03", "modules_flat": [
        {"slug": "mcp_core",       "label": "MCP Core",       "url_name": "l03_mcp_core"},
        {"slug": "mcp_native",     "label": "MCP Native",     "url_name": "l03_mcp_native"},
        {"slug": "mcp_translator", "label": "MCP Translator", "url_name": "l03_mcp_translator"},
        {"slug": "upload_mcp",     "label": "Upload MCP",     "url_name": "l03_upload_mcp"},
    ]},
    # ... lesson 04, lesson 05 entries
]
```

### 1.2 `core/views.py`

```python
from django.shortcuts import render
from .nav_registry import NAV

def dashboard(request):
    """Root view — renders the full shell with an empty workspace."""
    return render(request, "core/base.html", {"nav": NAV})
```

### 1.3 `core/urls.py`

```python
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
```

### 1.4 `core/templates/core/base.html`

Key structure:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <title>Damian's Operation Center</title>
</head>
<body class="flex flex-col h-screen overflow-hidden bg-gray-100">

  <!-- 1.2 Title Bar -->
  <header class="bg-gray-900 text-white px-6 py-3 flex-shrink-0">
    <h1 class="text-xl font-bold">Damian's Operation Center</h1>
  </header>

  <div class="flex flex-1 overflow-hidden">

    <!-- 1.3 Nav Bar -->
    <nav class="w-64 bg-gray-800 text-gray-200 flex-shrink-0 overflow-y-auto p-4">
      {% include "core/partials/nav_menu.html" with nav=nav %}
    </nav>

    <!-- 1.4 Workspace -->
    <main id="workspace-container"
          class="flex-grow overflow-y-auto p-6 bg-white">
      <p class="text-gray-400 text-sm">Select a module from the sidebar.</p>
    </main>

  </div>
</body>
</html>
```

### 1.5 `core/templates/core/partials/nav_menu.html`

Use Django template loops over `nav`. Each module link:
```html
<a href="#"
   hx-get="{% url module.url_name %}"
   hx-target="#workspace-container"
   hx-swap="innerHTML"
   class="block pl-6 py-1 text-sm hover:text-white hover:bg-gray-700 rounded">
  {{ module.label }}
</a>
```

---

## Phase 2 — Lesson 01 App

### 2.1 App layout

```
lesson_01/
├── __init__.py
├── apps.py
├── models.py
├── migrations/
├── urls.py
├── views/
│   ├── __init__.py
│   ├── interaction.py
│   ├── structured.py
│   └── grounding.py
├── services/
│   ├── __init__.py
│   ├── interaction_service.py
│   ├── structured_service.py
│   └── grounding_service.py
└── templates/
    └── lesson_01/
        ├── interaction.html
        ├── structured.html
        ├── grounding.html
        └── partials/
            ├── chat_message.html   # single message pair snippet
            ├── structured_result.html
            └── grounding_result.html
```

### 2.2 `lesson_01/models.py`

```python
from django.db import models

class ChatMessage(models.Model):
    session_id = models.CharField(max_length=64, db_index=True)
    role       = models.CharField(max_length=16)   # "human" | "ai"
    content    = models.TextField()
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]
```

### 2.3 `lesson_01/services/interaction_service.py`

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from django.conf import settings
from lesson_01.models import ChatMessage

def get_llm():
    return ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
    )

def chat_with_agent(session_id: str, new_message: str) -> str:
    history = ChatMessage.objects.filter(session_id=session_id)
    messages = [SystemMessage(content="You are a helpful assistant.")]
    for m in history:
        cls = HumanMessage if m.role == "human" else AIMessage
        messages.append(cls(content=m.content))
    messages.append(HumanMessage(content=new_message))

    response = get_llm().invoke(messages)
    ai_content = response.content

    ChatMessage.objects.create(session_id=session_id, role="human", content=new_message)
    ChatMessage.objects.create(session_id=session_id, role="ai",    content=ai_content)
    return ai_content
```

### 2.4 `lesson_01/services/structured_service.py`

```python
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from django.conf import settings

class EvaluationResult(BaseModel):
    score: int
    reasoning: str

def evaluate_text(text: str) -> EvaluationResult:
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
    )
    structured_llm = llm.with_structured_output(EvaluationResult)
    return structured_llm.invoke(
        f"Evaluate the following text on a scale from 1-10 and explain why:\n\n{text}"
    )
```

### 2.5 `lesson_01/services/grounding_service.py`

```python
from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from django.conf import settings

_vectorstore = None   # module-level singleton

def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        loader = DirectoryLoader(str(settings.KNOWLEDGE_BASE_DIR), glob="**/*.md",
                                 loader_cls=TextLoader)
        docs = loader.load()
        embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base=settings.OPENROUTER_BASE_URL,
            model="openai/text-embedding-3-small",
        )
        _vectorstore = FAISS.from_documents(docs, embeddings)
    return _vectorstore

def answer_question(question: str) -> str:
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
    )
    qa = RetrievalQA.from_chain_type(llm=llm,
                                     retriever=_get_vectorstore().as_retriever())
    return qa.invoke({"query": question})["result"]
```

### 2.6 `lesson_01/views/interaction.py`

```python
import uuid
from django.shortcuts import render
from django.http import HttpRequest
from lesson_01.models import ChatMessage
from lesson_01.services.interaction_service import chat_with_agent

def interaction_view(request: HttpRequest):
    """Initial workspace partial — renders chat shell."""
    session_id = request.session.setdefault("chat_session_id", str(uuid.uuid4()))
    messages   = ChatMessage.objects.filter(session_id=session_id)
    return render(request, "lesson_01/interaction.html",
                  {"messages": messages, "session_id": session_id})

def interaction_api(request: HttpRequest):
    """HTMX POST endpoint — returns only the new message pair HTML."""
    session_id  = request.session.get("chat_session_id", str(uuid.uuid4()))
    user_input  = request.POST.get("message", "")
    ai_response = chat_with_agent(session_id, user_input)
    return render(request, "lesson_01/partials/chat_message.html",
                  {"user_msg": user_input, "ai_msg": ai_response})
```

### 2.7 `lesson_01/urls.py`

```python
from django.urls import path
from .views import interaction, structured, grounding

urlpatterns = [
    path("interaction/",     interaction.interaction_view, name="l01_interaction"),
    path("interaction/api/", interaction.interaction_api,  name="l01_interaction_api"),
    path("structured/",      structured.structured_view,   name="l01_structured"),
    path("structured/api/",  structured.structured_api,    name="l01_structured_api"),
    path("grounding/",       grounding.grounding_view,     name="l01_grounding"),
    path("grounding/api/",   grounding.grounding_api,      name="l01_grounding_api"),
]
```

---

## Phase 3 — Lesson 02 App (Tool Use)

### 3.1 App layout

```
lesson_02/
├── services/
│   ├── weather_service.py      # @tool get_weather + manual loop
│   └── filesystem_agent_service.py  # @tool list_dir/read/write + AgentExecutor
├── views/
│   ├── tools.py
│   └── tool_use.py
└── templates/lesson_02/
    ├── tools.html
    ├── tool_use.html
    └── partials/
        ├── weather_result.html
        └── agent_result.html
```

### 3.2 `lesson_02/services/filesystem_agent_service.py` (security note)

```python
from pathlib import Path
from django.conf import settings
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

SANDBOX = settings.SANDBOX_DIR.resolve()

def _assert_safe(path: Path):
    resolved = (SANDBOX / path).resolve()
    if not str(resolved).startswith(str(SANDBOX)):
        raise PermissionError(f"Path traversal blocked: {resolved}")
    return resolved

@tool
def list_directory(subpath: str = ".") -> str:
    """List files in sandbox directory."""
    safe = _assert_safe(Path(subpath))
    return "\n".join(str(p.relative_to(SANDBOX)) for p in safe.iterdir())

@tool
def read_file(subpath: str) -> str:
    """Read a file from the sandbox."""
    return _assert_safe(Path(subpath)).read_text()

@tool
def write_file(subpath: str, content: str) -> str:
    """Write content to a file in the sandbox."""
    target = _assert_safe(Path(subpath))
    target.write_text(content)
    return f"Written {len(content)} chars to {subpath}"

def run_filesystem_agent(objective: str) -> dict:
    tools = [list_directory, read_file, write_file]
    llm   = ChatOpenAI(...)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a filesystem agent. Use tools to complete the objective."),
        ("human",  "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent    = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, return_intermediate_steps=True)
    result   = executor.invoke({"input": objective})
    return {"output": result["output"], "steps": result["intermediate_steps"]}
```

### 3.3 `lesson_02/urls.py`

```python
urlpatterns = [
    path("tools/",        views.tools.tools_view,        name="l02_tools"),
    path("tools/api/",    views.tools.tools_api,         name="l02_tools_api"),
    path("tool-use/",     views.tool_use.tool_use_view,  name="l02_tool_use"),
    path("tool-use/api/", views.tool_use.tool_use_api,   name="l02_tool_use_api"),
]
```

---

## Phase 4 — Lesson 03 App (MCP)

### 4.1 App layout

```
lesson_03/
├── services/
│   └── mcp_service.py      # StdioServerParameters, session helpers
├── views/
│   ├── mcp_core.py
│   ├── mcp_native.py
│   ├── mcp_translator.py
│   └── upload_mcp.py
└── templates/lesson_03/
```

### 4.2 `lesson_03/services/mcp_service.py`

```python
import asyncio, shlex
from django.conf import settings
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool

async def _list_tools_async():
    params = StdioServerParameters(command=shlex.split(settings.MCP_SERVER_SCRIPT)[0],
                                   args=shlex.split(settings.MCP_SERVER_SCRIPT)[1:])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            return await session.list_tools()

def list_mcp_tools():
    return asyncio.run(_list_tools_async())

def get_mcp_langchain_tools(session) -> list:
    """Map MCP tools JSON schema → LangChain StructuredTool list."""
    tools = []
    for t in asyncio.run(session.list_tools()).tools:
        def make_fn(name):
            async def fn(**kwargs):
                result = await session.call_tool(name, kwargs)
                return result.content[0].text
            return fn
        tools.append(StructuredTool.from_function(
            coroutine=make_fn(t.name), name=t.name, description=t.description))
    return tools
```

### 4.3 Notes on async Django views for MCP

Where `asyncio.run()` is inappropriate (already inside event loop), use `async def` Django views and `await` directly. The MCP views should be declared `async def` and use Django's async view support.

---

## Phase 5 — Lesson 04 App (Media)

### 5.1 App layout

```
lesson_04/
├── models.py           # VideoGenerationJob
├── services/
│   ├── audio_service.py         # Whisper transcription + OpenRouter summary
│   ├── video_generation_service.py  # Kling/Luma API call + job status
│   ├── image_service.py         # DALL-E 3 generation, Replicate editing
│   └── report_service.py        # WeasyPrint PDF generation
└── templates/lesson_04/
```

### 5.2 `lesson_04/models.py`

```python
class VideoGenerationJob(models.Model):
    task_id    = models.CharField(max_length=128, unique=True)
    prompt     = models.TextField()
    status     = models.CharField(max_length=32, default="pending")
    result_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 5.3 HTMX polling pattern for video generation

The view that initiates generation returns:
```html
<div hx-get="{% url 'l04_video_status' job_id=job.task_id %}"
     hx-trigger="every 5s"
     hx-swap="outerHTML">
  <p>Generating... (task {{ job.task_id }})</p>
</div>
```

The status view at `l04_video_status` with URL `/04/video/status/<task_id>/`:
- If pending → returns the polling div again (HTMX keeps polling)
- If done → returns `<video src="...">` (polling stops naturally since the new HTML has no `hx-trigger`)

---

## Phase 6 — Lesson 05 App (Orchestration)

### 6.1 App layout

```
lesson_05/
├── services/
│   ├── confirmation_service.py  # LangGraph with interrupt_before
│   └── orchestrator_service.py  # Supervisor: intent classify → delegate
└── templates/lesson_05/
    ├── confirmation.html
    └── agent.html
```

### 6.2 `lesson_05/services/confirmation_service.py`

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from django.conf import settings

# Graph state, nodes, and interrupt
def build_graph():
    builder = StateGraph(...)
    builder.add_node("plan_action", plan_action_node)
    builder.add_node("send_email_node", send_email_node)
    builder.set_entry_point("plan_action")
    builder.add_edge("plan_action", "send_email_node")
    builder.add_edge("send_email_node", END)
    memory = SqliteSaver.from_conn_string(str(settings.BASE_DIR / "db.sqlite3"))
    return builder.compile(checkpointer=memory, interrupt_before=["send_email_node"])
```

### 6.3 Two views for Human-in-the-Loop

```python
# View 1: initiate
def confirmation_start(request):
    graph  = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    state  = graph.invoke({"input": request.POST["task"]}, config)
    # graph halted → return confirmation UI with pending action details
    return render(request, "lesson_05/partials/confirm_prompt.html",
                  {"action": state["pending_action"], "thread_id": config["configurable"]["thread_id"]})

# View 2: resume
def confirmation_resume(request):
    from langgraph.types import Command
    thread_id = request.POST["thread_id"]
    graph     = build_graph()
    config    = {"configurable": {"thread_id": thread_id}}
    result    = graph.invoke(Command(resume=True), config)
    return render(request, "lesson_05/partials/confirm_done.html", {"result": result})
```

---

## Phase 7 — Template Conventions

All module templates are **partials** (no `<html>/<body>` wrapper) because HTMX injects them into `#workspace-container`. Example structure for a chat partial:

```html
{# lesson_01/interaction.html — full workspace partial #}
<div class="flex flex-col h-full">
  <div id="chat-history" class="flex-1 overflow-y-auto space-y-2 p-4">
    {% for msg in messages %}
      {% include "lesson_01/partials/chat_message.html" with user_msg=msg.content role=msg.role %}
    {% endfor %}
  </div>
  <form hx-post="{% url 'l01_interaction_api' %}"
        hx-target="#chat-history"
        hx-swap="beforeend"
        hx-on::after-request="this.reset()"
        class="flex gap-2 p-4 border-t">
    <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
    <input name="message" class="flex-1 border rounded px-3 py-2" placeholder="Type a message...">
    <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded">Send</button>
  </form>
</div>
```

---

## Phase 8 — Migrations & Initial Data

```bash
python manage.py makemigrations lesson_01 lesson_04
python manage.py migrate
mkdir sandbox knowledge_base
echo "# Sample knowledge\nThis app was built for AI Devs." > knowledge_base/sample.md
```

---

## Implementation Order for Coding Agent

Execute phases in this sequence to allow incremental testing:

1. **Phase 0** — scaffold project, settings, requirements, `.env`
2. **Phase 1** — `core` app: base template, nav registry, dashboard view
3. **Phase 2** — `lesson_01`: models → services → views → templates → urls → migrate
4. **Phase 3** — `lesson_02`: services (security-first) → views → templates → urls
5. **Phase 4** — `lesson_03`: async MCP service → views → templates
6. **Phase 5** — `lesson_04`: models → services → views → templates → migrate
7. **Phase 6** — `lesson_05`: LangGraph services → views → templates
8. **Final** — wire all lesson urls into main `operation_center/urls.py`, verify nav_registry entries match all url names

---

## Key Cross-Cutting Constraints

| Concern | Approach |
|---|---|
| LLM calls | Always via `langchain-openai` pointing to `OPENROUTER_BASE_URL` |
| HTMX responses | Never return full HTML page from API endpoints — partials only |
| CSRF | Include `{% csrf_token %}` in every `hx-post` form |
| Security (filesystem) | Always resolve + assert path is child of `SANDBOX_DIR` |
| Async | Use `async def` views only where explicitly needed (MCP lesson 03) |
| Database | SQLite default; no migrations needed for lessons 02, 03, 05 |
| Secrets | Load from `.env` via `python-dotenv`; never hardcode keys |
