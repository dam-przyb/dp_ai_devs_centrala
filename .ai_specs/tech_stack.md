# Technology Stack Specification

**Context**: This is an educational public repository. Simplicity and low barrier to entry are the primary goals. 

## 1. Backend Framework: Django Monolith
*   **Core**: Python 3.12+ with Django 5.x.
*   **Architecture**: Single monolithic application exposing HTML directly. Do not use Django REST Framework or Django Ninja to decouple the frontend unless specifically necessary for an MCP integration.
*   **Database**: SQLite for development (default out-of-the-box Django behavior) or standard PostgreSQL if a vector-database extension (`pgvector`) is explicitly required by the lessons.

## 2. LLM Provider: OpenRouter
*   **Provider**: OpenRouter is the sole LLM gateway to be used. 
*   **Libraries**: Use `langchain-openai` (since OpenRouter provides an OpenAI-compatible endpoint) or the official `openai` Python SDK configured to point to `https://openrouter.ai/api/v1`.
*   **Model Strings**: Default to open/cheap models available via OpenRouter unless a specific feature (like Gemini's native video processing) is strictly required by the lesson.

## 3. Frontend & UI
*   **Templating**: Standard Django Django Templates (HTML).
*   **Interactivity**: HTMX. Instead of forms doing full page reloads, use `hx-post` to push data to the backend, and target specific DOM elements (`hx-target`) to swap the response HTML (`hx-swap="innerHTML"`).
*   **Styling**: Tailwind CSS (via Tailwind CLI or CDN for simplicity). Use standard Tailwind utility classes to construct the layout.

## 4. Asynchronous Tooling
*   **Background Jobs**: Do not use complex message brokers like Celery/Redis. To keep the educational setup simple, rely on synchronous processing where possible. If async is strictly necessary for long-running LLM processes, consider using Python's built-in `asyncio` with Django's asynchronous views (`async def`), or a lightweight background queue like Django-Q2 or Huey.
