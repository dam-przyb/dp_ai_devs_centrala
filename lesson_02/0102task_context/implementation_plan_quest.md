# Implementation Plan — Task: findhim (S01E02)

## Problem Statement

Identify which suspect from the previous task (S01E01) was seen near a nuclear
power plant in Poland, retrieve their access level, and submit the full report
to `https://hub.ag3nts.org/verify`.

---

## Inputs Available

| File | Contents |
|---|---|
| `suspect_list.json` | 5 suspects: name, surname, born, city, tags |
| `powerplants.json` | 7 Polish power plant sites: name → `{is_active, power, code}` |

Missing from saved powerplants data: **GPS coordinates** per site.  
These are resolved at runtime by a hard-coded city → (lat, lon) map of well-known
Polish cities (accurate to ±1 km, sufficient for this task).

---

## Algorithm

```
For each suspect in suspect_list.json:
  1. POST /api/location {apikey, name, surname}
     → receive list of (lat, lon) sightings

For each suspect sighting:
  2. Calculate Haversine distance to every power plant (lat, lon)
  3. Track (suspect, min_distance, power_plant_code)

Identify suspect with minimum overall distance to any power plant.

4. POST /api/accesslevel {apikey, name, surname, birthYear}
   → receive accessLevel integer

5. Build answer payload:
   {name, surname, accessLevel, powerPlant}

6. POST /verify {apikey, task: "findhim", answer: {...}}
   → receive {flag} if correct
```

---

## Module Architecture

### New files (implemented)

```
lesson_02/
├── services/
│   └── findhim_agent_service.py   ← LangChain agent with Function Calling
├── views/
│   └── findhim.py                 ← Thin Django view (GET workspace + POST API)
└── templates/lesson_02/
    ├── findhim.html               ← Workspace partial (matches lesson_01 quest style)
    └── partials/
        └── findhim_result.html    ← HTMX result partial (flag banner + step tracker + tool trace)
```

### Modified files (implemented)

```
lesson_02/urls.py          ← added findhim/ and findhim/api/ URL patterns
core/nav_registry.py       ← added "Quest" module to 02 — Tool Use section
```

### Standalone runner

```
run_findhim_agent.py       ← Execute agent outside Django (for quick testing)
```

---

## UI Integration (lesson_01 quest pattern)

The module follows the same structural pattern as `lesson_01/quest`:

| Aspect | lesson_01 quest | lesson_02 findhim |
|---|---|---|
| Nav label | "Quest" | "Quest" |
| Trigger | Single "Execute Quest" button | Single "Run Agent" button |
| Spinner | SVG animate-spin + HTMX indicator | Same pattern, violet colour |
| Success banner | Green gradient + flag + copy button | Violet gradient + output + copy button |
| Step tracker | Numbered green circles | Numbered green circles (4 steps) |
| Extra detail | People table | Collapsible tool call trace |
| Error display | Red panel with guidance | Red panel with guidance |

The "Quest" entry is registered in `core/nav_registry.py` under the `01_02`
lesson group so it appears in the left sidebar automatically.

---

## Agent Tools (Function Calling)

| Tool | Description |
|---|---|
| `get_suspect_locations(name, surname)` | Calls `/api/location`, returns list of `{lat, lon}` |
| `get_access_level(name, surname, birth_year)` | Calls `/api/accesslevel`, returns `int` |
| `haversine_distance(lat1, lon1, lat2, lon2)` | Pure math — returns km distance |
| `submit_answer(name, surname, access_level, power_plant)` | POST to `/verify` + saves `answer.json` |

The agent is given a **system prompt** that includes:
- The full suspect list (serialised JSON)
- The full power plant list with hardcoded city coordinates and codes
- Clear instruction: iterate suspects → check proximity → report → submit

**Max iterations**: 15 (guard against runaway loops, per hints).

---

## Power Plant City Coordinates (hardcoded)

| City | Latitude | Longitude | Code |
|---|---|---|---|
| Grudziądz | 53.4836 | 18.7536 | PWR7264PL |
| Zabrze | 50.3249 | 18.7857 | PWR3847PL |
| Piotrków Trybunalski | 51.4060 | 19.7041 | PWR5921PL |
| Tczew | 54.0952 | 18.7774 | PWR1593PL |
| Radom | 51.4027 | 21.1471 | PWR8406PL |
| Chełmno | 53.3511 | 18.4238 | PWR2758PL |
| Żarnowiec | 54.7039 | 18.1408 | PWR6132PL |

---

## Answer Output

Saved to `lesson_02/0102task_context/answer.json` by the `submit_answer` tool:

```json
{
  "apikey": "<AIDEVS_API_KEY>",
  "task": "findhim",
  "answer": {
    "name": "...",
    "surname": "...",
    "accessLevel": 0,
    "powerPlant": "PWR____PL"
  }
}
```

---

## Key Design Decisions

1. **LangChain manual tool-calling loop** — follows the existing
   `filesystem_agent_service.py` pattern; consistent with the educational codebase.
2. **API key from `settings.AIDEVS_API_KEY`** — never hardcoded in source code.
3. **Synchronous HTTP via `requests`** — consistent with the "no Celery/Redis" policy.
4. **Thin view** — all logic lives in the service; the view only handles HTTP
   marshalling and template rendering.
5. **HTMX pattern** — GET renders the workspace form; POST to `/findhim/api/` returns
   the result partial, swapped into `#findhim-result`.
6. **Nav registration** — single line in `core/nav_registry.py` makes the module
   appear in the sidebar alongside other lesson-02 tools.

---

## Running the Agent

### Via UI (preferred)
1. Start the Django server: `python manage.py runserver`
2. Open the app in the browser → navigate to **02 — Tool Use → Quest**
3. Click **Run Agent**

### Via command line
```bash
python lesson_02/run_findhim_agent.py
```
This bypasses Django's HTTP layer and runs the agent directly, printing the
full tool trace and saving `answer.json`.
