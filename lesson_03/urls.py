from django.urls import path
from lesson_03.views import mcp_core, mcp_native, mcp_translator, quest, upload_mcp

urlpatterns = [
    # Quest (S01E03 proxy mission)
    path("quest/",            quest.quest_view,         name="l03_quest"),
    path("quest/status/",     quest.quest_status_api,   name="l03_quest_status_api"),
    path("quest/tunnel/start/", quest.quest_tunnel_start_api, name="l03_quest_tunnel_start_api"),
    path("quest/tunnel/stop/",  quest.quest_tunnel_stop_api,  name="l03_quest_tunnel_stop_api"),
    path("quest/verify/retry/", quest.quest_verify_retry_api,  name="l03_quest_verify_retry_api"),
    path("quest/probe/",      quest.quest_probe_api,    name="l03_quest_probe_api"),

    # Public proxy endpoint contract
    path("quest/proxy/",      quest.proxy_endpoint_api, name="l03_proxy_endpoint"),

    # MCP tool explorer — list tools, call them directly
    path("mcp-core/",        mcp_core.mcp_core_view,         name="l03_mcp_core"),
    path("mcp-core/api/",    mcp_core.mcp_core_api,          name="l03_mcp_core_api"),

    # Native MCP call — no LangChain, raw ClientSession usage
    path("mcp-native/",      mcp_native.mcp_native_view,     name="l03_mcp_native"),
    path("mcp-native/api/",  mcp_native.mcp_native_api,      name="l03_mcp_native_api"),

    # Translator — MCP tools wrapped as LangChain tools inside an agent
    path("mcp-translator/",      mcp_translator.mcp_translator_view,  name="l03_mcp_translator"),
    path("mcp-translator/api/",  mcp_translator.mcp_translator_api,   name="l03_mcp_translator_api"),

    # Upload + MCP — upload a file, process it with the MCP filesystem agent
    path("upload-mcp/",      upload_mcp.upload_mcp_view,     name="l03_upload_mcp"),
    path("upload-mcp/api/",  upload_mcp.upload_mcp_api,      name="l03_upload_mcp_api"),
]
