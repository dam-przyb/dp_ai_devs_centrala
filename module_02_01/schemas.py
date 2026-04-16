"""
schemas.py — Pydantic data contracts for the Agentic RAG module (02_01).

These models define the boundary between the LangGraph service layer and the
Django views / templates. Using Pydantic v2 ensures all agent outputs are
validated and safe to pass to templates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileListing(BaseModel):
    """
    Result of a directory listing tool call.

    Attributes:
        path: The directory path listed, relative to the document root.
        entries: Sorted entry names; directories carry a trailing '/'.
    """

    path: str
    entries: list[str]


class SearchMatch(BaseModel):
    """
    Single line that matched the search query inside the document corpus.

    Attributes:
        file: Relative path from the document root.
        line_number: 1-based line number of the match.
        line_content: The matching line text (stripped).
    """

    file: str
    line_number: int
    line_content: str


class SearchResult(BaseModel):
    """
    Aggregated result of a corpus-wide text search.

    Attributes:
        query: The search term used.
        matches: Up to 50 matching lines.
        total: Total match count before the cap.
    """

    query: str
    matches: list[SearchMatch]
    total: int


class Source(BaseModel):
    """
    A file fragment consulted by the agent during its reasoning loop.

    Attributes:
        file: Relative path from the document root.
        start_line: First line read (1-based), or None for a whole-file read.
        end_line: Last line read (inclusive, 1-based), or None.
    """

    file: str
    start_line: int | None = None
    end_line: int | None = None


class AgentReply(BaseModel):
    """
    Final output returned from a single agentic RAG run.

    Attributes:
        answer: The synthesised English answer.
        sources: Files (and optional line ranges) the agent actually read.
        steps_taken: Number of LLM calls made (= steps, not tool calls).
        error: Non-None when the run hit max_steps or a fatal error occurred.
    """

    answer: str
    sources: list[Source] = Field(default_factory=list)
    steps_taken: int = 0
    error: str | None = None
