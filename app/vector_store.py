"""Vector storage helpers for provider-agnostic embeddings.

Embeddings are stored in dimension-specific tables so different models can
coexist without destructive schema changes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg import Connection, connect
from psycopg.rows import dict_row
from psycopg.sql import Identifier, SQL

from app.config import ALL_KNOWN_DIMENSIONS, DATABASE_URL, SUPPORTED_DIMENSIONS
from app.errors import VectorStoreError

ANN_INDEXED_DIMENSIONS: frozenset[int] = SUPPORTED_DIMENSIONS


def get_embedding_table(dimensions: int) -> str:
    table_map = {d: f"chunk_embeddings_{d}" for d in sorted(ALL_KNOWN_DIMENSIONS)}

    try:
        return table_map[dimensions]
    except KeyError as exc:
        raise VectorStoreError(
            f"Unsupported embedding dimensions: {dimensions}. "
            f"Supported: {', '.join(str(d) for d in sorted(SUPPORTED_DIMENSIONS))}."
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


# ---------------------------------------------------------------------------
# Embedding status helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmbeddingStatus:
    """Summary row returned by get_embedding_status."""

    project_id: str
    provider: str
    model: str
    dimensions: int
    indexed: bool
    chunk_count: int
    embedding_count: int
    missing_count: int


def get_embedding_status(
    conn: Connection,
    *,
    project_id: str,
) -> list[EmbeddingStatus]:
    """Return per-provider/model embedding coverage for *project_id*.

    Queries each dimension-specific table and compares the embedding count
    against the total chunk count for the project.
    """
    if not project_id.strip():
        raise VectorStoreError("project_id cannot be empty")

    # Total chunks for this project.
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM chunks WHERE project_id = %s",
            (project_id,),
        )
        total_chunks: int = (cur.fetchone() or {"cnt": 0})["cnt"]

    results: list[EmbeddingStatus] = []

    for dim in sorted(ALL_KNOWN_DIMENSIONS):
        table = get_embedding_table(dim)
        query = SQL(
            """
            SELECT provider, model, COUNT(*) AS cnt
            FROM {table}
            WHERE project_id = %s
            GROUP BY provider, model
            ORDER BY provider, model
            """
        ).format(table=Identifier(table))

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (project_id,))
            rows = cur.fetchall()

        for row in rows:
            emb_count = row["cnt"]
            results.append(
                EmbeddingStatus(
                    project_id=project_id,
                    provider=row["provider"],
                    model=row["model"],
                    dimensions=dim,
                    indexed=dim in ANN_INDEXED_DIMENSIONS,
                    chunk_count=total_chunks,
                    embedding_count=emb_count,
                    missing_count=max(0, total_chunks - emb_count),
                )
            )

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.vector_store",
        description="Vector store utilities",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status", help="Show embedding status for a project")
    status_parser.add_argument("--project-id", required=True, help="Project identifier")

    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.command == "status":
        with connect(DATABASE_URL) as conn:
            rows = get_embedding_status(conn, project_id=args.project_id)

        if not rows:
            print(f"No embeddings found for project '{args.project_id}'")
            return

        header = f"{'provider':<16} {'model':<28} {'dim':>5} {'indexed':<8} {'embeddings':>10} {'chunks':>8} {'missing':>8}"
        print(header)
        print("-" * len(header))
        for r in rows:
            indexed_label = "ANN" if r.indexed else "exact"
            print(
                f"{r.provider:<16} {r.model:<28} {r.dimensions:>5} {indexed_label:<8} "
                f"{r.embedding_count:>10} {r.chunk_count:>8} {r.missing_count:>8}"
            )


if __name__ == "__main__":
    main()