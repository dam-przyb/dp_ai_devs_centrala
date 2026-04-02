"""
Central navigation registry.

Each entry in NAV describes one lesson with its modules.
The `url_name` field maps to a Django URL name — used in templates with {% url module.url_name %}.
Modules without a url_name are rendered as "coming soon" placeholders.
"""

NAV = [
    {
        "id": "01_01",
        "chapter": "01",
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
        "chapter": "01",
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
        "chapter": "01",
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
        "chapter": "01",
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
        "chapter": "01",
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
        ],
    },
]
