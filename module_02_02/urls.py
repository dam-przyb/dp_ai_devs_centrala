"""URL configuration for module_02_02."""

from django.urls import path

from module_02_02 import views

urlpatterns = [
    # Chunking demo
    path("chunking/",     views.chunking_index, name="m0202_chunking"),
    path("chunking/run/", views.chunking_run,   name="m0202_chunking_run"),

    # Embeddings demo
    path("embeddings/",         views.embeddings_index,   name="m0202_embeddings"),
    path("embeddings/compute/", views.embeddings_compute, name="m0202_embeddings_compute"),

    # Hybrid RAG chat
    path("rag/",        views.rag_index,   name="m0202_hybrid_rag"),
    path("rag/chat/",   views.rag_chat,    name="m0202_rag_chat"),
    path("rag/clear/",  views.rag_clear,   name="m0202_rag_clear"),
    path("rag/reindex/", views.rag_reindex, name="m0202_rag_reindex"),
]
