from django.urls import path
from lesson_01.views import interaction, structured, grounding

urlpatterns = [
    # Interaction (multi-turn chat)
    path("interaction/",     interaction.interaction_view, name="l01_interaction"),
    path("interaction/api/", interaction.interaction_api,  name="l01_interaction_api"),

    # Structured output
    path("structured/",      structured.structured_view,   name="l01_structured"),
    path("structured/api/",  structured.structured_api,    name="l01_structured_api"),

    # Grounding (RAG)
    path("grounding/",       grounding.grounding_view,     name="l01_grounding"),
    path("grounding/api/",   grounding.grounding_api,      name="l01_grounding_api"),
]
