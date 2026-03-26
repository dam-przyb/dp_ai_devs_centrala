# 0103 KAIZEN - Collaboration Retrospective (You + Coding Agent)

## 1) What Went Well

1. You gave full task context files early.
2. You pushed for architecture clarity before coding.
3. You asked for phased delivery with approval gates.
4. You reported real logs from runtime, not just symptoms.

These habits significantly improved solution quality.


## 2) Where We Struggled

## A. Validation of real traffic vs local probe traffic

Problem:
- local probe worked, but Hub traffic did not appear.
- this delayed confidence in whether endpoint was truly reachable and functional.

What caused delay:
- we initially looked at agent logic/prompt, while root issue was infrastructure/middleware (CSRF + tunnel interaction).

How to improve next time:
- ask for a strict network pipeline check early:
  1) public URL reachable,
  2) request reaches Django view,
  3) JSON parsed,
  4) message persisted,
  5) response returned.


## B. Tunnel automation assumptions

Problem:
- tunnel startup expected to run silently, but process became interactive (host trust + password).
- status polling noise hid the real blocker.

What caused delay:
- environment assumption: password auth would work with ssh fallback.
- on Windows non-interactive ssh mode, password prompts are disabled.

How to improve next time:
- explicitly ask agent to include environment preflight before implementation:
  - check tool availability (plink/ssh),
  - check auth mode (password vs key),
  - check host key trust mode.


## C. Prompt and policy mismatch to mission-critical package

Problem:
- early prompt was too generic.
- mission target PKG12345678 needed explicit mention and hard policy.

What caused delay:
- we focused on general agent behavior instead of task-specific constraints.

How to improve next time:
- include mandatory mission invariants at the start of request:
  - exact target package,
  - exact forced destination,
  - expected covert behavior.


## D. Missing explicit "findings first" checkpoints

Problem:
- several iterations mixed diagnosis and implementation.
- this made it harder to isolate root causes quickly.

How to improve next time:
- ask for this exact mode when bug appears:

  "Do a strict findings-only review first.
   Provide severity, file/line references, and likely root cause.
   Wait for approval before edits."

This creates cleaner debugging loops.


## 3) Better Prompting Patterns for Future Work

Use this template when starting a task:

1. Goal and success condition:
- what exact output means done.

2. Hard constraints:
- API contract,
- required tool/framework,
- files to use,
- what not to change.

3. Non-negotiable invariants:
- critical IDs, codes, hidden logic constraints.

4. Operational environment:
- OS,
- auth method,
- available binaries,
- expected external integrations.

5. Delivery style:
- phase-by-phase,
- summarize and wait for approval,
- findings-first during debugging.


## 4) Concrete Examples of Better Instructions

Instead of:
- "it does not work"

Use:
- "Public verify says pending, but no new rows appear in session JSON. Please audit ingress path from tunnel to proxy view and confirm whether request reaches proxy_endpoint_api. Findings only first."

Instead of:
- "tunnel failed"

Use:
- "Tunnel startup fails with permission denied (publickey,password). Check if startup command is interactive, which binary is used, and whether password auth is possible in current mode."


## 5) Collaboration Anti-Patterns to Avoid

1. Mixing probe and production verification evidence without labels.
2. Treating polling logs as proof of endpoint traffic.
3. Adjusting prompt repeatedly before validating network/middleware path.
4. Assuming installed dependencies are visible in current shell session.


## 6) Practices That Should Become Default

1. Preflight checks before coding:
- executable presence,
- env vars loaded,
- route existence,
- external host accessibility.

2. Add observability first:
- incoming request event,
- parsed payload snapshot,
- tool call trace,
- persistence trace.

3. Keep deterministic policy in code for mission-critical branches.

4. Persist state for debugging and recovery.

5. Separate diagnosis stage from implementation stage on hard bugs.


## 7) What You Did Very Well as a Human-in-the-Loop

1. You detected conceptual mismatch early and challenged assumptions.
2. You asked for educational explanation, not only code output.
3. You insisted on practical, testable behavior and logs.
4. You kept moving forward with precise runtime feedback.

This is exactly how to collaborate effectively with coding agents.


## 8) Suggested Personal Playbook for Next Tasks

1. Start with a small "definition of done" checklist.
2. Force preflight diagnostics before first implementation.
3. Request phase-based execution with approval gates.
4. During failures: ask for findings-only pass first.
5. After success: request kaizen and reusable runbook.

If you follow this loop, future agent collaboration will be faster, calmer, and more predictable.
