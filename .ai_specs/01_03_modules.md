# Coding Agent Instructions: Lesson 03 Modules (Model Context Protocol)

**Goal Requirement**: Implement MCP Core, Native, Translator, and Upload flows in Django.

## 1. Module `01_03_mcp_core`
**Objective**: Connect the Django application as an MCP Client over stdio to a known external MCP server script.
*   **Backend Details**:
    1.  Use the official `mcp` Python SDK (`mcp.client.stdio.StdioServerParameters`).
    2.  Provide a server script path (e.g., a node `npx` command or a python script) in Django settings.
    3.  Create a Django service to establish a persistent session (or open/close per request), fetch tools via `session.list_tools()`, and call tools. 

## 2. Module `01_03_mcp_native`
**Objective**: Combine Native Python tools and MCP tools in a single Agent executor.
*   **Backend Details**:
    1.  Write a wrapper `get_mcp_tools(session) -> list[BaseTool]` that maps the JSON schema returned by the MCP `list_tools()` into standard LangChain tools.
    2.  Combine this list with local decorators (e.g., `local_calculator()`).
    3.  Pass the unified list to an OpenRouter standard Agent Executor. 

## 3. Module `01_03_mcp_translator`
**Objective**: Utilize an MCP "files" server to translate a file.
*   **Backend Details**:
    1.  Specify a file on the MCP server. Use the `read_file` tool provided by the MCP server.
    2.  Pass the content into an LLM Prompt designed for precise translation.
    3.  If writing back is supported by the server, use `write_file`. Otherwise, return a `HttpResponse` offering the translated string as a download to the browser.
*   **Frontend (HTMX)**:
    1.  Render a view asking for a source filepath and target language.

## 4. Module `01_03_upload_mcp`
**Objective**: Accept a file via the browser and send it into an MCP workflow.
*   **Backend Details**:
    1.  Create a standard Django view that handles `<input type="file" name="document">`.
    2.  Store the file temporarily on the server (`/tmp` or Django's `MEDIA_ROOT`).
    3.  Execute an MCP tool providing the local path of the temporarily stored file to the MCP ecosystem processing agent.
