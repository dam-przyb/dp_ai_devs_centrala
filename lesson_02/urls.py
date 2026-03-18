from django.urls import path
from lesson_02.views import tools, tool_use, findhim

urlpatterns = [
    # Minimal tool (weather + manual tool loop)
    path("tools/",        tools.tools_view,       name="l02_tools"),
    path("tools/api/",    tools.tools_api,         name="l02_tools_api"),

    # FS agent (sandboxed filesystem + AgentExecutor)
    path("tool-use/",     tool_use.tool_use_view,  name="l02_tool_use"),
    path("tool-use/api/", tool_use.tool_use_api,   name="l02_tool_use_api"),

    # FindHim investigation agent (S01E02)
    path("findhim/",      findhim.findhim_view,    name="l02_findhim"),
    path("findhim/api/",  findhim.findhim_api,     name="l02_findhim_api"),
]
