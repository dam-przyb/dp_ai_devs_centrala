"""
Pydantic data contracts for module_02_02.

Covers all three sections:
- Chunking: Chunk, ChunkMetadata, ChunkingResult
- Embeddings: EmbeddingEntry, SimilarityMatrix
- Hybrid RAG: SearchResult, HybridAnswer
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# =============================================================================
# Chunking schemas
# =============================================================================


class ChunkMetadata(BaseModel):
    """Metadata attached to every chunk regardless of strategy."""

    # Strategy that produced this chunk
    strategy: str
    # Zero-based chunk index within the document
    index: int
    # Optional heading derived from separator/section detection
    heading: str | None = None
    # Context sentence added by the LLM (context-enriched strategy only)
    context: str | None = None
    # Topic label assigned by the LLM (topic-based strategy only)
    topic: str | None = None


class Chunk(BaseModel):
    """A single document chunk with its content and metadata."""

    content: str
    metadata: ChunkMetadata


class ChunkingResult(BaseModel):
    """Aggregated output from running all four chunking strategies."""

    # Source file path (relative to workspace)
    source_path: str
    # Results keyed by strategy name: "characters", "separators", "context", "topics"
    strategies: dict[str, list[Chunk]] = Field(default_factory=dict)
    # Token usage totals from LLM-based strategies (may be 0 for deterministic ones)
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0


# =============================================================================
# Embedding schemas
# =============================================================================


class EmbeddingEntry(BaseModel):
    """A single text together with its embedding vector."""

    text: str
    embedding: list[float]


class SimilarityMatrix(BaseModel):
    """Pairwise cosine similarity matrix for a list of texts."""

    texts: list[str]
    # Row-major 2-D matrix (list of rows, each row is a list of similarity scores)
    matrix: list[list[float]]


# =============================================================================
# Hybrid RAG schemas
# =============================================================================


class SearchResult(BaseModel):
    """A single retrieval result from the hybrid search pipeline."""

    chunk_id: int
    doc_path: str
    content: str
    # Normalised RRF score (higher is better)
    rrf_score: float
    # Individual ranks — None if the method did not return this result
    fts_rank: int | None = None
    vector_rank: int | None = None


class HybridAnswer(BaseModel):
    """The final answer produced by the hybrid RAG agent."""

    answer: str
    sources: list[str] = Field(default_factory=list)
    # Total search calls made during the agent loop
    search_calls: int = 0
    # Whether vector search was available (may degrade to FTS-only)
    vector_available: bool = True
