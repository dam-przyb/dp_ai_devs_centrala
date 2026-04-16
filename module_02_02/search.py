"""
Hybrid search implementation for module_02_02.

Provides three functions:
- fts_search(query, top_k)       — SQLite FTS5 full-text search
- vector_search(query, top_k)    — sqlite-vec cosine similarity search
- hybrid_search(keywords, semantic, top_k) — RRF fusion of both

Reciprocal Rank Fusion (RRF) formula:
    score(d) = Σ  1 / (k + rank(d))
where k = 60 (spec requirement) and rank is 1-based.

Vector search degrades gracefully to an empty list if the vec_chunks table
is empty or an error occurs.
"""

from __future__ import annotations

import logging
import struct
from typing import Any

from langchain_openai import OpenAIEmbeddings
from django.conf import settings

from module_02_02.db import get_connection, init_db, VECTOR_DIM
from module_02_02.schemas import SearchResult

logger = logging.getLogger(__name__)

# RRF k constant per spec
_RRF_K = 60


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pack_vector(embedding: list[float]) -> bytes:
    """Serialise a float list to little-endian binary for sqlite-vec queries."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def _get_embedder() -> OpenAIEmbeddings:
    """Build embedder pointing at the OpenRouter gateway."""
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
    )


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert sqlite3.Row to plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# Individual search methods
# ---------------------------------------------------------------------------

def fts_search(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """
    Perform an FTS5 full-text search over indexed chunks.

    Returns a list of dicts with keys: chunk_id, doc_path, content, fts_rank.
    Results are ordered by relevance (bm25 score, lower magnitude = better).

    Args:
        query:  Full-text query string.
        top_k:  Maximum number of results to return.

    Returns:
        List of result dicts sorted by FTS rank (best first).
    """
    conn = get_connection()
    init_db(conn)

    try:
        rows = conn.execute(
            """
            SELECT
                c.id      AS chunk_id,
                d.path    AS doc_path,
                c.content AS content,
                rank      AS fts_score
            FROM chunks_fts
            JOIN chunks   c ON chunks_fts.rowid = c.id
            JOIN documents d ON c.document_id = d.id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, top_k),
        ).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("FTS search failed: %s", exc)
        return []
    finally:
        conn.close()

    return [_row_to_dict(r) for r in rows]


def vector_search(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """
    Perform a semantic vector search over indexed chunks.

    Embeds the query with text-embedding-3-small, then queries sqlite-vec
    using Euclidean (L2) distance which correlates with cosine similarity
    for normalised vectors.

    Returns a list of dicts with keys: chunk_id, doc_path, content, distance.
    Degrades gracefully to empty list on any failure.

    Args:
        query:  Natural language query.
        top_k:  Maximum number of results to return.

    Returns:
        List of result dicts sorted by vector similarity (closest first).
    """
    try:
        embedder = _get_embedder()
        query_vec = embedder.embed_query(query)
        query_bytes = _pack_vector(query_vec)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding query failed (vector search disabled): %s", exc)
        return []

    conn = get_connection()
    init_db(conn)

    try:
        rows = conn.execute(
            """
            SELECT
                c.id       AS chunk_id,
                d.path     AS doc_path,
                c.content  AS content,
                v.distance AS distance
            FROM vec_chunks v
            JOIN chunks    c ON v.rowid = c.id
            JOIN documents d ON c.document_id = d.id
            WHERE v.embedding MATCH ?
              AND k = ?
            ORDER BY distance
            """,
            (query_bytes, top_k),
        ).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vector search query failed: %s", exc)
        return []
    finally:
        conn.close()

    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

def hybrid_search(
    keywords: str,
    semantic: str,
    top_k: int = 10,
) -> tuple[list[SearchResult], bool]:
    """
    Fuse FTS and vector results using Reciprocal Rank Fusion (RRF, k=60).

    Both `keywords` and `semantic` inputs are required by the spec's search
    tool contract. The function degrades gracefully when vector search fails —
    in that case it returns FTS-only results and sets vector_available=False.

    Algorithm:
    1. Run fts_search(keywords) → ranked list F
    2. Run vector_search(semantic) → ranked list V
    3. For each unique chunk across F and V:
           rrf_score = Σ  1 / (60 + rank)
    4. Sort by rrf_score descending, return top_k.

    Args:
        keywords:  Keyword query for FTS BM25 search.
        semantic:  Natural language query for vector search.
        top_k:     Number of fused results to return.

    Returns:
        Tuple of (results, vector_available) where vector_available indicates
        whether the vector search component contributed results.
    """
    fts_results = fts_search(keywords, top_k=top_k * 2)
    vector_results = vector_search(semantic, top_k=top_k * 2)

    vector_available = len(vector_results) > 0

    # Build per-chunk RRF score accumulator
    # Key: chunk_id  →  {"score": float, "doc_path": str, "content": str}
    scores: dict[int, dict[str, Any]] = {}

    for rank_0, row in enumerate(fts_results):
        cid = row["chunk_id"]
        rrf = 1.0 / (_RRF_K + rank_0 + 1)
        if cid not in scores:
            scores[cid] = {
                "doc_path": row["doc_path"],
                "content": row["content"],
                "rrf_score": 0.0,
                "fts_rank": None,
                "vector_rank": None,
            }
        scores[cid]["rrf_score"] += rrf
        scores[cid]["fts_rank"] = rank_0 + 1

    for rank_0, row in enumerate(vector_results):
        cid = row["chunk_id"]
        rrf = 1.0 / (_RRF_K + rank_0 + 1)
        if cid not in scores:
            scores[cid] = {
                "doc_path": row["doc_path"],
                "content": row["content"],
                "rrf_score": 0.0,
                "fts_rank": None,
                "vector_rank": None,
            }
        scores[cid]["rrf_score"] += rrf
        scores[cid]["vector_rank"] = rank_0 + 1

    sorted_chunks = sorted(scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)

    results = [
        SearchResult(
            chunk_id=cid,
            doc_path=meta["doc_path"],
            content=meta["content"],
            rrf_score=meta["rrf_score"],
            fts_rank=meta["fts_rank"],
            vector_rank=meta["vector_rank"],
        )
        for cid, meta in sorted_chunks[:top_k]
    ]

    return results, vector_available
