# Lesson 04 — Kaizen: Collaboration Retrospective

> *Kaizen (改善) — continuous improvement through honest reflection.*

---

## What Was the Task

Build a Django module for lesson 04 in which an LLM agent reads a fictional railway transport system documentation (some files text, one file an image), fills an exact form template, and submits it to a verification hub — retrying on validation errors. The hub returns a flag on success.

---

## What Worked Well

- **Plan-first, code-second flow** worked smoothly. Asking for a detailed plan before any code was written saved rework — the URL pattern, vision model choice, and retry strategy were all resolved upfront.
- **The three clarifying questions** surfaced the most critical unknowns (URL pattern, image model, retry behaviour) in one round. This was the most efficient single exchange of the session.
- **The agent succeeded on the real task** in 3 submission attempts without any manual intervention — the self-correction loop (read hub error → fix → resubmit) worked exactly as designed.
- **The log.json** proved its value immediately: it captured the exact sequence of errors and fixes that led to `{FLG:WISDOM}`, making the agent's reasoning fully observable after the run.

---

## What Went Wrong / Friction Points

### 1. Template filter `|tojson` used instead of `|escapejs`

**What happened**: The `sendit_result.html` partial used `{{ text|tojson }}` in two `onclick` clipboard buttons. This is a Jinja2/Flask convention — it does not exist in Django. Django would raise `Invalid filter: 'tojson'` at render time. The template was delivered with this bug built in.

**Root cause**: I (the coding agent) applied a filter from a different framework without cross-checking it against Django's built-in filter list.

**How it was caught**: You noticed problems in the template and asked for a review, at which point the two occurrences were found and fixed to `|escapejs` with surrounding single quotes.

**How to avoid it in future**:
- When asking for Django templates, explicitly state: *"use only Django built-in template tags and filters"* or *"double-check all filters are in the Django template filter reference"*
- After template delivery, a fast sanity check is: `python manage.py check` or load the template in a Python shell — Django will raise on invalid filters immediately

---

### 2. Import order check run against the wrong Python interpreter

**What happened**: The first `python -c "from lesson_04.services..."` smoke-test failed with `ModuleNotFoundError: No module named 'langchain'`. This was alarming until we discovered the project uses a `.venv` virtual environment. When re-run with `.venv\Scripts\python.exe`, everything imported cleanly.

**Root cause**: The terminal's active Python (`python`) was the system-wide interpreter, not the project venv. The `langchain-openai` and `langchain` packages were only installed in the venv.

**How to avoid it in future**:
- At the start of every coding session, note the venv path in your request: *"The project uses `.venv` — always run Python commands with `.venv\Scripts\python.exe`"*
- Or activate the venv first: `.venv\Scripts\activate` — then `python` resolves correctly for the rest of the session
- This is worth keeping as a standing instruction in the task description whenever asking a coding agent to run validation commands

---

### 3. Task description was loose about retrieval mechanics

**What happened**: The task said *"documentation files are referenced in index.md"* but did not say how they were referenced (the `[include file="..."]` directive) or where they were hosted. This required the clarifying question about URL patterns, plus a regex solution to parse the directives.

**Why it matters**: If the URL pattern had been more obscure (e.g. requiring authentication, a different path structure, or session cookies) the agent would have had to guess or fail. We got lucky that the pattern `https://hub.ag3nts.org/dane/doc/{filename}` was simple and you knew it.

**How to handle this in future**:
- When describing a task that involves fetching external resources, include: the base URL or URL pattern, whether authentication is needed, what file types to expect, and what to do when a file is inaccessible
- A good template for this kind of task: *"External docs are at `{base_url}/{filename}`. Some may be images requiring vision. If a file returns 4xx, treat it as empty and continue."*

---

### 4. No explicit timeout / loading feedback in the original frontend spec

**What happened**: The agent task can take 60–90 seconds (fetching 10 docs + vision model call + 3 LLM round-trips). The `hx-indicator` spinner was added proactively but was not in the original requirements.

**Improvement**: When specifying frontend requirements for long-running agent operations, always include: expected duration, whether a progress indicator is needed, and whether you want streaming updates or a single final response.

---

## General Patterns for Working with a Coding Agent

### Ask clarifying questions *before* you approve coding — not after

The three-question round we did here was the right moment. Changes to a service's architecture (e.g. "use polling instead of single POST") are cheap before coding starts and expensive after.

What to clarify upfront for agent tasks:
- External API: URL, auth, request/response format
- Model selection: which LLM, vision-capable or not, temperature
- Error handling: retry count, how errors surface (auto-fix vs. manual)
- Output format: what fields does the result dict contain
- Logging: where, what level of detail

### Describe the *contract* of each component, not just its name

Instead of: *"Add a service that fills the form"*

Write: *"Add `services/sendit_service.py` with a `run_sendit_agent() -> dict` function. The dict must contain: `flag` (str|None), `declaration` (str|None), `steps` (list), `submissions` (list with attempt/status_code/response fields), `action_log` (list), `success` (bool). The view receives this dict and passes it to the template as `data`."*

This prevents mismatch between what the service returns and what the template tries to render.

### Specify the framework version for template/filter questions

Always state: *"Django 6, standard template engine (not Jinja2)"*. This eliminates a whole class of wrong filter names (`tojson`, `safe_json`, etc.) that exist in other frameworks.

### Use the log as a shared language during debugging

Because `log.json` captures every agent action with timestamps, error messages, and response bodies, it becomes the single source of truth when something goes wrong. When reporting an issue to the coding agent, paste the relevant log entries rather than describing the symptom — this gives precise context with no ambiguity.

Example message format that works well:
> *"Attempt 2 failed with the below log entry. What did the agent get wrong and how should the service be adjusted?"*
> ```json
> {
>   "action": "submit_declaration",
>   "attempt": 2,
>   "status_code": 400,
>   "response_json": {"code": -760, "message": "The shipment will not fit on the train."}
> }
> ```

### Separate "python-side" and "LLM-side" responsibilities clearly

A pattern that worked well in this task: **all HTTP fetching and file parsing is done in Python before the agent starts**. The LLM only does reasoning and template filling. This makes the agent easier to test (you can feed it mock docs), easier to observe (fetched content is logged), and cheaper to run (no extra tool-calling round-trips for HTTP fetches).

Contrast with: giving the LLM a `fetch_document(url)` tool and letting it decide what to fetch. That approach is more flexible but harder to control and observe.

---

## Checklist for Future Agent Tasks in This Project

- [ ] State the `.venv` path or activate the venv before any shell commands
- [ ] Specify all external URLs, auth requirements, and file types upfront
- [ ] Specify the result dict contract (fields, types) before service is written
- [ ] Note *"Django template engine, not Jinja2"* when templates are involved
- [ ] Specify whether long-running operations need streaming or loading feedback
- [ ] Agree on retry behaviour and max attempts before implementation
- [ ] Confirm log format and location upfront so the template can render it
