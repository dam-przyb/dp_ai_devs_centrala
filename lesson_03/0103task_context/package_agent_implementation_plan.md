# Implementation Plan: Package Agent Service (Lesson 03 Quest)

## 1. Goal

Build a new Lesson 03 "Quest" module that exposes and controls a public HTTP endpoint for task `proxy`.
The endpoint acts as a conversation-aware package assistant with tool access to:

- check package status,
- redirect package,
- keep independent per-session memory,
- auto-submit verify payload,
- display success flag in UI in format `{FLG:...}`.

This plan intentionally covers design only (no implementation yet).

---

## 2. Requirement Fit Check

Your instruction set is sufficient to start implementation.

### Covered clearly

- Use LangGraph ReAct agent.
- Keep agent prompt in an external `.txt` file.
- Define tools in the same `.py` service file (same style as `findhim_agent_service.py`).
- Use Azyl credentials from `.env` / task context.
- Provide visual layer in Lesson 03 "Quest" section.
- Support activate/deactivate HTTP server and log events.
- Auto-post verification and show flag.

### Assumptions (to confirm before coding)

- "Activate/deactivate HTTP server" means controlling an external tunnel process (Azyl SSH reverse tunnel), not replacing Django's own server process.
- Public endpoint for Hub will be implemented as a Django route (inside this app), while Azyl tunnel exposes local Django host publicly.
- Server control in UI will manage tunnel lifecycle + endpoint readiness checks.

---

## 3. Current Repo Baseline (Analysis)

### Existing patterns to reuse

- Thin views + service orchestration pattern exists in Lesson 02 and Lesson 03.
- HTMX partial rendering and spinner UX pattern already exists and is consistent.
- "Quest" UX pattern already proven in Lesson 01 and Lesson 02.
- LangGraph ReAct baseline already exists in MCP translator service.
- Task API key wiring already exists (`settings.AIDEVS_API_KEY`).

### Gaps for this task

- Lesson 03 currently has no `Quest` route/module.
- No service yet for package API tools (`/api/packages`) and proxy endpoint behavior.
- No process manager for Azyl tunnel lifecycle.
- No runtime log persistence model for quest operations.

---

## 4. Target Architecture

### 4.1 Runtime components

1. **Quest Control UI (Django + HTMX)**
   - Start tunnel
   - Stop tunnel
   - Show endpoint URL/status
   - Show event log and latest flag

2. **Proxy Endpoint (publicly reachable)**
   - Receives JSON `{sessionID, msg}`
   - Returns JSON `{msg}`
   - Uses per-session memory
   - Executes LangGraph ReAct + tool calls

3. **Package Agent Service**
   - Tool definitions in one file
   - External prompt loaded from `.txt`
   - Tool loop trace + API logs
   - Mission logic for redirect override when reactor package detected

4. **Azyl Tunnel Manager**
   - Starts SSH reverse tunnel with Azyl credentials
   - Verifies tunnel health
   - Stops process cleanly

5. **Auto-Verify Worker Function (sync call on completion trigger)**
   - Posts to `/verify` with `task=proxy`
   - Saves full response
   - Extracts and surfaces flag

### 4.2 Data flow

1. Operator sends message to public proxy URL.
2. Django proxy endpoint resolves session state.
3. Service runs ReAct agent with tools.
4. Tools call package API `/api/packages`.
5. Final response returned to operator as `{msg: ...}`.
6. UI polling reads live logs/status.
7. On success criteria, service submits `/verify` and stores flag.

---

## 5. Proposed Files (Planned)

### New service + prompt

- `lesson_03/services/package_agent_service.py`
  - Main orchestration service.
  - Tool definitions in same file.
  - Session memory store abstraction.
  - Package API client helper.
  - Verify submission helper.
  - Structured logging helper.

- `lesson_03/0103task_context/package_agent_system_prompt.txt`
  - External system prompt for ReAct agent.
  - Includes behavior guardrails from task and hints.

### New process/tunnel helper

- `lesson_03/services/azyl_tunnel_service.py`
  - Start/stop/check tunnel process.
  - Persist runtime metadata (pid, started_at, public_url, health state).

### New views

- `lesson_03/views/quest.py`
  - `quest_view` (GET workspace)
  - `quest_start_tunnel_api` (POST)
  - `quest_stop_tunnel_api` (POST)
  - `quest_status_api` (GET, HTMX polling)
  - `proxy_endpoint_api` (POST JSON for Hub/operator)

### New templates

- `lesson_03/templates/lesson_03/quest.html`
- `lesson_03/templates/lesson_03/partials/quest_status.html`
- `lesson_03/templates/lesson_03/partials/quest_log.html`

### URL and nav updates

- `lesson_03/urls.py`
  - Add quest workspace routes and API routes.
  - Add public proxy endpoint route.

- `core/nav_registry.py`
  - Add Lesson 03 module entry labeled `Quest`.

### Optional persistence model (recommended)

- `lesson_03/models.py` (if we choose DB-backed observability)
  - `QuestRuntimeState`
  - `QuestEventLog`
  - `QuestSessionSnapshot` (optional)

---

## 6. Detailed Functional Plan

## Phase A: Agent Core Service

### A1. Prompt externalization

- Load prompt from `package_agent_system_prompt.txt` at runtime.
- Validate prompt file exists on startup call.
- Add fallback error if missing.

### A2. ReAct graph

- Build with `langgraph.prebuilt.create_react_agent`.
- LLM config from settings/OpenRouter.
- Deterministic config (`temperature=0`) for repeatability.

### A3. Tools in same file

- `check_package(packageid)`
- `redirect_package(packageid, destination, code)`
- Both call `https://hub.ag3nts.org/api/packages` with AIDEVS key.
- Log every request/response/error entry.

### A4. Session memory

- In-memory dict for runtime speed plus optional JSON snapshot on disk.
- Keyed by `sessionID`.
- Memory payload compatible with LangChain/LangGraph message format.

### A5. Mission behavior

- Prompt + safety checks enforce hidden redirect destination override to `PWR6132PL` in reactor-package scenario.
- Preserve natural operator-facing language.

### A6. Verify submission

- Build payload:
  - `apikey`
  - `task: proxy`
  - `answer.url`
  - `answer.sessionID`
- Persist verify result and extract flag pattern `{FLG:...}`.

## Phase B: Azyl tunnel lifecycle

### B1. Start tunnel

- Build SSH command using Azyl user/host/port and assigned remote port mapping.
- Run as subprocess.
- Capture stdout/stderr to event log.
- Health-check endpoint URL after startup.

### B2. Stop tunnel

- Graceful terminate; hard kill fallback.
- Clear runtime state and log final status.

### B3. Reliability

- Guard against duplicate start calls.
- Detect dead subprocess and show stale-state warning.
- Validate local Django target host/port before start.

## Phase C: Django Quest UI

### C1. Quest workspace

- Control panel:
  - Start server/tunnel button
  - Stop server/tunnel button
  - Status badge (inactive/starting/active/error)
  - Public URL display with copy action

### C2. Logs panel

- Chronological event feed (newest first).
- Filters: lifecycle, tool, verify, error.
- Expandable sections for request/response payloads.

### C3. Completion panel

- Show verify result and highlighted flag once present.
- Flag regex extraction and explicit success styling.

### C4. Polling

- HTMX polling endpoint every 3–5 seconds for status/log refresh.

## Phase D: Proxy endpoint behavior

### D1. Contract

- Accept POST JSON only.
- Validate `sessionID` and `msg`.
- Return JSON `{"msg": "..."}`.

### D2. Error strategy

- Tool/API failures become natural-language operator-safe messages.
- Internal details logged to Quest event log.
- Always return valid JSON envelope.

### D3. Multi-session support

- Full isolation per `sessionID`.
- No cross-session context bleed.

---

## 7. Security and Ops Plan

- Keep Azyl password only in env; never render in templates.
- Scrub secrets from logs (`apikey`, password, tokens).
- Add CSRF-safe handling for UI POST routes.
- Keep public proxy endpoint no-auth by design (task requirement), but strict JSON validation and method restriction.
- Add host guidance for local + Azyl testing in docs.

---

## 8. Testing Plan

1. **Unit tests (service level)**
   - Prompt loading
   - Tool payload correctness
   - Session isolation logic
   - Flag extraction parser

2. **Integration tests (Django endpoints)**
   - Proxy endpoint contract success/error
   - Quest start/stop/status routes
   - Verify submission path

3. **Manual flow test**
   - Start tunnel from UI
   - Confirm public URL reachable
   - Simulate operator conversation with two sessions
   - Confirm logs populate
   - Confirm auto-verify and flag rendering

---

## 9. Acceptance Criteria

- Lesson 03 sidebar includes `Quest` and loads workspace.
- User can activate/deactivate tunnel from UI.
- UI shows live status, URL, and event logs.
- Public endpoint responds in required JSON contract.
- Per-session memory works for concurrent sessions.
- Agent uses LangGraph ReAct and external prompt `.txt`.
- Tools are defined in one service `.py` file.
- Verify call is automatic and success flag is displayed as `{FLG:...}`.

---

## 10. Risks and Mitigations

- **Tunnel startup fragility (Windows SSH differences)**
  - Mitigation: isolate command builder, expose raw stderr in logs, provide fallback with `127.0.0.1` mapping.

- **Long-lived subprocess in Django dev server**
  - Mitigation: track pid/state centrally; add stale-process detection and kill path.

- **Agent loop hangs or tool-call loops**
  - Mitigation: enforce max iterations and timeout budget.

- **Hub validation timing/race conditions**
  - Mitigation: explicit readiness checks before auto-verify submission.

---

## 11. Implementation Order (Recommended)

1. Add prompt file and package agent service skeleton.
2. Implement tools + API client + logs.
3. Implement proxy endpoint contract.
4. Implement Azyl tunnel service (start/stop/status).
5. Implement Quest views/templates/partials.
6. Wire URLs and sidebar nav.
7. Add verify automation + flag extraction UI.
8. Run manual end-to-end check with Hub.

---

## 12. Final Note

This plan is actionable and consistent with your current repository architecture (thin Django views, service-centric logic, HTMX partial UI, LangGraph usage).
After your approval, implementation can proceed in incremental commits by phase.