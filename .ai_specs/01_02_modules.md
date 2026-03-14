# Coding Agent Instructions: Lesson 02 Modules (Tool Use)

**Goal Requirement**: Implement tool-calling (function calling) capabilities using a Django backend and OpenRouter.

## 1. Module `01_02_tools` (Minimal API Tool)
**Objective**: Bind a single, simple Python function to the LLM.
*   **Backend Details**:
    1.  Define a simple Python tool using the Langchain `@tool` decorator (`get_weather(location: str) -> str`).
    2.  Instantiate the OpenRouter LLM using `langchain-openai`.
    3.  Bind the tool: `llm.bind_tools([get_weather])`.
    4.  Create a Django service that handles the raw workflow: receive prompt -> call LLM -> if LLM requests tool, execute the python function -> pass function result back to LLM -> return final string to user.
*   **Frontend (HTMX)**:
    1.  Provide an input specifically for asking weather. The returned HTML snippet should display the final answer.

## 2. Module `01_02_tool_use` (Sandboxed File System Tools)
**Objective**: Provide the LLM with an array of tools allowing it to interact with the local filesystem securely.
*   **Backend Details**:
    1.  Define Python tools for filesystem operations: `list_directory`, `read_file`, `write_file`.
    2.  **Security**: Hardcode a sandbox directory (e.g., `settings.BASE_DIR / 'sandbox'`). Inside the tools, assert that the resolved path is always a child of the sandbox directory to prevent path traversal attacks.
    3.  Initialize a LangChain agent (`create_tool_calling_agent`) with these tools and an `AgentExecutor`.
*   **Frontend (HTMX)**:
    1.  The UI should have a text area for "Agent Objective" (e.g., "Summarize all `.txt` files in the folder").
    2.  The HTMX endpoint should trigger the agent run and return an HTML partial that lists the "Agent Thoughts" (steps taken) and the final "Agent Output".
