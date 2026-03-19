# 0102 Kaizen — collaboration retrospective (you + coding agent)

This note is a practical retrospective: what slowed us down, why, and how to brief coding agents better next time.

---

## 1) What went well

- You gave strong context: files, symptoms, expected behavior.
- You insisted on analysis before coding (very good for risky tasks).
- You clearly set architectural preference (agent-based approach).
- You requested observability (request/response log), which unblocked debugging.

These are high-quality habits.

---

## 2) Where we struggled

## A) Goal drift during implementation
We started with one direction (deterministic non-agent path), then switched to your preferred architecture (supervisor + tools).  
Result: extra iteration cycle.

How to avoid:
- lock architecture early with explicit “must-have / must-not-have”.

Suggested brief line:
> “Implementation must be agent-based (supervisor + tools). Deterministic-only solution is out of scope.”

---

## B) Implicit constraints surfaced late
Example: “no model selector in UI, model config only in code” came later.  
This changed already-implemented UI behavior.

How to avoid:
- put UX constraints in initial request as hard rules.

Template:
> UI constraints: no model dropdown, one action button only, show collapsible debug logs.

---

## C) Data contract mismatch not declared as top risk
Critical issue was API coordinate keys (`lat/lon` vs `latitude/longitude`).  
This caused misleading “No matching suspect”.

How to avoid:
- ask the agent to explicitly harden external data parsing from start.

Template:
> Assume external APIs may vary field names. Add normalization layer and explicit validation errors.

---

## D) Success criteria could be sharper
Initially we focused on “works” rather than strict verification checkpoints.

How to avoid:
- define acceptance criteria as testable bullets.

Example:
1. Agent makes calls to `/api/location`, `/api/accesslevel`, `/verify`.
2. `answer.json` matches submitted payload.
3. UI shows tool trace and API log.
4. On failure, error message includes endpoint + status + response body.

---

## 3) How to brief coding agent for smoother outcomes

Use this structure in future:

## 1. Objective
One sentence with exact end state.

## 2. Hard constraints
- architecture constraints,
- UI constraints,
- libraries/framework constraints.

## 3. Input contracts
- file locations,
- API schemas (and expected variants),
- known edge cases.

## 4. Expected outputs
- exact file changes,
- expected runtime behavior,
- expected logs/diagnostics.

## 5. Acceptance checks
Concrete checks agent should pass before finishing.

---

## 4) Example “high-clarity” prompt you can reuse

> Build S01E02 using supervisor + tool-calling agent only.  
> Keep model selection in `findhim_agent_service.py` (default `openai/gpt-5.4-mini`), no model UI.  
> Tools must cover location lookup, distance calculation, access-level lookup, and verify submit.  
> Normalize location keys (`lat/lon` and `latitude/longitude`).  
> Add collapsible API request/response log and tool-call trace in result partial.  
> Do analysis first, then propose plan, then wait for permission to code.

---

## 5) What to ask agent to report every time

At end of implementation, ask for:
- root cause summary (if bugfix),
- changed files list,
- before/after behavior,
- open risks,
- suggested next hardening step.

This reduces ambiguity and rework.

---

## 6) Collaboration anti-patterns to avoid

- “Fix it somehow” (too broad).
- changing architecture mid-flight without restating constraints.
- no explicit acceptance criteria.
- no requirement for debug visibility.

---

## 7) Practical improvement loop (Kaizen)

For each future task:
1. Start with “must-have / must-not-have”.
2. Include one paragraph of domain context.
3. Require analysis + plan first.
4. Require observable output/logging.
5. End with acceptance checklist.

This gives coding agents less room for wrong assumptions and speeds up convergence.

---

## 8) Final takeaway

Your strongest leverage is not more detail everywhere — it is **better structure** in requirements.  
When you provide architecture constraints + data contracts + acceptance checks up front, agent performance improves dramatically and iterations drop.
