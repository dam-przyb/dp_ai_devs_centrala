# Implementation Plan: Quest Module for Lesson 01

## Task Overview
Create a new module "Quest" under "01 — Basics" that automates the task from task.txt:
- Download people.csv from ag3nts.org
- Filter people by criteria (male, 20-40 years old in 2026, born in Grudziądz)
- Tag jobs using LLM with structured output
- Submit filtered results to ag3nts.org
- Display the flag response

## Current Codebase Understanding

### Architecture
- **Framework**: Django with HTMX for dynamic content loading
- **Structure**: Modular lesson-based apps (lesson_01, lesson_02, etc.)
- **Navigation**: Centralized in `core/nav_registry.py`
- **Pattern**: Each module has views, services, templates, and URLs
- **LLM Integration**: Using OpenRouter API via LangChain with structured output

### Existing Patterns in lesson_01
1. **Interaction**: Multi-turn chat with session-based history
2. **Structured**: Single-form structured output demo
3. **Grounding**: RAG-based Q&A system

All use the service layer pattern with Pydantic models for structured data.

---

## Implementation Plan

### Phase 1: UI & Cosmetic Changes

#### 1.1 Font Integration (Xirod Font)
**File**: `core/templates/core/base.html`

**Changes**:
- Add font import in `<head>`:
  ```html
  <link href="https://fonts.cdnfonts.com/css/xirod" rel="stylesheet">
  ```
  Or download and serve locally from static files
- Update the title span styling:
  ```html
  <style>
    .title-font {
      font-family: 'Xirod', sans-serif;
    }
  </style>
  <span class="text-lg font-bold tracking-wide title-font">Damian's Operation Center</span>
  ```

**Location**: Lines 6-24 in `base.html`

#### 1.2 Dashboard Subtitle Update
**File**: `core/templates/core/base.html:21`

**Change**:
```html
<!-- FROM -->
<span class="text-gray-500 text-xs">| AI Devs Dashboard</span>

<!-- TO -->
<span class="text-gray-500 text-xs">| |AI_Devs4 - Builders | Dashboard</span>
```

---

### Phase 2: Quest Module Implementation

#### 2.1 Navigation Registry Update
**File**: `core/nav_registry.py`

**Change**: Add new module to the "01 — Basics" section (id: "01_01"):
```python
{
    "slug": "quest",
    "label": "Quest",
    "url_name": "l01_quest",
},
```

**Insert After**: Line 29 (after "grounding" module)

#### 2.2 Environment Configuration
**File**: `.env` (update) and `.env.example` (update)

**Add**:
```
AG3NTS_API_KEY=your_api_key_here
```

**File**: `operation_center/settings.py`

**Add** (after line 110):
```python
# AG3NTS Hub API key (lesson 01 quest)
AG3NTS_API_KEY = os.getenv("AG3NTS_API_KEY", "")
```

#### 2.3 Data Models
**File**: `lesson_01/models.py`

**Add** (if we want to persist results):
```python
class QuestPerson(models.Model):
    """Stores people who match the quest criteria."""
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    gender = models.CharField(max_length=1)
    born = models.IntegerField()
    city = models.CharField(max_length=100)
    job = models.TextField()
    tags = models.JSONField()  # List of tags assigned by LLM
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lesson_01_quest_person"
        ordering = ['-created_at']

class QuestExecution(models.Model):
    """Tracks quest execution history."""
    executed_at = models.DateTimeField(auto_now_add=True)
    total_people = models.IntegerField()
    filtered_people = models.IntegerField()
    transport_people = models.IntegerField()
    flag = models.CharField(max_length=200, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "lesson_01_quest_execution"
        ordering = ['-executed_at']
```

**Migration**: Run `python manage.py makemigrations lesson_01` after adding models.

#### 2.4 Service Layer
**File**: `lesson_01/services/quest_service.py` (NEW)

**Purpose**: Business logic for the quest task

**Key Functions**:
1. `download_people_csv(api_key: str) -> list[dict]`
   - Downloads CSV from `https://hub.ag3nts.org/data/{api_key}/people.csv`
   - Parses and returns as list of dictionaries
   - Uses `requests` or `httpx` library

2. `filter_people(people: list[dict]) -> list[dict]`
   - Filters by:
     - Gender: "M"
     - Age: born between 1986-2006 (20-40 years in 2026)
     - City: "Grudziądz"
   - Returns filtered list

3. `tag_jobs_batch(people: list[dict]) -> list[dict]`
   - Uses LLM with structured output to tag jobs
   - Implements batch processing (all jobs in one LLM call)
   - Pydantic model for tags:
     ```python
     class PersonTags(BaseModel):
         person_index: int
         tags: list[str]  # From: IT, transport, edukacja, medycyna, praca z ludźmi, praca z pojazdami, praca fizyczna

     class BatchTagResult(BaseModel):
         results: list[PersonTags]
     ```
   - Returns people list with tags added

4. `filter_transport(people: list[dict]) -> list[dict]`
   - Filters people who have "transport" tag
   - Returns final filtered list

5. `submit_to_hub(api_key: str, people: list[dict]) -> dict`
   - Posts to `https://hub.ag3nts.org/verify`
   - Format:
     ```json
     {
       "apikey": "...",
       "task": "people",
       "answer": [{"name": "...", "surname": "...", "gender": "...", "born": ..., "city": "...", "tags": ["..."]}]
     }
     ```
   - Returns response (should contain flag)

6. `execute_quest(api_key: str) -> dict`
   - Orchestrates the entire quest pipeline
   - Returns results dict with:
     - success: bool
     - flag: str
     - total_people: int
     - filtered_people: int
     - transport_people: int
     - people: list[dict]
     - error: str (if any)

**Implementation Notes**:
- Use `ChatOpenAI` with `with_structured_output()` (following structured_service.py pattern)
- Include tag descriptions in LLM prompt to improve classification
- Use batch processing (one LLM call for all jobs) to reduce API costs
- Handle errors gracefully (network, API, LLM)

#### 2.5 View Layer
**File**: `lesson_01/views/quest.py` (NEW)

**Functions**:
1. `quest_view(request: HttpRequest) -> HttpResponse`
   - GET endpoint
   - Renders main quest interface
   - Shows history of previous executions (from QuestExecution model)
   - Template: `lesson_01/templates/lesson_01/quest.html`

2. `quest_execute_api(request: HttpRequest) -> HttpResponse`
   - POST endpoint
   - Calls `execute_quest()` service
   - Saves results to database
   - Returns partial template with results
   - Template: `lesson_01/templates/lesson_01/partials/quest_result.html`

**Pattern**: Follow interaction.py structure (clean separation of GET/POST)

#### 2.6 URL Configuration
**File**: `lesson_01/urls.py`

**Add** (after grounding paths):
```python
# Quest (task 0101)
path("quest/",       quest.quest_view,        name="l01_quest"),
path("quest/api/",   quest.quest_execute_api, name="l01_quest_api"),
```

**Update imports**:
```python
from lesson_01.views import interaction, structured, grounding, quest
```

#### 2.7 Templates

##### Main Template: `lesson_01/templates/lesson_01/quest.html`

**Structure**:
```html
<div class="flex flex-col h-full">
  <!-- Header -->
  <div class="px-6 py-4 border-b bg-gray-50">
    <h2 class="font-semibold text-gray-800">Quest — People Identification Task</h2>
    <p class="text-xs text-gray-500 mt-0.5">
      Filter and tag people from ag3nts.org database
    </p>
  </div>

  <!-- Content Area -->
  <div class="flex-1 overflow-y-auto p-6">

    <!-- Description Card -->
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
      <h3 class="font-semibold text-blue-900 mb-2">Task Description</h3>
      <ul class="text-sm text-blue-800 space-y-1 list-disc list-inside">
        <li>Download people.csv from ag3nts.org</li>
        <li>Filter: Men, 20-40 years old (in 2026), born in Grudziądz</li>
        <li>Tag jobs using LLM (structured output)</li>
        <li>Select people with "transport" tag</li>
        <li>Submit to ag3nts.org/verify</li>
      </ul>
    </div>

    <!-- Execute Button -->
    <div class="mb-6">
      <button
        hx-post="{% url 'l01_quest_api' %}"
        hx-target="#quest-result"
        hx-swap="innerHTML"
        class="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-medium transition-colors">
        🚀 Execute Quest
      </button>
    </div>

    <!-- Results Container -->
    <div id="quest-result">
      <!-- Results will be injected here via HTMX -->
    </div>

    <!-- Execution History -->
    <div class="mt-8">
      <h3 class="font-semibold text-gray-800 mb-3">Execution History</h3>
      <div class="space-y-2">
        {% for exec in executions %}
        <div class="border rounded-lg p-3 {% if exec.success %}bg-green-50 border-green-200{% else %}bg-red-50 border-red-200{% endif %}">
          <div class="flex justify-between items-start">
            <div>
              <span class="text-xs text-gray-500">{{ exec.executed_at|date:"Y-m-d H:i" }}</span>
              {% if exec.success %}
                <p class="text-sm text-green-800 font-medium mt-1">Success! Flag: {{ exec.flag }}</p>
              {% else %}
                <p class="text-sm text-red-800 mt-1">Failed: {{ exec.error_message }}</p>
              {% endif %}
            </div>
            <div class="text-xs text-gray-600">
              {{ exec.transport_people }} / {{ exec.filtered_people }} / {{ exec.total_people }}
            </div>
          </div>
        </div>
        {% empty %}
        <p class="text-sm text-gray-400 italic">No executions yet.</p>
        {% endfor %}
      </div>
    </div>

  </div>
</div>
```

##### Result Partial: `lesson_01/templates/lesson_01/partials/quest_result.html`

**Structure**:
```html
{% if success %}
<div class="bg-green-50 border border-green-200 rounded-lg p-6 mb-4">
  <h3 class="text-lg font-semibold text-green-900 mb-3">✅ Quest Completed!</h3>

  <div class="space-y-2 mb-4">
    <p class="text-sm text-green-800"><strong>Flag:</strong> <code class="bg-green-100 px-2 py-1 rounded">{{ flag }}</code></p>
    <p class="text-sm text-green-800"><strong>Total People Downloaded:</strong> {{ total_people }}</p>
    <p class="text-sm text-green-800"><strong>After Filtering (M, 20-40, Grudziądz):</strong> {{ filtered_people }}</p>
    <p class="text-sm text-green-800"><strong>With Transport Tag:</strong> {{ transport_people }}</p>
  </div>

  <!-- Expandable People List -->
  <details class="mt-4">
    <summary class="cursor-pointer text-sm font-medium text-green-900 hover:text-green-700">
      View Selected People ({{ transport_people }})
    </summary>
    <div class="mt-3 space-y-2">
      {% for person in people %}
      <div class="bg-white border border-green-200 rounded p-3 text-sm">
        <p class="font-medium">{{ person.name }} {{ person.surname }}</p>
        <p class="text-gray-600 text-xs">Born: {{ person.born }} | City: {{ person.city }}</p>
        <p class="text-gray-600 text-xs">Job: {{ person.job }}</p>
        <p class="text-gray-600 text-xs">Tags: {{ person.tags|join:", " }}</p>
      </div>
      {% endfor %}
    </div>
  </details>
</div>
{% else %}
<div class="bg-red-50 border border-red-200 rounded-lg p-6">
  <h3 class="text-lg font-semibold text-red-900 mb-2">❌ Quest Failed</h3>
  <p class="text-sm text-red-800">{{ error }}</p>
</div>
{% endif %}
```

---

### Phase 3: Testing & Refinement

#### 3.1 Manual Testing Checklist
- [ ] Font displays correctly in title
- [ ] Subtitle text is updated
- [ ] Quest module appears in sidebar navigation
- [ ] Clicking Quest loads the interface
- [ ] Execute button triggers the quest
- [ ] CSV downloads successfully
- [ ] Filtering works correctly (age calculation, city, gender)
- [ ] LLM tagging works with structured output
- [ ] Transport filtering is accurate
- [ ] Submission to hub succeeds
- [ ] Flag is displayed in results
- [ ] Execution history saves and displays
- [ ] Error handling works (network errors, API errors)

#### 3.2 Edge Cases to Handle
1. **Missing/Invalid API Key**: Show clear error message
2. **Network Failures**: Retry logic or clear error
3. **LLM Failures**: Fallback or error handling
4. **Invalid CSV Format**: Parse error handling
5. **Hub API Errors**: Display response errors
6. **Empty Results**: Handle case where no one matches

---

## Alternative Approaches Considered

### Option A: Step-by-Step UI (Not Recommended)
- Separate buttons for each step
- Shows intermediate results
- **Pros**: More educational, easier to debug
- **Cons**: More complex UI, more HTMX endpoints

### Option B: Notebook Integration (Not Recommended)
- Keep as Jupyter notebook
- Embed in Django via iframe or nbconvert
- **Pros**: Easy to iterate, familiar format
- **Cons**: Doesn't fit UI patterns, harder to maintain

### Option C: API Key in UI (Not Chosen)
- Input field for API key in the form
- **Pros**: More flexible, no .env needed
- **Cons**: Less secure, inconsistent with app pattern

---

## File Structure Summary

```
lesson_01/
├── views/
│   ├── __init__.py
│   ├── interaction.py
│   ├── structured.py
│   ├── grounding.py
│   └── quest.py (NEW)
├── services/
│   ├── __init__.py
│   ├── interaction_service.py
│   ├── structured_service.py
│   ├── grounding_service.py
│   └── quest_service.py (NEW)
├── templates/
│   └── lesson_01/
│       ├── interaction.html
│       ├── structured.html
│       ├── grounding.html
│       ├── quest.html (NEW)
│       └── partials/
│           ├── chat_message.html
│           ├── structured_result.html
│           ├── grounding_result.html
│           └── quest_result.html (NEW)
├── models.py (UPDATE - add QuestPerson, QuestExecution)
├── urls.py (UPDATE - add quest paths)
└── 0101task_context/
    ├── task.txt
    ├── hints.txt
    ├── output_template.json
    └── implementation_plan.md (THIS FILE)
```

---

## Dependencies to Check

Current dependencies (from requirements.txt):
- ✅ django
- ✅ langchain-openai (for LLM)
- ✅ pydantic (for structured models)
- ✅ python-dotenv (for .env)

May need to add:
- ✅ httpx or requests (for HTTP calls) - likely already installed as langchain dependency
- ✅ pandas (optional, for CSV handling) - or use Python's csv module

---

## Implementation Time Estimate

- **Phase 1 (UI/Cosmetic)**: 15-30 minutes
- **Phase 2.1-2.3 (Setup)**: 30 minutes
- **Phase 2.4 (Service Logic)**: 2-3 hours (main complexity)
- **Phase 2.5-2.7 (Views/Templates)**: 1-2 hours
- **Phase 3 (Testing)**: 1 hour
- **Total**: 5-7 hours

---

## Questions for User

Before implementation, please clarify:

1. **API Key Storage**: Should AG3NTS_API_KEY be in .env (recommended) or configurable in UI?

2. **Results Display**: After success, should we:
   - Display the flag only?
   - Show filtered people list?
   - Save to database models?
   - All of the above?

3. **Execution Mode**:
   - Single button (execute everything) - RECOMMENDED
   - Step-by-step buttons (download → filter → tag → submit)
   - Expandable sections showing progress

4. **Error Handling**: If quest fails:
   - Just show error message?
   - Allow retry with different parameters?
   - Log detailed debug info?

5. **Existing Work**: You mentioned a first iteration in .ipynb file. Should I:
   - Look for it elsewhere (different location)?
   - Start fresh following the patterns above?
   - Migrate notebook code to Django if found?

---

## Next Steps (After Approval)

1. Implement Phase 1 (cosmetic changes) - quick win
2. Set up Phase 2.1-2.3 (infrastructure)
3. Implement Phase 2.4 (service logic) - core functionality
4. Build Phase 2.5-2.7 (UI layer)
5. Test and refine (Phase 3)
6. Create migration and run it
7. Restart Django server and verify

---

## Notes

- The implementation follows existing patterns in the codebase
- Uses structured output (LangChain + Pydantic) as demonstrated in structured_service.py
- HTMX pattern consistent with other modules
- Database models optional but recommended for tracking
- Batch LLM processing reduces API costs significantly
- Font integration may require testing across browsers

