# General Architecture & UI Specification

**Context**: Building a unified dashboard interface using a Django monolith with HTMX.

## 1. UI Layout Specification (`frontend_layout.jpg`)

The entire application will reside in a single dashboard screen constructed with Django Templates and Tailwind CSS.

### 1.1 Main Canva (`<body class="flex flex-col h-screen overflow-hidden...">`)
The root application container holding the layout structure.

### 1.2 Title Bar (`<header class="...">`)
*   **Location**: Top edge of the screen, spanning full width or spanning the workspace width.
*   **Content**: "Damian's Operation Center".
*   **Role**: Static header, branding.

### 1.3 Nav Bar (`<nav class="w-64 flex-shrink-0...">`)
*   **Location**: Left side of the screen as a persistent sidebar.
*   **Content**: A hierarchical, collapsible menu.
    *   Level 1: Course Chapters (e.g., "01").
    *   Level 2: Lessons (e.g., "[01, 01_interaction]").
    *   Level 3: Specific Modules ("interaction", "grounding").
*   **Interaction Strategy (HTMX)**: 
    *   When a user clicks a module name, it triggers an HTMX request `hx-get="/lesson/01_01/interaction/"`.
    *   The request specifically targets the Workspace container (`hx-target="#workspace-container"`).
    *   This ensures only the tool's interface changes, creating a single-page application feel without React.

### 1.4 Workspace (`<main id="workspace-container" class="flex-grow...">`)
*   **Location**: The large main area occupying the rest of the screen (right of the nav bar, below the title bar).
*   **Role**: This is the dynamic mounting point. When a Django view returns an HTMX partial response, that HTML snippet (e.g., a chat interface, an upload form) is injected here.

## 2. Backend Routing Strategy

Rather than building JSON APIs, the Django views render HTML partials natively.

**Example Flow**:
1. User loads `/`. Django renders `base.html` containing the Nav Bar and an empty `#workspace-container`.
2. User clicks "Tool Use" in the Nav Bar. The link has `hx-get="/modules/01_02/tool_use/" hx-target="#workspace-container"`.
3. The Django URL router directs to `views.module_01_02_tool_use`.
4. The view returns ONLY the rendered HTML for the specific tool (e.g., `<div class="tool-demo"><form hx-post="...">...</form></div>`).
5. HTMX swaps that HTML into the Workspace.
