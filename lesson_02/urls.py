from django.urls import path
from lesson_02.views import tools, tool_use

urlpatterns = [
    # Minimal tool (weather + manual tool loop)
    path("tools/",        tools.tools_view,       name="l02_tools"),
    path("tools/api/",    tools.tools_api,         name="l02_tools_api"),

    # FS agent (sandboxed filesystem + AgentExecutor)
    path("tool-use/",     tool_use.tool_use_view,  name="l02_tool_use"),
    path("tool-use/api/", tool_use.tool_use_api,   name="l02_tool_use_api"),
]
