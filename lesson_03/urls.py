from django.urls import path
from lesson_03.views import mcp_core, mcp_native, mcp_translator, upload_mcp

urlpatterns = [
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
