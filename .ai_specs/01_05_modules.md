# Coding Agent Instructions: Lesson 05 Modules (Agent Orchestration)

**Goal Requirement**: Final culmination modules covering Multi-Agent and Human-in-the-Loop configurations.

## 1. Module `01_05_confirmation` (Human-in-the-Loop)
**Objective**: Halt agent execution pending user approval.
*   **Backend Details**:
    1.  Construct a graph using `LangGraph`.
    2.  Add a standard software breakpoint via the `interrupt_before` argument on the specific node (e.g., `["send_email_node"]`).
    3.  Use standard dictionary/in-memory savers (or SQLite checkpointing) to freeze the graph state. 
    4.  Django View 1: Initiates graph, hits the interrupt, and returns the pending action details.
    5.  Django View 2: Receives the user's `POST` request accepting the action, and resumes the graph using `graph.invoke(Command(resume=True), config)`.
*   **Frontend (HTMX)**:
    1.  The UI displays a large "Confirm Action: Send Email To X?" `<form>`. Clicking Yes fires an HTMX POST to resume the graph.

## 2. Module `01_05_agent` (Master Orchestrator)
**Objective**: Establish a unified "API/Agent Server" combining prior lesson endpoints.
*   **Backend Details**:
    1.  Create a Django supervisor service.
    2.  It takes a simple text input and categorizes the intent via an OpenRouter call to delegate exactly which subsystem should be triggered (Media Generation, Tool Interaction, MCP Translation).
    3.  It then returns the unified response.
*   **Frontend (HTMX)**:
    1.  The primary chat thread for "Damian's Operation Center". All inputs here are pushed straight to the `01_05_agent` Django endpoint.
