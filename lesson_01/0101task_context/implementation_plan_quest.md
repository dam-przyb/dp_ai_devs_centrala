# Implementation Plan: Quest Module + UI Improvements

## Context

This implementation adds a "Quest" module to lesson_01 of the AI Devs Dashboard. The Quest module automates a multi-step workflow to identify people working in the transport sector from a CSV dataset, using LLM-powered job tagging with structured output, and submits results to an external verification API to receive a completion flag.

Additionally, we'll apply cosmetic improvements to the main header by integrating the Xirod font and updating the subtitle text.

**Why this is needed:**
- Demonstrates practical LLM application: filtering data, structured output, and API integration
- Combines multiple AI Devs concepts: structured output (from lesson_01), API calls, batch processing
- Provides a complete end-to-end workflow example within the existing Django + HTMX architecture

**User Requirements:**
1. Create Quest subsection under "01 — Basics" navigation
2. Implement workflow: Download CSV → Filter → Tag Jobs → Select Transport Workers → Submit → Display Flag
3. Change header font to Xirod
4. Update subtitle text from "| AI Devs Dashboard" to "| |AI_Devs4 - Builders | Dashboard"

---

## Task Specification

**Workflow Steps:**
1. **Download** people.csv from `https://hub.ag3nts.org/data/{AIDEVSKEY}/people.csv`
2. **Filter** people by criteria:
   - Gender: Male (M)
   - Age in 2026: 20-40 years (born 1986-2006)
   - Birth city: Grudziądz
3. **Tag jobs** using LLM with structured output (available tags: IT, transport, edukacja, medycyna, praca z ludźmi, praca z pojazdami, praca fizyczna)
4. **Select** people with "transport" tag
5. **Submit** to `https://hub.ag3nts.org/verify` endpoint
6. **Display** returned flag: `{FLG:SOMETHING}`

**API Key:** AIDEVSKEY from .env file (value: 9b2b37d3-dfab-42e0-a4b2-d84454981394)

**Expected CSV Structure:** name, surname, gender, born (year), city, job (description)

**Submission Format:**
```json
{
  "apikey": "...",
  "task": "people",
  "answer": [
    {
      "name": "Jan",
      "surname": "Kowalski",
      "gender": "M",
      "born": 1987,
      "city": "Grudziądz",
      "tags": ["transport", "praca z pojazdami"]
    }
  ]
}
```

---

## Implementation Approach

### A. Quest Module (Django Pattern)

Following the established lesson_01 pattern (interaction, structured, grounding modules):

**Service Layer Architecture:**
- Create `lesson_01/services/quest_service.py` with complete workflow logic
- Use Pydantic models for structured data (Person, JobTags, PersonWithTags, QuestResult)
- Implement atomic functions: download_csv(), filter_people(), tag_jobs(), select_transport(), submit_to_verify()
- Main orchestrator: execute_quest() that calls all steps and tracks progress

**View Layer:**
- Create `lesson_01/views/quest.py` with 2 endpoints (standard pattern):
  - `quest_view()` [GET] - Renders main template
  - `quest_api()` [POST] - Executes workflow, returns HTMX partial
- Error handling with try/except wrapping service calls

**Templates:**
- `lesson_01/templates/lesson_01/quest.html` - Main UI with "Execute Quest" button
- `lesson_01/templates/lesson_01/partials/quest_result.html` - Results display with:
  - Step-by-step progress accordion
  - Summary statistics (counts at each filter step)
  - List of submitted people with their tags
  - Prominent flag display (large, green banner)

**LLM Integration:**
- Use ChatOpenAI with `with_structured_output(JobTags)` (matches structured_service.py pattern)
- System prompt with tag descriptions for accurate classification
- Batch processing consideration for performance

**URL Configuration:**
- Add routes to `lesson_01/urls.py`:
  ```python
  path("quest/", quest.quest_view, name="l01_quest"),
  path("quest/api/", quest.quest_api, name="l01_quest_api"),
  ```

**Navigation Integration:**
- Update `core/nav_registry.py` NAV list
- Add after "grounding" module (line 29):
  ```python
  {
      "slug": "quest",
      "label": "Quest",
      "url_name": "l01_quest",
  },
  ```

**Settings Configuration:**
- Add to `operation_center/settings.py` after OPENROUTER settings:
  ```python
  AIDEVS_API_KEY = os.getenv("AIDEVSKEY", "")
  ```

### B. Font Integration (Xirod)

**Approach:** Set up Django static files system and use @font-face

**Steps:**
1. Create project static folder structure:
   ```
   c:\zz_projects\dp_ai_devs_centrala\static\fonts\
   ```

2. Download Xirod font from https://www.1001fonts.com/xirod-font.html
   - Save as: `static/fonts/Xirod.ttf`
   - License: Check 1001fonts license (free for personal use)

3. Configure static files in `operation_center/settings.py`:
   ```python
   STATIC_URL = "static/"  # Already exists
   STATICFILES_DIRS = [BASE_DIR / "static"]  # Add this
   ```

4. Update `core/templates/core/base.html`:
   - Add @font-face declaration in `<style>` block (after line 9)
   - Apply font to line 20 header text
   - Update text on line 21

**Implementation:**
```html
<style>
  @font-face {
    font-family: 'Xirod';
    src: url('{% static "fonts/Xirod.ttf" %}') format('truetype');
    font-weight: normal;
    font-style: normal;
  }
  /* Existing HTMX styles... */
</style>

<!-- Line 20: Apply Xirod font -->
<span class="text-lg font-bold tracking-wide" style="font-family: 'Xirod', sans-serif;">
  Damian's Operation Center
</span>

<!-- Line 21: Update text -->
<span class="text-gray-500 text-xs">| |AI_Devs4 - Builders | Dashboard</span>
```

5. Add {% load static %} at top of base.html (after doctype, before html tag)

---

## Critical Files

### New Files (7 files)

1. **c:\zz_projects\dp_ai_devs_centrala\lesson_01\services\quest_service.py**
   - Pydantic models: Person, JobTags, PersonWithTags, QuestResult
   - Functions: download_csv(), filter_people(), tag_job(), select_transport_people(), submit_to_verify(), execute_quest()
   - ~200 lines

2. **c:\zz_projects\dp_ai_devs_centrala\lesson_01\views\quest.py**
   - quest_view(request) → render quest.html
   - quest_api(request) → execute workflow, return partial
   - ~40 lines

3. **c:\zz_projects\dp_ai_devs_centrala\lesson_01\templates\lesson_01\quest.html**
   - Header with title/description
   - Execute button with HTMX (hx-post, hx-target)
   - Result container div
   - ~50 lines

4. **c:\zz_projects\dp_ai_devs_centrala\lesson_01\templates\lesson_01\partials\quest_result.html**
   - Error display conditional
   - Step-by-step progress accordion
   - Statistics cards
   - People list with tags
   - Flag banner (green, prominent)
   - ~100 lines

5. **c:\zz_projects\dp_ai_devs_centrala\static\fonts\Xirod.ttf**
   - Downloaded font file from 1001fonts.com

### Modified Files (4 files)

6. **c:\zz_projects\dp_ai_devs_centrala\lesson_01\urls.py**
   - Add 2 quest URL patterns

7. **c:\zz_projects\dp_ai_devs_centrala\core\nav_registry.py**
   - Add quest module entry to NAV[0]["modules"] list

8. **c:\zz_projects\dp_ai_devs_centrala\operation_center\settings.py**
   - Add AIDEVS_API_KEY configuration
   - Add STATICFILES_DIRS configuration

9. **c:\zz_projects\dp_ai_devs_centrala\core\templates\core\base.html**
   - Add {% load static %} tag
   - Add @font-face declaration
   - Apply Xirod font to line 20
   - Update text on line 21

---

## Detailed Service Layer Design

### Pydantic Models

```python
class Person(BaseModel):
    """CSV row representation"""
    name: str
    surname: str
    gender: str
    born: int  # Birth year
    city: str
    job: str  # Job description text

class JobTags(BaseModel):
    """LLM structured output for single job"""
    tags: list[str] = Field(
        description="Applicable tags: IT, transport, edukacja, medycyna, praca z ludźmi, praca z pojazdami, praca fizyczna"
    )

class PersonWithTags(BaseModel):
    """Person with assigned job tags"""
    name: str
    surname: str
    gender: str
    born: int
    city: str
    tags: list[str]

class QuestResult(BaseModel):
    """Complete workflow result for UI display"""
    total_downloaded: int
    after_filter: int
    transport_workers: int
    submitted: list[PersonWithTags]
    flag: str
    error: str | None = None
```

### Service Functions

**download_csv(api_key: str) -> list[Person]:**
- HTTP GET to `https://hub.ag3nts.org/data/{api_key}/people.csv`
- Use requests library
- Parse CSV with csv.DictReader
- Convert rows to Person objects
- Raise exception on HTTP errors

**filter_people(people: list[Person]) -> list[Person]:**
- Filter by gender == "M" (case-insensitive)
- Filter by city == "Grudziądz" (case-insensitive)
- Calculate age in 2026: `2026 - person.born`
- Filter by 20 <= age <= 40
- Return filtered list

**tag_job(job_description: str) -> JobTags:**
- Get LLM using ChatOpenAI (OpenRouter settings)
- Use `llm.with_structured_output(JobTags)`
- System prompt: job classifier with tag descriptions
- Return JobTags model with list of applicable tags

**tag_all_jobs(people: list[Person]) -> list[PersonWithTags]:**
- Iterate over people
- Call tag_job() for each person's job description
- Create PersonWithTags objects
- Consider: batch processing for efficiency (optional optimization)

**select_transport_people(tagged: list[PersonWithTags]) -> list[PersonWithTags]:**
- Filter where "transport" in person.tags
- Return filtered list

**submit_to_verify(api_key: str, people: list[PersonWithTags]) -> dict:**
- Build payload: {"apikey": api_key, "task": "people", "answer": [...]}
- Convert PersonWithTags to dict format (name, surname, gender, born, city, tags)
- POST to `https://hub.ag3nts.org/verify`
- Parse JSON response
- Extract flag from response
- Return response dict

**execute_quest(api_key: str) -> QuestResult:**
- Call all functions in sequence
- Track counts at each step
- Catch exceptions and populate error field
- Return QuestResult with all data for UI rendering

---

## UI/UX Design

### Main Template (quest.html)

**Header Section:**
- Title: "Quest - People Finder"
- Description: "Identify transport workers from the Great Correction survivor database"

**Action Section:**
- Single button: "Execute Quest"
- HTMX attributes:
  ```html
  hx-post="{% url 'l01_quest_api' %}"
  hx-target="#quest-result"
  hx-swap="innerHTML"
  hx-indicator="#loading-spinner"
  ```
- Loading spinner (shown during request)

**Result Container:**
- Empty div with id="quest-result"
- HTMX swaps content here

### Result Partial (quest_result.html)

**Error Display (if error):**
- Red banner with error message
- Retry suggestion

**Success Display (if no error):**

**Progress Steps Accordion:**
- Step 1: Downloaded {total_downloaded} people
- Step 2: Filtered to {after_filter} people (Male, age 20-40, Grudziądz)
- Step 3: Tagged jobs with LLM
- Step 4: Found {transport_workers} transport workers
- Step 5: Submitted to hub
- Each step expandable for details

**Statistics Cards:**
- Total downloaded, Filtered, Transport workers
- Visual cards with Tailwind styling

**People List:**
- Table format
- Columns: Name, Surname, Birth Year, Tags
- Show all submitted people

**Flag Display:**
- Large, prominent banner
- Green background (bg-green-500)
- Large text (text-2xl or text-3xl)
- Format: "🎉 SUCCESS! Flag: {FLG:SOMETHING}"
- Copyable (click to copy)

---

## Technical Considerations

### Performance
- LLM tagging: ~30-60 seconds for 50-100 people (sequential calls)
- Optimization: Batch jobs in one LLM call with structured array output (future enhancement)
- CSV caching: Consider storing in session/temp file for re-runs

### Error Handling
- CSV download failure: Clear message, check API key
- LLM API failure: Retry logic or detailed error
- Verify endpoint failure: Show response body
- No matching people: Show message (not error)
- Invalid CSV format: Validate columns

### Rate Limiting
- OpenRouter: Respect rate limits
- Consider adding delay between LLM calls if needed

### Data Validation
- Validate CSV has required columns
- Validate Person model fields
- Validate tag format from LLM

---

## Implementation Sequence

1. **Setup Static Files**
   - Create `static/fonts/` directory
   - Download Xirod font
   - Update settings.py with STATICFILES_DIRS

2. **Update Base Template**
   - Add {% load static %}
   - Add @font-face in style block
   - Apply font to header
   - Update subtitle text

3. **Create Quest Service**
   - Write quest_service.py with all models and functions
   - Test individual functions in Django shell

4. **Create Quest Views**
   - Write quest.py with quest_view and quest_api
   - Import quest_service functions

5. **Create Quest Templates**
   - Write quest.html (main template)
   - Write quest_result.html (partial)
   - Follow existing module styling patterns

6. **Update URL Configuration**
   - Add quest routes to lesson_01/urls.py

7. **Update Navigation**
   - Add quest entry to core/nav_registry.py

8. **Update Settings**
   - Add AIDEVS_API_KEY to settings.py

9. **Test Complete Workflow**
   - Start Django dev server
   - Navigate to Quest module
   - Execute workflow
   - Verify each step
   - Check flag display

10. **Test Header Changes**
    - Verify Xirod font loads
    - Verify text updates
    - Check browser console for errors

---

## Verification Steps

### Quest Module Testing:
1. Navigate to "01 — Basics" → "Quest" in sidebar
2. Click "Execute Quest" button
3. Verify loading spinner appears
4. Wait for completion (~30-60 seconds)
5. Verify step-by-step progress displays
6. Verify statistics are accurate
7. Verify people list shows transport workers
8. Verify flag displays prominently
9. Copy flag and verify format: `{FLG:SOMETHING}`

### Header Testing:
1. Refresh main page
2. Verify "Damian's Operation Center" uses Xirod font
3. Verify subtitle reads "| |AI_Devs4 - Builders | Dashboard"
4. Check browser DevTools: Network tab shows Xirod.ttf loaded
5. Check Console for no 404 errors

### Error Testing:
1. Temporarily modify AIDEVS_API_KEY to invalid value
2. Execute quest
3. Verify clear error message displays
4. Restore correct API key
5. Verify retry works

---

## Dependencies

**Already in requirements.txt:**
- django>=5.0
- langchain-openai
- pydantic
- requests
- python-dotenv

**No new dependencies needed** - all libraries already available.

---

## Success Criteria

✅ Quest module appears in "01 — Basics" navigation
✅ Clicking Quest loads the module UI
✅ Execute button triggers full workflow
✅ Each step completes without errors
✅ LLM successfully tags jobs with structured output
✅ Transport workers correctly identified
✅ Submission to hub succeeds
✅ Flag displays prominently in UI
✅ Header font changes to Xirod
✅ Header subtitle updates to new text
✅ No console errors
✅ HTMX functionality works smoothly
✅ Error handling graceful and informative

---

## Notes

- **Save plan**: This plan will be saved in `c:\zz_projects\dp_ai_devs_centrala\lesson_01\0101task_context\` folder as per user request
- **Existing plan**: There's already an `implementation_plan.md` in that folder - this plan supersedes it with actionable steps
- **API key**: Already in .env, no user action needed
- **Font license**: Xirod is free for personal use from 1001fonts.com
- **Execution time**: ~30-60 seconds due to LLM calls (set user expectation)
- **Flag format**: Unknown until received, display as-is from API response
- **Polish language**: Task description is in Polish, but implementation in English (standard practice)

---

## Estimated Implementation Time

- Static files setup: 10 minutes
- Header updates: 10 minutes
- Quest service layer: 60 minutes
- Quest views: 20 minutes
- Quest templates: 45 minutes
- Configuration updates: 10 minutes
- Testing and debugging: 30 minutes

**Total: ~3 hours**
