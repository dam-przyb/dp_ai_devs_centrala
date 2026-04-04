# Lesson 05 — Kaizen: What We Struggled With and How to Avoid It

## Purpose of this file

A retrospective on every friction point encountered during this lesson — what
broke, why it broke, and how to describe the problem more precisely next time
so the collaboration with a coding agent is smoother.

---

## 1. The Rate-Limit Bug — The Costliest Mistake

### What happened

The agent ran successfully, called `reconfigure`, received a 200 response — and
then immediately froze.  The log showed:

```
"message": "⏳ Rate limit — waiting 1775333535.0s  (remaining=0, reset_after=1775333535)"
```

1 775 333 535 seconds ≈ **56 years**.  The agent would never have completed.

### Root cause

The code assumed `x-ratelimit-reset-after` always represents *seconds to wait*.
In reality the API returns it as an **absolute Unix epoch timestamp** (seconds
since 1970).  The value `1 775 333 535` means "quota resets at Unix time
1 775 333 535" (April 2027), not "wait 56 years".

The same response also contained `retry-after: 24` — the correct 24-second wait
— which was ignored in favour of the larger (wrong) value.

### Lesson

**Never trust non-standard rate-limit headers without inspection.**
The only HTTP standard for "seconds to wait" is `Retry-After`.  Any custom header
like `x-ratelimit-reset-after` can be a Unix timestamp, an ISO date string, or a
duration in seconds — the semantics are not standardised.

### How to describe this to a coding agent next time

> "The API returns a rate-limit header `x-ratelimit-reset-after` whose value is
> an **absolute Unix timestamp** (seconds since epoch), NOT a duration.
> Before sleeping, detect whether the value is a timestamp (value > 3600) and
> compute `delta = value - time.time()`.  Always prefer `Retry-After` (standard
> HTTP — always in seconds) when it is present.  Apply a hard cap of `MAX_WAIT_S`
> seconds after all calculations so no sleep can exceed a safe maximum."

### The fix applied

```python
# Priority 1: Retry-After — standard, always seconds
if retry_after:
    wait_s = float(retry_after)

# Priority 2: x-ratelimit-reset-after — detect Unix timestamp
if not wait_s and reset_after:
    val = float(reset_after)
    wait_s = (val - time.time()) if val > 3_600 else val

# Hard cap — never sleep more than 120 s regardless of header value
wait_s = min(wait_s, MAX_RATE_LIMIT_WAIT_S)
```

---

## 2. Unknown API Contract at Task Start

### What happened

The task description gave zero documentation about what actions exist, what
parameters they require, or in what order they must be called.  The initial
planning discussion had to design around complete uncertainty.

### Why this was fine here but can trap you

The self-documenting `help` action handled it gracefully.  But the initial
architecture assumed a fixed sequence (e.g. "call reconfigure then setstatus
then save").  That assumption would have been wrong if the API had required
a different order.

### Lesson

When an API is undocumented, **the agent's first action must always be to read
the docs**.  The system prompt and tool docstring must both say this explicitly —
not as a suggestion, but as a rule:

```
STRICT RULE 1: Begin by calling action="help". Never skip this step.
Use ONLY the exact action names and parameter names that help returns.
```

### How to describe to a coding agent

> "The API is self-documenting.  The agent MUST call `action='help'` as its
> very first action and read the returned documentation carefully.  All subsequent
> action names and parameter names must come verbatim from that documentation.
> The agent must never invent or guess any parameter name."

---

## 3. The Model Name Mismatch

### What happened

The model was initially specified as `google/gemini-3.1-pro-preview` but the
correct OpenRouter identifier is `google/gemini-2.5-pro-preview`.  This would
have caused a silent API error on the first LLM call.

### Lesson

Model identifiers on OpenRouter are **not predictable** from the model's
marketing name.  Always verify the exact string from
[openrouter.ai/models](https://openrouter.ai/models) before hardcoding.

### How to describe to a coding agent

> "The model string must be the exact OpenRouter API identifier as it appears
> at openrouter.ai/models.  Do not infer or guess the identifier from the
> model's display name."

---

## 4. Blocking HTTP vs Background Thread — The Timeout Risk

### What happened

The original plan proposed a blocking HTMX + spinner pattern (used in earlier
lessons like `findhim`).  Because this task can take **many minutes** due to
rate-limit sleeps and 503 retries, a blocking Django view would hit the default
gunicorn/development-server request timeout and drop the connection before the
agent finished.

### What we chose instead

A **background daemon thread** that starts immediately and returns a `task_id`.
Live progress is delivered via **Server-Sent Events (SSE)** — a separate HTTP
connection that stays open as long as the agent runs.

### When to choose blocking vs background + SSE

| Pattern | Use when |
|---|---|
| Blocking HTMX | Task completes in < 30 s with high confidence |
| Background thread + SSE | Task can take minutes; live feedback is valuable |
| Celery task + polling | Multi-process deployment; survives server restart |

### How to describe to a coding agent

> "The agent task can take several minutes due to rate-limit waits.  Use a
> **background daemon thread** that returns a `task_id` immediately.  Expose a
> separate SSE endpoint (`StreamingHttpResponse`, `content_type='text/event-stream'`)
> that polls the in-memory task store and pushes JSON events to the browser.
> The Django view POST handler must return **without blocking** — it only starts
> the thread and returns the live-log partial."

---

## 5. Passing Context into a `@tool` without LLM Seeing It

### What happened

The `@tool` function needed access to `task_id` to append log entries correctly.
But `task_id` is an internal implementation detail — if it appeared as a tool
parameter, the LLM would attempt to fill it in as an argument, likely with
a hallucinated or wrong value.

### How it was solved

`threading.local()` was used to bind `task_id` to the current thread before
the LLM is invoked.  The tool reads it from thread-local storage:

```python
_thread_local = threading.local()

# In the worker node, before calling the LLM:
_thread_local.task_id = state["task_id"]

# Inside the @tool:
task_id = getattr(_thread_local, "task_id", "unknown")
```

### Lesson

Any context that must be available inside a `@tool` but must NOT be visible
to the LLM should be passed via **thread-local storage** (for daemon threads)
or a **closure** (for inline tool definitions).

### How to describe to a coding agent

> "The tool needs access to `task_id` for logging but this must NOT appear as
> a tool parameter (the LLM would try to fill it in).  Bind it using
> `threading.local()` in the worker node before invoking the LLM, and read
> it inside the tool with `getattr(_thread_local, 'task_id', 'unknown')`."

---

## 6. Incremental Planning vs Upfront Contract

### What happened

During the planning phase, the agent architecture (Supervisor + ReAct) was
agreed upon first, then details emerged (live log, SSE, the need for background
threading) as follow-up questions.  Each clarification required re-reading the
plan and mentally merging the updates.

### What would have been smoother

Providing the following upfront in the initial request would have allowed the
agent to produce a more complete plan in one pass:

1. **Non-functional requirements**: "This can take minutes — the UI must not block"
2. **Infrastructure constraints**: "Django dev server with default timeout"
3. **Observability requirement**: "I need to see every API call and LLM decision live"
4. **Known API quirks**: "503 is simulated overload, not a real error; rate limit headers may be non-standard"
5. **Output requirements**: "Save log.json and answer.json to the task context directory"

### Template for describing agentic tasks to a coding agent

```
Task: [one sentence describing the goal]

API/Endpoint: [URL, method, auth]
Known quirks: [list any non-standard behaviour — 503 patterns, header formats, etc.]

Agent requirements:
- Start with: [first action to take]
- Success condition: [what does success look like in the response?]
- Error handling: [retry strategy, caps, fallbacks]

Infrastructure:
- Long-running? [yes/no — affects blocking vs background thread choice]
- Live feedback needed? [yes/no — affects SSE vs polling vs blocking]
- Persist output to: [path]

LLM:
- Model: [exact OpenRouter identifier]
- Tool parameter design: [note any context that must NOT be LLM-visible]
```

---

## Summary Table

| Issue | Root cause | Prevention |
|---|---|---|
| 56-year rate-limit sleep | Confused Unix timestamp with duration | Always prefer `Retry-After`; detect timestamps with `val > 3600` heuristic; apply hard cap |
| Model name wrong | Guessed OpenRouter identifier | Always verify at openrouter.ai/models |
| Would have timed out | Long task in blocking view | Use background thread + SSE for tasks > ~30 s |
| LLM filling in internal tool args | `task_id` exposed as tool parameter | Use `threading.local()` for hidden per-thread context |
| Multi-pass planning | Non-functional requirements stated late | Provide full NFR list (timing, observability, persistence) in the first message |
