"""
Central navigation registry.

NAV is a two-level hierarchy:  Season → Lessons → Modules.

Structure:
    NAV: list[Season]
    Season:
        id          str         e.g. "S1"
        label       str         e.g. "Season 1 — Foundations"
        lessons:    list[Lesson]
    Lesson:
        id          str         e.g. "01_01"
        label       str         e.g. "01 — Basics"
        modules:    list[Module]
    Module:
        slug        str         unique within lesson
        label       str         display name
        url_name    str | None  Django URL name; None = "coming soon"
"""

NAV = [
    # =========================================================================
    # Season 1 — Foundations
    # =========================================================================
    {
        "id": "S1",
        "label": "Season 1 — Foundations",
        "lessons": [
            {
                "id": "01_01",
                "label": "01 — Basics",
                "modules": [
                    {
                        "slug": "interaction",
                        "label": "Interaction (Chat)",
                        "url_name": "l01_interaction",
                    },
                    {
                        "slug": "structured",
                        "label": "Structured Output",
                        "url_name": "l01_structured",
                    },
                    {
                        "slug": "grounding",
                        "label": "Grounding (RAG)",
                        "url_name": "l01_grounding",
                    },
                    {
                        "slug": "quest",
                        "label": "Quest",
                        "url_name": "l01_quest",
                    },
                ],
            },
            {
                "id": "01_02",
                "label": "02 — Tool Use",
                "modules": [
                    {
                        "slug": "tools",
                        "label": "Minimal Tool",
                        "url_name": "l02_tools",
                    },
                    {
                        "slug": "tool_use",
                        "label": "FS Agent",
                        "url_name": "l02_tool_use",
                    },
                    {
                        "slug": "findhim",
                        "label": "Quest",
                        "url_name": "l02_findhim",
                    },
                ],
            },
            {
                "id": "01_03",
                "label": "03 — MCP",
                "modules": [
                    {
                        "slug": "quest",
                        "label": "Quest",
                        "url_name": "l03_quest",
                    },
                    {
                        "slug": "mcp_core",
                        "label": "MCP Core",
                        "url_name": "l03_mcp_core",
                    },
                    {
                        "slug": "mcp_native",
                        "label": "MCP Native",
                        "url_name": "l03_mcp_native",
                    },
                    {
                        "slug": "mcp_translator",
                        "label": "MCP Translator",
                        "url_name": "l03_mcp_translator",
                    },
                    {
                        "slug": "upload_mcp",
                        "label": "Upload MCP",
                        "url_name": "l03_upload_mcp",
                    },
                ],
            },
            {
                "id": "01_04",
                "label": "04 — Media",
                "modules": [
                    {
                        "slug": "audio",
                        "label": "Audio Transcription",
                        "url_name": "l04_audio",
                    },
                    {
                        "slug": "video_gen",
                        "label": "Video Generation",
                        "url_name": "l04_video_gen",
                    },
                    {
                        "slug": "image",
                        "label": "Image Generation",
                        "url_name": "l04_image",
                    },
                    {
                        "slug": "report",
                        "label": "PDF Report",
                        "url_name": "l04_report",
                    },
                    {
                        "slug": "sendit",
                        "label": "Quest (SPK)",
                        "url_name": "l04_sendit",
                    },
                ],
            },
            {
                "id": "01_05",
                "label": "05 — Orchestration",
                "modules": [
                    {
                        "slug": "confirmation",
                        "label": "Human-in-the-Loop",
                        "url_name": "l05_confirmation",
                    },
                    {
                        "slug": "agent",
                        "label": "Master Orchestrator",
                        "url_name": "l05_agent",
                    },
                    {
                        "slug": "railway",
                        "label": "Railway Quest",
                        "url_name": "l05_railway",
                    },
                ],
            },
        ],
    },
    # =========================================================================
    # Season 2 — Advanced Agents
    # =========================================================================
    {
        "id": "S2",
        "label": "Season 2 — Advanced Agents",
        "lessons": [
            {
                "id": "02_01",
                "label": "06 — Agentic RAG",
                "modules": [
                    {
                        "slug": "rag_agent",
                        "label": "File-Tool RAG Agent",
                        "url_name": "m0201_rag_agent",
                    },
                ],
            },
            {
                "id": "02_02",
                "label": "07 — Chunking & Embeddings",
                "modules": [
                    {
                        "slug": "chunking",
                        "label": "Chunking Demo",
                        "url_name": "m0202_chunking",
                    },
                    {
                        "slug": "embeddings",
                        "label": "Embeddings Demo",
                        "url_name": "m0202_embeddings",
                    },
                    {
                        "slug": "hybrid_rag",
                        "label": "Hybrid RAG",
                        "url_name": "m0202_hybrid_rag",
                    },
                ],
            },
            {
                "id": "02_03",
                "label": "08 — Graph RAG",
                "modules": [
                    {
                        "slug": "graph_rag",
                        "label": "Graph RAG Agent",
                        "url_name": None,
                    },
                ],
            },
            {
                "id": "02_04",
                "label": "09 — Daily Ops Workflow",
                "modules": [
                    {
                        "slug": "daily_ops",
                        "label": "Daily Ops",
                        "url_name": None,
                    },
                ],
            },
            {
                "id": "02_05",
                "label": "10 — Memory & Sandbox",
                "modules": [
                    {
                        "slug": "memory_chat",
                        "label": "Observational Memory Chat",
                        "url_name": None,
                    },
                    {
                        "slug": "sandbox",
                        "label": "MCP Sandbox Agent",
                        "url_name": None,
                    },
                ],
            },
        ],
    },
]
