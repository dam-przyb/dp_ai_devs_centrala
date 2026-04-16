"""
Document indexer for module_02_02 Hybrid RAG.

Responsibilities
----------------
- Enumerate markdown files in the workspace directory.
- Skip files whose SHA-256 hash has not changed since last indexing.
- Split each file into chunks using the 'separators' strategy.
- Compute text-embedding-3-small embeddings for each chunk.
- Write documents, chunks, FTS entries, and vector rows to SQLite.
- Prune rows belonging to files that no longer exist on disk.

Public API
----------
    from module_02_02.indexer import index_workspace
    stats = index_workspace()  # returns {"indexed": N, "skipped": N, "deleted": N}
"""

from __future__ import annotations

import hashlib
import struct
import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from module_02_02.db import get_connection, init_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Separator strategy settings — matches spec acceptance criteria
_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", " "]
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 200

# Embedding model — text-embedding-3-small, dim 1536
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBED_BATCH_SIZE = 20  # embed N chunks per API call to stay within rate limits


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _workspace_dir() -> Path:
    """
    Return the workspace directory scoped to module_02_02.

    The workspace lives at <MEDIA_ROOT>/module_02_02/workspace/ and is
    distinct from the _lessons_texts directory used by module_02_01.
    """
    ws = Path(settings.MEDIA_ROOT) / "module_02_02" / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _pack_vector(embedding: list[float]) -> bytes:
    """
    Serialise a float list to little-endian binary for sqlite-vec.

    sqlite-vec expects raw IEEE-754 float32 bytes for vec0 inserts.
    """
    return struct.pack(f"{len(embedding)}f", *embedding)


def _get_embedder() -> OpenAIEmbeddings:
    """
    Build an OpenAIEmbeddings instance pointing at the OpenRouter gateway.

    We use the OpenAI-compatible endpoint exposed by OpenRouter so that
    the same API key works for both chat and embeddings.
    """
    return OpenAIEmbeddings(
        model=_EMBEDDING_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
    )


def _chunk_document(text: str) -> list[str]:
    """
    Split a document into chunks using the separator strategy from the spec.

    Uses RecursiveCharacterTextSplitter with the heading/paragraph separators
    defined in the module spec.

    Args:
        text: Full document text.

    Returns:
        List of text chunk strings.
    """
    splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS,
        chunk_size=_CHUNK_SIZE,
        chunk_overlap=_CHUNK_OVERLAP,
        keep_separator=True,
    )
    return splitter.split_text(text)


def _embed_in_batches(
    texts: list[str],
    embedder: OpenAIEmbeddings,
) -> list[list[float]]:
    """
    Embed a list of texts in batches to respect API rate limits.

    Args:
        texts:    Texts to embed.
        embedder: Configured OpenAIEmbeddings instance.

    Returns:
        List of embedding vectors (same order as input texts).
    """
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        vectors.extend(embedder.embed_documents(batch))
    return vectors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_workspace() -> dict[str, int]:
    """
    Index (or re-index) all markdown files in the workspace directory.

    Algorithm:
    1. Open DB, ensure schema exists.
    2. Load current {path → sha256} map from the documents table.
    3. Walk the workspace directory for *.md files.
    4. Skip any file whose hash matches the stored value.
    5. For new/changed files: chunk → embed → write rows.
    6. Delete rows for files that no longer exist on disk.

    Returns:
        dict with keys "indexed", "skipped", "deleted".

    Raises:
        Exception: Any failure is logged and re-raised so the view can report it.
    """
    conn = get_connection()
    init_db(conn)
    embedder = _get_embedder()

    ws_dir = _workspace_dir()
    md_files = sorted(ws_dir.glob("*.md"))

    # Load existing path → (id, sha256) map from DB
    existing: dict[str, dict[str, Any]] = {}
    for row in conn.execute("SELECT id, path, sha256 FROM documents"):
        existing[row["path"]] = {"id": row["id"], "sha256": row["sha256"]}

    stats = {"indexed": 0, "skipped": 0, "deleted": 0}

    for md_path in md_files:
        rel_path = md_path.name
        current_hash = _sha256(md_path)

        if rel_path in existing and existing[rel_path]["sha256"] == current_hash:
            # File unchanged — skip expensive embedding
            stats["skipped"] += 1
            continue

        logger.info("Indexing %s", rel_path)
        text = md_path.read_text(encoding="utf-8")
        chunks = _chunk_document(text)

        if not chunks:
            logger.warning("No chunks produced for %s", rel_path)
            continue

        # Embed all chunks for this document
        vectors = _embed_in_batches(chunks, embedder)

        # --- Upsert document row ---
        if rel_path in existing:
            doc_id = existing[rel_path]["id"]
            conn.execute(
                "UPDATE documents SET sha256 = ?, indexed_at = unixepoch('now') WHERE id = ?",
                (current_hash, doc_id),
            )
            # Delete old chunks so triggers clean up FTS and we reinsert fresh
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM vec_chunks WHERE rowid IN "
                         "(SELECT id FROM chunks WHERE document_id = ?)", (doc_id,))
        else:
            cursor = conn.execute(
                "INSERT INTO documents (path, sha256) VALUES (?, ?)",
                (rel_path, current_hash),
            )
            doc_id = cursor.lastrowid

        # --- Insert chunks + vectors ---
        for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            # Extract heading from first line if it starts with #
            heading = None
            first_line = chunk_text.strip().splitlines()[0] if chunk_text.strip() else ""
            if first_line.startswith("#"):
                heading = first_line.lstrip("#").strip()

            cursor = conn.execute(
                """
                INSERT INTO chunks (document_id, strategy, heading, content, chunk_index)
                VALUES (?, 'separators', ?, ?, ?)
                """,
                (doc_id, heading, chunk_text, idx),
            )
            chunk_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                (chunk_id, _pack_vector(vector)),
            )

        conn.commit()
        stats["indexed"] += 1

    # --- Prune deleted files ---
    disk_paths = {md.name for md in md_files}
    for stored_path, meta in existing.items():
        if stored_path not in disk_paths:
            conn.execute("DELETE FROM documents WHERE id = ?", (meta["id"],))
            logger.info("Pruned deleted document %s", stored_path)
            stats["deleted"] += 1

    if stats["deleted"]:
        conn.commit()

    conn.close()
    return stats


def get_index_stats() -> dict[str, int]:
    """
    Return lightweight statistics about the current index state.

    Returns:
        dict with keys "documents" and "chunks".
    """
    conn = get_connection()
    init_db(conn)
    docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    return {"documents": docs, "chunks": chunks}
