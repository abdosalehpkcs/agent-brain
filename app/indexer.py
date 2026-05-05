"""Indexing helpers that store content once and embeddings by model dimension.

Re-index behaviour:
- Chunks are identified by (document_id, chunk_index).
- Documents are identified by (project_id, path) with a content_hash.
- Unchanged documents (same content_hash) are skipped entirely.
- Changed documents delete old chunks/embeddings and re-create.
- Embeddings are scoped to (chunk_id, provider, model); switching provider
  adds new embeddings without touching existing ones.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from psycopg import Connection, connect
from psycopg.rows import dict_row
from psycopg.sql import Identifier, SQL
from psycopg.types.json import Json

from app.config import (
    ALL_KNOWN_DIMENSIONS,
    DATABASE_URL,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
)
from app.embeddings import get_embedding
from app.errors import EmbeddingProviderError
from app.vector_store import get_embedding_table, upsert_embedding


@dataclass(frozen=True)
class ProjectConfig:
    id: str
    name: str
    type: str
    root_path: Path
    include: list[str]
    exclude: list[str]
    description: str | None


def upsert_chunk(
    conn: Connection,
    *,
    project_id: str,
    document_id: UUID,
    file_path: str,
    chunk_index: int,
    chunk_type: str | None,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    if not content.strip():
        raise ValueError("Chunk content cannot be empty")

    payload = metadata or {}

    query = """
        INSERT INTO chunks (
            project_id,
            document_id,
            file_path,
            chunk_index,
            chunk_type,
            content,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (document_id, chunk_index)
        DO UPDATE SET
            file_path = EXCLUDED.file_path,
            chunk_type = EXCLUDED.chunk_type,
            content = EXCLUDED.content,
            metadata = EXCLUDED.metadata
        RETURNING id
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            query,
            (
                project_id,
                document_id,
                file_path,
                chunk_index,
                chunk_type,
                content,
                Json(payload),
            ),
        )
        row = cur.fetchone()

    if not row:
        raise RuntimeError("Failed to upsert chunk")

    return row["id"]


def index_chunk(
    conn: Connection,
    *,
    project_id: str,
    document_id: UUID,
    file_path: str,
    chunk_index: int,
    chunk_type: str | None,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    chunk_id = upsert_chunk(
        conn,
        project_id=project_id,
        document_id=document_id,
        file_path=file_path,
        chunk_index=chunk_index,
        chunk_type=chunk_type,
        content=content,
        metadata=metadata,
    )

    # Check whether an embedding already exists for this (chunk, provider, model).
    table = get_embedding_table(EMBEDDING_DIMENSIONS)
    exists_query = SQL(
        """
        SELECT 1 FROM {table}
        WHERE chunk_id = %s AND provider = %s AND model = %s
        LIMIT 1
        """
    ).format(table=Identifier(table))
    with conn.cursor() as cur:
        cur.execute(exists_query, (chunk_id, EMBEDDING_PROVIDER, EMBEDDING_MODEL))
        if cur.fetchone() is not None:
            return chunk_id  # Already embedded for current provider/model.

    embedding = get_embedding(content)
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise EmbeddingProviderError(
            "Embedding dimension mismatch between provider output and configuration: "
            f"expected {EMBEDDING_DIMENSIONS}, got {len(embedding)}"
        )

    upsert_embedding(
        conn,
        chunk_id=chunk_id,
        project_id=project_id,
        provider=EMBEDDING_PROVIDER,
        model=EMBEDDING_MODEL,
        embedding=embedding,
    )

    return chunk_id


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project indexer")
    parser.add_argument("project_config", help="Path to project YAML file")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1200,
        help="Max characters per chunk (default: 1200)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Characters of overlap between chunks (default: 150)",
    )
    return parser


def _load_project_config(config_path: Path) -> ProjectConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"Project config not found: {config_path}")

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Project config must be a YAML object")

    project_id = str(payload.get("id", "")).strip()
    name = str(payload.get("name", "")).strip()
    project_type = str(payload.get("type", "")).strip()
    root_path_raw = str(payload.get("root_path", "")).strip()
    include = payload.get("include") or []
    exclude = payload.get("exclude") or []
    description = payload.get("description")

    if not project_id:
        raise ValueError("Project config is missing required field: id")
    if not name:
        raise ValueError("Project config is missing required field: name")
    if project_type not in {"coding", "research"}:
        raise ValueError("Project config type must be one of: coding, research")
    if not root_path_raw:
        raise ValueError("Project config is missing required field: root_path")
    if not isinstance(include, list) or not include:
        raise ValueError("Project config include must be a non-empty list of glob patterns")
    if not isinstance(exclude, list):
        raise ValueError("Project config exclude must be a list of glob patterns")

    # Resolve root_path relative to the config file's directory if it's a relative path
    root_path = Path(root_path_raw).expanduser()
    if not root_path.is_absolute():
        root_path = (config_path.parent / root_path).resolve()
    else:
        root_path = root_path.resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"root_path does not exist or is not a directory: {root_path}")

    include_patterns = [str(pattern).strip() for pattern in include if str(pattern).strip()]
    exclude_patterns = [str(pattern).strip() for pattern in exclude if str(pattern).strip()]
    if not include_patterns:
        raise ValueError("Project config include must contain at least one non-empty pattern")

    return ProjectConfig(
        id=project_id,
        name=name,
        type=project_type,
        root_path=root_path,
        include=include_patterns,
        exclude=exclude_patterns,
        description=(str(description).strip() if description else None),
    )


def _discover_files(config: ProjectConfig) -> list[Path]:
    selected: set[Path] = set()
    for pattern in config.include:
        for path in config.root_path.glob(pattern):
            if path.is_file():
                selected.add(path.resolve())

    excluded: set[Path] = set()
    for pattern in config.exclude:
        for path in config.root_path.glob(pattern):
            if path.is_file():
                excluded.add(path.resolve())

    files = sorted(path for path in selected if path not in excluded)
    return files


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    step = chunk_size - chunk_overlap
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized):
            break
        start += step

    return chunks


def _upsert_project(conn: Connection, config: ProjectConfig) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (id, name, type, root_path, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id)
            DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                root_path = EXCLUDED.root_path,
                description = EXCLUDED.description
            """,
            (
                config.id,
                config.name,
                config.type,
                str(config.root_path),
                config.description,
            ),
        )


def _reindex_project(
    conn: Connection,
    *,
    config: ProjectConfig,
    files: list[Path],
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[int, int, int]:
    """Index *files* into the project, skipping unchanged documents.

    Returns (documents_processed, chunks_indexed, documents_skipped).
    """
    # Build a map of existing documents by relative path -> (id, content_hash).
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, path, content_hash FROM documents WHERE project_id = %s",
            (config.id,),
        )
        existing: dict[str, dict[str, Any]] = {
            row["path"]: {"id": row["id"], "content_hash": row["content_hash"]}
            for row in cur.fetchall()
        }

    indexed_documents = 0
    indexed_chunks = 0
    skipped_documents = 0

    for file_path in files:
        raw_content = file_path.read_text(encoding="utf-8", errors="ignore")
        content_hash = hashlib.sha256(raw_content.encode("utf-8", errors="ignore")).hexdigest()
        relative_path = str(file_path.relative_to(config.root_path))

        prev = existing.get(relative_path)
        if prev and prev["content_hash"] == content_hash:
            # Content unchanged — still need to ensure embeddings exist for
            # the current provider/model (handles provider switch).
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id FROM chunks WHERE document_id = %s ORDER BY chunk_index",
                    (prev["id"],),
                )
                chunk_rows = cur.fetchall()

            chunks = _split_text(raw_content, chunk_size, chunk_overlap)
            for idx, chunk_row in enumerate(chunk_rows):
                chunk_content = chunks[idx] if idx < len(chunks) else None
                if chunk_content is None:
                    continue
                _ensure_embedding(conn, chunk_id=chunk_row["id"], project_id=config.id, content=chunk_content)

            skipped_documents += 1
            continue

        # Content changed or new file — delete old document rows (cascades to
        # chunks and embeddings) then re-insert.
        if prev:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (prev["id"],))

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO documents (project_id, source_type, path, title, content_hash, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    config.id,
                    "file",
                    relative_path,
                    file_path.name,
                    content_hash,
                    Json({"absolute_path": str(file_path)}),
                ),
            )
            row = cur.fetchone()

        if not row:
            raise RuntimeError(f"Failed to insert document row for {file_path}")

        document_id = row["id"]
        chunks = _split_text(raw_content, chunk_size, chunk_overlap)
        for idx, chunk in enumerate(chunks):
            index_chunk(
                conn,
                project_id=config.id,
                document_id=document_id,
                file_path=relative_path,
                chunk_index=idx,
                chunk_type="text",
                content=chunk,
            )
            indexed_chunks += 1

        indexed_documents += 1

    return indexed_documents, indexed_chunks, skipped_documents


def _ensure_embedding(
    conn: Connection,
    *,
    chunk_id: UUID,
    project_id: str,
    content: str,
) -> None:
    """Create an embedding for *chunk_id* if one does not exist for the active provider/model."""
    table = get_embedding_table(EMBEDDING_DIMENSIONS)
    exists_query = SQL(
        "SELECT 1 FROM {table} WHERE chunk_id = %s AND provider = %s AND model = %s LIMIT 1"
    ).format(table=Identifier(table))
    with conn.cursor() as cur:
        cur.execute(exists_query, (chunk_id, EMBEDDING_PROVIDER, EMBEDDING_MODEL))
        if cur.fetchone() is not None:
            return

    embedding = get_embedding(content)
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise EmbeddingProviderError(
            f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, got {len(embedding)}"
        )

    upsert_embedding(
        conn,
        chunk_id=chunk_id,
        project_id=project_id,
        provider=EMBEDDING_PROVIDER,
        model=EMBEDDING_MODEL,
        embedding=embedding,
    )


def main() -> None:
    args = _build_parser().parse_args()
    config = _load_project_config(Path(args.project_config).expanduser().resolve())
    files = _discover_files(config)

    if not files:
        include_joined = ", ".join(config.include)
        exclude_joined = ", ".join(config.exclude) if config.exclude else "(none)"
        raise SystemExit(
            "No files matched project config. "
            f"root_path={config.root_path} include=[{include_joined}] exclude=[{exclude_joined}]"
        )

    with connect(DATABASE_URL) as conn:
        _upsert_project(conn, config)
        documents, chunks, skipped = _reindex_project(
            conn,
            config=config,
            files=files,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        conn.commit()

    print(
        f"Indexed project={config.id} files={len(files)} "
        f"documents={documents} chunks={chunks} skipped={skipped} "
        f"provider={EMBEDDING_PROVIDER} model={EMBEDDING_MODEL} "
        f"dimensions={EMBEDDING_DIMENSIONS}"
    )


if __name__ == "__main__":
    main()