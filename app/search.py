"""Search helpers that enforce provider/model scoped retrieval."""

from __future__ import annotations

import argparse

from psycopg import Connection, connect

from app.config import DATABASE_URL, EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, EMBEDDING_PROVIDER
from app.decisions import DecisionRecord, list_project_decisions
from app.embeddings import get_embedding
from app.vector_store import SearchResult, search_embeddings


def search_project_chunks(
    conn: Connection,
    *,
    project_id: str,
    query_text: str,
    limit: int = 10,
) -> list[SearchResult]:
    embedding = get_embedding(query_text)

    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            "Configured EMBEDDING_DIMENSIONS does not match runtime embedding output: "
            f"expected {EMBEDDING_DIMENSIONS}, got {len(embedding)}"
        )

    return search_embeddings(
        conn,
        query_embedding=embedding,
        project_id=project_id,
        provider=EMBEDDING_PROVIDER,
        model=EMBEDDING_MODEL,
        limit=limit,
    )


def search_project_memory(
    conn: Connection,
    *,
    project_id: str,
    query_text: str,
    limit: int = 10,
    include_decisions: bool = False,
) -> tuple[list[SearchResult], list[DecisionRecord]]:
    chunks = search_project_chunks(
        conn,
        project_id=project_id,
        query_text=query_text,
        limit=limit,
    )

    decisions: list[DecisionRecord] = []
    if include_decisions:
        decisions = list_project_decisions(
            conn,
            project_id=project_id,
            status="active",
            limit=20,
        )

    return chunks, decisions


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Semantic project search")
    parser.add_argument("project_id", help="Project identifier")
    parser.add_argument("query", help="Search query text")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--include-decisions",
        action="store_true",
        help="Include active decision memory entries for the project",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    with connect(DATABASE_URL) as conn:
        chunks, decisions = search_project_memory(
            conn,
            project_id=args.project_id,
            query_text=args.query,
            limit=args.limit,
            include_decisions=args.include_decisions,
        )

    if not chunks:
        print("No matching chunks found")
    else:
        for chunk in chunks:
            print(
                f"chunk={chunk.chunk_id} distance={chunk.distance:.6f} "
                f"file={chunk.file_path} index={chunk.chunk_index}"
            )

    if args.include_decisions:
        if not decisions:
            print("No active decisions found")
        else:
            print("Active decisions:")
            for decision in decisions:
                print(f"- {decision.id} | {decision.title} | {decision.status or 'unknown'}")


if __name__ == "__main__":
    main()