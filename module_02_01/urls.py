from django.urls import path
from module_02_01 import views

urlpatterns = [
    # Main workspace page (GET)
    path("",       views.index_view, name="m0201_rag_agent"),

    # HTMX chat endpoint (POST) — returns _chat_result.html partial
    path("chat/",  views.chat_api,   name="m0201_rag_chat"),

    # HTMX clear endpoint (POST) — resets session and returns empty state
    path("clear/", views.clear_api,  name="m0201_rag_clear"),
]
