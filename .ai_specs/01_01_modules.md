# Coding Agent Instructions: Lesson 01 Modules (Grounding, Interaction, Structured)

**Goal Requirement**: Implement the following three tools as standard Django Views rendering HTMX partials. Use OpenRouter (`langchain-openai`) for all LLM calls. The frontend should heavily utilize Tailwind CSS for simple, clean styling.

## 1. Module `01_01_interaction`
**Objective**: Build a multi-turn chat interface that retains context.
*   **Backend Details**: 
    1.  Create a Django Model `ChatMessage` (fields: `session_id`, `role`, `content`, `timestamp`).
    2.  Create a Django service function `chat_with_agent(session_id: str, new_message: str) -> str`. This function should load memory from the database, append to a `langchain` prompt, call OpenRouter, and return the `AIMessage` content.
*   **Frontend (HTMX)**: 
    1.  Create a view `lesson_01_interaction_view` that renders the initial chat history UI (a scrollable div and an input form).
    2.  The form should use `<form hx-post="{% url 'interaction_api' %}" hx-target="#chat-history" hx-swap="beforeend">`.
    3.  The API endpoint should append the user's message, call `chat_with_agent`, and return purely the HTML snippet for the new user message AND the new AI response.

## 2. Module `01_01_structured`
**Objective**: Ensure the LLM outputs strict JSON mapped to defined schema.
*   **Backend Details**:
    1.  Define a Pydantic model representing the expected JSON structure (e.g., `EvaluationResult` with `score` and `reasoning`).
    2.  Use the `with_structured_output(EvaluationResult)` feature from `langchain` targeting an OpenRouter model.
*   **Frontend (HTMX)**:
    1.  Provide a form where the user submits text to be evaluated.
    2.  Submit via HTMX. The backend parses the resulting structured Pydantic object and returns a tailored HTML table or card displaying the extracted fields cleanly.

## 3. Module `01_01_grounding`
**Objective**: Basic Retrieval-Augmented Generation (RAG) using a local knowledge base.
*   **Backend Details**:
    1.  Use Python `pathlib` and Langchain document loaders to read local Markdown files.
    2.  Do *not* integrate external vector DBs. Use an in-memory `FAISS` store or `Chroma` local instance (or standard SQLite `pgvector` if strictly configured) to hold the embeddings. Note: Use `OpenAIEmbeddings` configured with openrouter if possible, or fallback to an open embedding model via HuggingFace for simplicity.
    3.  Implement a question-answering chain that fetches context from the vector store before prompting the LLM. 
*   **Frontend (HTMX)**:
    1.  A standard "Ask a Question" input box.
    2.  The response HTML snippet should highlight the fact-checked answer.
