"""
SQLite schema initialisation for module_02_02 Hybrid RAG.

Tables
------
documents
    Primary document registry keyed by file path.  SHA-256 hash allows the
    indexer to skip re-indexing unchanged files.

chunks
    Individual text chunks linked to a document.  Stores the raw content
    and the strategy used to produce it.

chunks_fts  (FTS5 virtual table)
    Full-text search index mirroring the `content` column of `chunks`.

vec_chunks  (sqlite-vec vec0 virtual table)
    1536-dimensional float32 vector store for semantic search.
    One row per chunk with the same rowid as `chunks`.

Usage
-----
    from module_02_02.db import get_connection, init_db
    conn = get_connection()
    init_db(conn)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from django.conf import settings


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Open (or create) the module_02_02 SQLite database with sqlite-vec loaded.

    The database lives at <MEDIA_ROOT>/module_02_02/hybrid_rag.db.
    The directory is created if it does not exist.

    Returns:
        sqlite3.Connection: A connection with sqlite-vec extension enabled,
                            row_factory set to sqlite3.Row for dict-like access,
                            and WAL journal mode for concurrent readers.
    """
    db_dir: Path = Path(settings.MEDIA_ROOT) / "module_02_02"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "hybrid_rag.db"

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Load sqlite-vec extension — required before any vec0 DDL or queries
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    # WAL mode improves concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")

    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

# Embedding dimensionality used by text-embedding-3-small
VECTOR_DIM = 1536


def init_db(conn: sqlite3.Connection) -> None:
    """
    Ensure all tables and indexes exist in the given connection.

    This is idempotent — safe to call on every app startup.

    Args:
        conn: An open SQLite connection with sqlite-vec loaded.
    """
    cursor = conn.cursor()

    # --- documents table ---
    # Tracks source files; sha256 prevents redundant re-indexing.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            path      TEXT    NOT NULL UNIQUE,
            sha256    TEXT    NOT NULL,
            indexed_at REAL   NOT NULL DEFAULT (unixepoch('now'))
        )
    """)

    # --- chunks table ---
    # Each row is one text chunk produced by a particular strategy.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            strategy    TEXT    NOT NULL DEFAULT 'separators',
            heading     TEXT,
            content     TEXT    NOT NULL,
            chunk_index INTEGER NOT NULL DEFAULT 0
        )
    """)

    # --- FTS5 virtual table ---
    # content='' means FTS5 stores its own copy of the text; triggers keep it
    # in sync with the `chunks` table.
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
        USING fts5(content, content='chunks', content_rowid='id')
    """)

    # Triggers to keep FTS5 in sync with `chunks`
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content)
                VALUES ('delete', old.id, old.content);
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END
    """)

    # --- sqlite-vec virtual table ---
    # vec0 stores float32 vectors of VECTOR_DIM dimensions.
    cursor.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks
        USING vec0(embedding float[{VECTOR_DIM}])
    """)

    conn.commit()
