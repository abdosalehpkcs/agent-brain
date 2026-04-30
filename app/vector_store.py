"""Vector storage helpers for provider-agnostic embeddings.

Embeddings are stored in dimension-specific tables so different models can
coexist without destructive schema changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.sql import Identifier, SQL

from app.errors import VectorStoreError

ANN_INDEXED_DIMENSIONS: frozenset[int] = frozenset({768, 1536})


def get_embedding_table(dimensions: int) -> str:
    table_map = {
        768: "chunk_embeddings_768",
        1536: "chunk_embeddings_1536",
        3072: "chunk_embeddings_3072",
    }

    try:
        return table_map[dimensions]
    except KeyError as exc:
        raise VectorStoreError(
            f"Unsupported embedding dimensions: {dimensions}. "
            "Supported values are 768, 1536, and 3072."
        ) from exc


def is_ann_indexed_dimension(dimensions: int) -> bool:
    """Return True when *dimensions* has an ANN index (ivfflat); False for exact scan."""
    return dimensions in ANN_INDEXED_DIMENSIONS


@dataclass(frozen=True)
class SearchResult:
    chunk_id: UUID
    project_id: str
    document_id: UUID
    file_path: str
    chunk_index: int
    chunk_type: str | None
    content: str
    metadata: dict[str, Any]
    provider: str
    model: str
    distance: float


def upsert_embedding(
    conn: Connection,
    *,
    chunk_id: UUID,
    project_id: str,
    provider: str,
    model: str,
    embedding: list[float],
) -> None:
    if not embedding:
        raise VectorStoreError("Embedding vector cannot be empty")

    dimensions = len(embedding)
    table_name = get_embedding_table(dimensions)

    query = SQL(
        """
        INSERT INTO {table_name} (
            chunk_id,
            project_id,
            provider,
            model,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (chunk_id, provider, model)
        DO UPDATE SET
            embedding = EXCLUDED.embedding,
            created_at = NOW()
        """
    ).format(table_name=Identifier(table_name))

    with conn.cursor() as cur:
        cur.execute(
            query,
            (chunk_id, project_id, provider, model, embedding),
        )


def search_embeddings(
    conn: Connection,
    *,
    query_embedding: list[float],
    project_id: str,
    provider: str,
    model: str,
    limit: int = 10,
) -> list[SearchResult]:
    if not query_embedding:
        raise VectorStoreError("Query embedding cannot be empty")
    if limit <= 0:
        raise VectorStoreError("Search limit must be greater than zero")

    dimensions = len(query_embedding)
    table_name = get_embedding_table(dimensions)

    query = SQL(
        """
        SELECT
            c.id AS chunk_id,
            c.project_id,
            c.document_id,
            c.file_path,
            c.chunk_index,
            c.chunk_type,
            c.content,
            c.metadata,
            e.provider,
            e.model,
            (e.embedding <=> %s::vector) AS distance
        FROM {table_name} AS e
        INNER JOIN chunks AS c
            ON c.id = e.chunk_id
        WHERE e.project_id = %s
          AND e.provider = %s
          AND e.model = %s
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
        """
    ).format(table_name=Identifier(table_name))

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            query,
            (query_embedding, project_id, provider, model, query_embedding, limit),
        )
        rows = cur.fetchall()

    return [
        SearchResult(
            chunk_id=row["chunk_id"],
            project_id=row["project_id"],
            document_id=row["document_id"],
            file_path=row["file_path"],
            chunk_index=row["chunk_index"],
            chunk_type=row["chunk_type"],
            content=row["content"],
            metadata=row["metadata"],
            provider=row["provider"],
            model=row["model"],
            distance=row["distance"],
        )
        for row in rows
    ]