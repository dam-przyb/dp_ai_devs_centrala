"""
Service layer for module_02_02.

Three main entry points:

1. run_chunking_demo(path) → ChunkingResult
   Runs all four chunking strategies on a markdown file and returns
   structured Chunk objects plus token usage.

2. embed_texts(phrases) → SimilarityMatrix
   Embeds a list of short phrases and returns the pairwise cosine
   similarity matrix.

3. run_hybrid_rag(query, history) → HybridAnswer
   Runs the LangGraph hybrid RAG agent loop with the search tool.

History serialisation helpers (serialise_history / deserialise_history)
allow conversation state to be stored in Django sessions.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from django.conf import settings
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from module_02_02.graphs import build_hybrid_rag_graph
from module_02_02.prompts import (
    CONTEXT_ENRICHMENT_PROMPT,
    TOPIC_CHUNKING_PROMPT,
    HYBRID_RAG_SYSTEM_PROMPT,
)
from module_02_02.schemas import (
    Chunk,
    ChunkMetadata,
    ChunkingResult,
    EmbeddingEntry,
    HybridAnswer,
    SearchResult,
    SimilarityMatrix,
)
from module_02_02.search import hybrid_search

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    """
    Build a ChatOpenAI instance via the OpenRouter gateway.

    Uses RAG_02_02_MODEL from settings (falls back to gpt-4o-mini).
    """
    return ChatOpenAI(
        model=getattr(settings, "RAG_02_02_MODEL", "openai/gpt-4o-mini"),
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
        temperature=0,
    )


def _get_embedder() -> OpenAIEmbeddings:
    """Build an OpenAIEmbeddings instance for text-embedding-3-small."""
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
    )


def _workspace_dir() -> Path:
    """Return the workspace directory, creating it if needed."""
    ws = Path(settings.MEDIA_ROOT) / "module_02_02" / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

# --- Characters strategy ---

def _chunk_characters(text: str) -> list[Chunk]:
    """
    Split text into fixed-size character chunks with overlap.

    Parameters match spec acceptance criteria:
        size=1000, overlap=200.

    Args:
        text: Full document text.

    Returns:
        List of Chunk objects with strategy='characters'.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""],
    )
    parts = splitter.split_text(text)
    return [
        Chunk(
            content=p,
            metadata=ChunkMetadata(strategy="characters", index=i),
        )
        for i, p in enumerate(parts)
    ]


# --- Separators strategy ---

_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", " "]


def _extract_heading(text: str) -> str | None:
    """Extract the first markdown heading from a chunk, if present."""
    for line in text.splitlines():
        stripped = line.lstrip("#").strip()
        if line.startswith("#") and stripped:
            return stripped
    return None


def _chunk_separators(text: str) -> list[Chunk]:
    """
    Recursive separator-based chunking with heading metadata.

    Splits on markdown headings first, falling back to paragraphs, lines,
    sentences, and finally words.  Stores the first heading found in
    each chunk as metadata.

    Args:
        text: Full document text.

    Returns:
        List of Chunk objects with strategy='separators'.
    """
    splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS,
        chunk_size=1000,
        chunk_overlap=200,
        keep_separator=True,
    )
    parts = splitter.split_text(text)
    return [
        Chunk(
            content=p,
            metadata=ChunkMetadata(
                strategy="separators",
                index=i,
                heading=_extract_heading(p),
            ),
        )
        for i, p in enumerate(parts)
    ]


# --- Context-enriched strategy ---

def _chunk_context_enriched(text: str, llm: ChatOpenAI) -> tuple[list[Chunk], int, int]:
    """
    Context-enriched chunking: separator split + one LLM call per chunk.

    Each chunk receives a 1-2 sentence context sentence situating it within
    the document.  Token usage is accumulated and returned.

    Args:
        text: Full document text.
        llm:  Configured ChatOpenAI instance.

    Returns:
        Tuple of (chunks, total_prompt_tokens, total_completion_tokens).
    """
    base_chunks = _chunk_separators(text)
    prompt_tokens = 0
    completion_tokens = 0
    enriched: list[Chunk] = []

    for chunk in base_chunks:
        try:
            response = llm.invoke([
                {"role": "system", "content": CONTEXT_ENRICHMENT_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Document excerpt:\n\n{text[:3000]}\n\n"
                        f"Chunk to contextualise:\n\n{chunk.content}"
                    ),
                },
            ])
            context_text = response.content.strip()
            usage = response.usage_metadata or {}
            prompt_tokens += usage.get("input_tokens", 0)
            completion_tokens += usage.get("output_tokens", 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Context enrichment LLM call failed: %s", exc)
            context_text = ""

        enriched.append(
            Chunk(
                content=chunk.content,
                metadata=ChunkMetadata(
                    strategy="context",
                    index=chunk.metadata.index,
                    heading=chunk.metadata.heading,
                    context=context_text,
                ),
            )
        )

    return enriched, prompt_tokens, completion_tokens


# --- Topic-based strategy ---

def _chunk_topics(text: str, llm: ChatOpenAI) -> tuple[list[Chunk], int, int]:
    """
    Topic-based chunking via a single LLM call returning JSON.

    The LLM is asked to break the document into {topic, content} objects.
    Original text is preserved — no summarisation.

    Args:
        text: Full document text.
        llm:  Configured ChatOpenAI instance.

    Returns:
        Tuple of (chunks, prompt_tokens, completion_tokens).
    """
    try:
        response = llm.invoke([
            {"role": "system", "content": TOPIC_CHUNKING_PROMPT},
            {"role": "user", "content": text},
        ])
        raw = response.content.strip()
        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        topic_objs = json.loads(raw)
        usage = response.usage_metadata or {}
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Topic chunking LLM call failed: %s", exc)
        # Graceful fallback: treat entire document as one chunk
        return (
            [Chunk(content=text, metadata=ChunkMetadata(strategy="topics", index=0))],
            0,
            0,
        )

    chunks = [
        Chunk(
            content=obj.get("content", ""),
            metadata=ChunkMetadata(
                strategy="topics",
                index=i,
                topic=obj.get("topic", ""),
            ),
        )
        for i, obj in enumerate(topic_objs)
        if isinstance(obj, dict) and obj.get("content")
    ]

    return chunks, prompt_tokens, completion_tokens


# =============================================================================
# Public service 1: run_chunking_demo
# =============================================================================

def run_chunking_demo(rel_path: str) -> ChunkingResult:
    """
    Run all four chunking strategies on a markdown file in the workspace.

    Strategies:
        - characters:  Fixed-size 1000/200 overlap splits.
        - separators:  Recursive heading/paragraph splits with heading metadata.
        - context:     Separator splits enriched with per-chunk LLM context.
        - topics:      Single LLM call returns JSON array of {topic, content}.

    Results are written to JSONL files in the workspace directory:
        workspace/example-characters.jsonl
        workspace/example-separators.jsonl
        workspace/example-context.jsonl
        workspace/example-topics.jsonl

    Args:
        rel_path: Filename relative to the workspace directory (e.g. 'example.md').

    Returns:
        ChunkingResult with per-strategy chunk lists and LLM token totals.

    Raises:
        FileNotFoundError: If the target file does not exist.
    """
    ws = _workspace_dir()
    full_path = ws / rel_path

    if not full_path.exists():
        raise FileNotFoundError(f"Workspace file not found: {rel_path}")

    text = full_path.read_text(encoding="utf-8")
    llm = _get_llm()

    # Run all four strategies
    chars_chunks = _chunk_characters(text)
    sep_chunks = _chunk_separators(text)
    ctx_chunks, pt_ctx, ct_ctx = _chunk_context_enriched(text, llm)
    topic_chunks, pt_topic, ct_topic = _chunk_topics(text, llm)

    result = ChunkingResult(
        source_path=rel_path,
        strategies={
            "characters": chars_chunks,
            "separators": sep_chunks,
            "context": ctx_chunks,
            "topics": topic_chunks,
        },
        llm_prompt_tokens=pt_ctx + pt_topic,
        llm_completion_tokens=ct_ctx + ct_topic,
    )

    # Persist JSONL output for each strategy
    stem = Path(rel_path).stem
    for strategy_name, chunks in result.strategies.items():
        out_path = ws / f"{stem}-{strategy_name}.jsonl"
        lines = [
            json.dumps(
                {"content": c.content, **c.metadata.model_dump(exclude_none=True)},
                ensure_ascii=False,
            )
            for c in chunks
        ]
        out_path.write_text("\n".join(lines), encoding="utf-8")

    return result


# =============================================================================
# Public service 2: embed_texts
# =============================================================================

def embed_texts(phrases: list[str]) -> SimilarityMatrix:
    """
    Embed a list of phrases and compute their pairwise cosine similarity matrix.

    Uses text-embedding-3-small via the OpenRouter gateway.

    Similarity thresholds (spec):
        >= 0.60 → green
        >= 0.35 → yellow
        < 0.35  → red

    Args:
        phrases: List of short text strings to embed (1 ≤ len ≤ 20).

    Returns:
        SimilarityMatrix with texts and row-major 2-D similarity scores.

    Raises:
        ValueError: If phrases list is empty.
    """
    if not phrases:
        raise ValueError("At least one phrase is required.")

    embedder = _get_embedder()
    raw_vectors = embedder.embed_documents(phrases)

    # Normalise each vector for cosine similarity via dot product
    def _norm(v: list[float]) -> list[float]:
        magnitude = math.sqrt(sum(x * x for x in v))
        if magnitude == 0:
            return v
        return [x / magnitude for x in v]

    normed = [_norm(v) for v in raw_vectors]

    # Build pairwise cosine similarity matrix (dot product of normed vectors)
    n = len(normed)
    matrix: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            dot = sum(normed[i][k] * normed[j][k] for k in range(len(normed[i])))
            # Clamp to [-1, 1] to handle floating-point imprecision
            row.append(round(max(-1.0, min(1.0, dot)), 4))
        matrix.append(row)

    return SimilarityMatrix(texts=phrases, matrix=matrix)


# =============================================================================
# Hybrid RAG agent — LangGraph tool + runner
# =============================================================================

@tool
def search(keywords: str, semantic: str) -> str:
    """
    Hybrid search combining BM25 full-text search and semantic vector similarity.

    Both inputs are required:
    - keywords:  space-separated keywords for BM25/FTS search
    - semantic:  natural language description of what you are looking for

    Returns a JSON string with the top matching chunks.
    """
    results, vector_available = hybrid_search(keywords=keywords, semantic=semantic, top_k=8)
    output = {
        "vector_available": vector_available,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "doc": r.doc_path,
                "rrf_score": round(r.rrf_score, 4),
                "content": r.content[:1200],  # cap per chunk to manage context size
            }
            for r in results
        ],
    }
    return json.dumps(output, ensure_ascii=False)


# Lazy singleton for the compiled RAG graph
_rag_graph: Any | None = None


def _get_rag_graph() -> Any:
    """
    Return (and cache) the compiled LangGraph for Hybrid RAG.

    Built lazily on first call to avoid importing heavy modules at Django startup.
    """
    global _rag_graph  # noqa: PLW0603
    if _rag_graph is None:
        llm = _get_llm()
        _rag_graph = build_hybrid_rag_graph(
            tools=[search],
            llm=llm,
            system_prompt=HYBRID_RAG_SYSTEM_PROMPT,
        )
    return _rag_graph


def run_hybrid_rag(query: str, history: list[AnyMessage]) -> HybridAnswer:
    """
    Execute the Hybrid RAG agent for a single user query.

    The agent loop:
    1. Appends the new user message to the conversation history.
    2. Invokes the LangGraph, which may call the search tool multiple times.
    3. Extracts the final AI text response and unique source documents.

    Args:
        query:   The user's natural language question.
        history: Previous conversation messages (may be empty for first turn).

    Returns:
        HybridAnswer with the agent's reply, cited sources, search call count,
        and a flag indicating whether vector search was operational.
    """
    graph = _get_rag_graph()

    messages = list(history) + [HumanMessage(content=query)]
    result = graph.invoke({"messages": messages, "step": 0})

    final_messages: list[AnyMessage] = result["messages"]

    # Extract the last AI message as the answer
    answer_text = ""
    for msg in reversed(final_messages):
        if isinstance(msg, AIMessage) and msg.content:
            answer_text = msg.content
            break

    # Count search tool calls and extract unique source documents
    sources: set[str] = set()
    search_calls = 0
    vector_available = True

    for msg in final_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "search":
                    search_calls += 1

        if isinstance(msg, ToolMessage):
            try:
                payload = json.loads(msg.content)
                if not payload.get("vector_available", True):
                    vector_available = False
                for r in payload.get("results", []):
                    if r.get("doc"):
                        sources.add(r["doc"])
            except (json.JSONDecodeError, AttributeError):
                pass

    return HybridAnswer(
        answer=answer_text,
        sources=sorted(sources),
        search_calls=search_calls,
        vector_available=vector_available,
    )


# =============================================================================
# History serialisation for Django session storage
# =============================================================================

def serialise_history(messages: list[AnyMessage]) -> list[dict[str, Any]]:
    """
    Convert a list of LangChain messages to JSON-serialisable dicts.

    Stored format: {"type": "human"|"ai"|"tool"|"system", "content": str,
                    "tool_calls": [...], "tool_call_id": str}

    Args:
        messages: LangChain message objects.

    Returns:
        List of plain dicts suitable for json.dumps / Django session storage.
    """
    serialised = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            serialised.append({"type": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            serialised.append({
                "type": "ai",
                "content": msg.content,
                "tool_calls": msg.tool_calls or [],
            })
        elif isinstance(msg, ToolMessage):
            serialised.append({
                "type": "tool",
                "content": msg.content,
                "tool_call_id": msg.tool_call_id,
            })
        elif isinstance(msg, SystemMessage):
            serialised.append({"type": "system", "content": msg.content})
    return serialised


def deserialise_history(data: list[dict[str, Any]]) -> list[AnyMessage]:
    """
    Reconstruct LangChain message objects from session-stored dicts.

    Args:
        data: List of dicts as written by serialise_history.

    Returns:
        List of LangChain AnyMessage objects.
    """
    messages: list[AnyMessage] = []
    for item in data:
        msg_type = item.get("type", "")
        content = item.get("content", "")
        if msg_type == "human":
            messages.append(HumanMessage(content=content))
        elif msg_type == "ai":
            messages.append(AIMessage(
                content=content,
                tool_calls=item.get("tool_calls", []),
            ))
        elif msg_type == "tool":
            messages.append(ToolMessage(
                content=content,
                tool_call_id=item.get("tool_call_id", ""),
            ))
        elif msg_type == "system":
            messages.append(SystemMessage(content=content))
    return messages
