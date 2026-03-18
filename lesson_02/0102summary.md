# Session Summary — S01E02 "findhim" Module

## What was built

A complete Django module (`lesson_02`) that solves the **findhim** task:
identify which suspect from S01E01 was seen near a Polish nuclear power plant,
retrieve their access level, and submit the report to `https://hub.ag3nts.org/verify`.

---

## Files Created / Modified

### New files

| Path | Purpose |
|---|---|
| `lesson_02/services/findhim_agent_service.py` | Hybrid investigation service (Phase 1 Python + Phase 2 LLM) |
| `lesson_02/views/findhim.py` | Thin Django view — GET workspace, POST API with model selector |
| `lesson_02/templates/lesson_02/findhim.html` | Workspace partial — model dropdown + Run Agent button |
| `lesson_02/templates/lesson_02/partials/findhim_result.html` | HTMX result partial — search summary banner, flag banner, step tracker, tool trace |
| `lesson_02/run_findhim_agent.py` | Standalone CLI runner (runs agent outside Django) |
| `lesson_02/0102task_context/implementation_plan_quest.md` | Full implementation plan |
| `lesson_02/0102task_context/answer.json` | Answer payload (template; overwritten by agent on each run) |

### Modified files

| Path | Change |
|---|---|
| `lesson_02/urls.py` | Added `findhim/` and `findhim/api/` URL patterns |
| `core/nav_registry.py` | Added `"Quest"` module (`l02_findhim`) to `02 — Tool Use` nav group |
| `operation_center/settings.py` | Added `AIDEVS_API_KEY` and `FINDHIM_MODEL` settings |
| `run_findhim_agent.py` (root) | Replaced with a redirect stub pointing to `lesson_02/run_findhim_agent.py` |

---

## Architecture — findhim_agent_service.py

The service uses a **hybrid** approach (not pure LLM) due to observed LLM
reasoning failures when tracking a global minimum across 35+ distance calls:

### Phase 1 — Pure Python (deterministic)
1. Load `suspect_list.json` (5 suspects from S01E01) and `powerplants.json`
2. POST `/api/location` for each suspect → get GPS sighting lists
3. For every sighting × every plant → compute Haversine distance in Python
4. Identify `(suspect, plant_code)` with minimum distance
5. Look up `birth_year` from suspect list

### Phase 2 — LLM Agent (2 tools only)
- The LLM receives the pre-computed winner as context
- **Tool 1**: `get_access_level(name, surname, birth_year)` → POST `/api/accesslevel`
- **Tool 2**: `submit_answer(name, surname, access_level, power_plant)` → POST `/verify` + saves `answer.json`

Max agent iterations: **10**.

### Key design notes
- **`answer.json` is written BEFORE the POST** to `/verify`, so it always reflects what was actually sent
- **Error responses from `/verify` include the full body** (status code + server message) so the LLM can read the rejection reason
- **Power plant GPS coordinates are hardcoded** because `findhim_locations.json` returns only `{code, is_active, power}` — no coordinates. City-centre approximations (±1 km) are used.

---

## Power Plant Coordinates (hardcoded in service)

| City | Lat | Lon | Code |
|---|---|---|---|
| Grudziądz | 53.4836 | 18.7536 | PWR7264PL |
| Zabrze | 50.3249 | 18.7857 | PWR3847PL |
| Piotrków Trybunalski | 51.4060 | 19.7041 | PWR5921PL |
| Tczew | 54.0952 | 18.7774 | PWR1593PL |
| Radom | 51.4027 | 21.1471 | PWR8406PL |
| Chełmno | 53.3511 | 18.4238 | PWR2758PL |
| Żarnowiec | 54.7039 | 18.1408 | PWR6132PL |

---

## Settings Added (`operation_center/settings.py`)

```python
# AI Devs API Key — set via AIDEVSKEY env var
AIDEVS_API_KEY = os.getenv("AIDEVSKEY", "")

# LLM model for findhim agent — override via FINDHIM_MODEL env var
FINDHIM_MODEL = os.getenv("FINDHIM_MODEL", "openai/gpt-5.4-mini")
```

---

## UI Integration

- The module appears in the sidebar as **02 — Tool Use → Quest** (registered in `core/nav_registry.py`)
- Pattern mirrors `lesson_01/quest`: single trigger button, SVG spinner, result banner with flag, numbered step tracker
- UI extras: **model dropdown** (GPT-4o / GPT-4o-mini / GPT-4.1) sent as `POST` field `model`
- Result partial shows: Phase 1 search summary (blue box) + flag banner (violet gradient) + 4-step tracker + collapsible tool call trace

---

## Bugs Fixed During Session

| Bug | Root cause | Fix |
|---|---|---|
| Nav "Quest" click did nothing | `import requests` in service — `requests` not installed; Django URL load failed silently | Replaced all `requests` calls with `httpx` |
| Template syntax error on load | `{{FLG:...}}` treated as Django template variable tag | Used `{% templatetag openvariable %}` |
| 400 errors on submit + wrong suspect | LLM failed to track global minimum across many distance calls; agent also retried with wrong person | Moved Phase 1 (all location fetching + distance comparison) to pure Python |
| `answer.json` showed different person than submitted | Save happened inside try/except after POST in old code | Save explicitly moved BEFORE `httpx.post()` |
| 400 error body swallowed | `raise_for_status()` converted error to exception, losing body | Removed `raise_for_status()`; return full body + status on errors |

---

## Current Status

The agent runs but was still returning 400 at time of session end. Oskar Sieradzki (PWR7264PL) was identified as the closest suspect by the agent in pure-LLM mode. After switching to hybrid mode the identification is now deterministic.

**Next session should**: run the agent via UI or `python lesson_02/run_findhim_agent.py`, verify the Phase 1 search summary looks correct (right suspect + plant), and check whether the 400 persists. If it does, the power plant code or the sighting coordinates being used for the winner may need review — consider logging the raw `/api/location` response to see the exact coordinates returned.

---

## Running the Agent

```bash
# Via CLI (from project root):
python lesson_02/run_findhim_agent.py

# Via UI:
python manage.py runserver
# Navigate: 02 — Tool Use → Quest → Run Agent
```
