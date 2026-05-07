"""Safe memory deletion (forget) operations for agent-brain.

This module provides controlled deletion of memories, decisions, and chunks
with support for dry-run mode, audit logging, and safety constraints.

Deletion is allowed by:
- Memory/chunk ID (single item)
- Decision ID (single item)
- Project ID + category + query match (bulk with dry-run required)

Unsafe broad deletions without clear matching rules are blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.sql import Identifier, SQL

from app.audit import AuditStatus, get_audit_logger
from app.config import EMBEDDING_DIMENSIONS
from app.errors import ForgetError
from app.vector_store import get_embedding_table


@dataclass(frozen=True)
class ForgetResult:
    """Result of a forget/delete operation."""

    deleted: bool
    count: int
    dry_run: bool
    items: list[dict[str, Any]]
    message: str


@dataclass(frozen=True)
class ForgetTarget:
    """Specifies what to delete."""

    chunk_id: UUID | None = None
    decision_id: UUID | None = None
    project_id: str | None = None
    category: str | None = None
    query: str | None = None


def forget_by_chunk_id(
    conn: Connection,
    *,
    chunk_id: UUID,
    project_id: str,
) -> ForgetResult:
    """Delete a single chunk and its embeddings by ID.

    Args:
        conn: Database connection.
        chunk_id: The UUID of the chunk to delete.
        project_id: Project ID for validation and audit.

    Returns:
        ForgetResult with deletion status.

    Raises:
        ForgetError: If the chunk doesn't exist or doesn't belong to the project.
    """
    audit = get_audit_logger()

    # Verify the chunk exists and belongs to the project
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, project_id, file_path, chunk_index, content
            FROM chunks
            WHERE id = %s
            """,
            (chunk_id,),
        )
        row = cur.fetchone()

    if not row:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.FAILED,
            item_id=str(chunk_id),
            reason="Chunk not found",
        )
        raise ForgetError(f"Chunk with ID {chunk_id} not found")

    if row["project_id"] != project_id:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.BLOCKED,
            item_id=str(chunk_id),
            reason="Chunk belongs to a different project",
        )
        raise ForgetError(
            f"Chunk {chunk_id} belongs to project '{row['project_id']}', "
            f"not '{project_id}'"
        )

    # Delete the chunk (embeddings cascade automatically)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM chunks WHERE id = %s", (chunk_id,))
        deleted_count = cur.rowcount

    conn.commit()

    audit.log_memory_delete(
        project_id=project_id,
        status=AuditStatus.SUCCESS,
        item_id=str(chunk_id),
        item_count=deleted_count,
    )

    return ForgetResult(
        deleted=True,
        count=deleted_count,
        dry_run=False,
        items=[
            {
                "id": str(chunk_id),
                "file_path": row["file_path"],
                "chunk_index": row["chunk_index"],
            }
        ],
        message=f"Deleted chunk {chunk_id}",
    )


def forget_by_decision_id(
    conn: Connection,
    *,
    decision_id: UUID,
    project_id: str,
) -> ForgetResult:
    """Delete a single decision by ID.

    Args:
        conn: Database connection.
        decision_id: The UUID of the decision to delete.
        project_id: Project ID for validation and audit.

    Returns:
        ForgetResult with deletion status.

    Raises:
        ForgetError: If the decision doesn't exist or doesn't belong to the project.
    """
    audit = get_audit_logger()

    # Verify the decision exists and belongs to the project
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, project_id, title, status
            FROM decisions
            WHERE id = %s
            """,
            (decision_id,),
        )
        row = cur.fetchone()

    if not row:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.FAILED,
            item_id=str(decision_id),
            category="decision",
            reason="Decision not found",
        )
        raise ForgetError(f"Decision with ID {decision_id} not found")

    if row["project_id"] != project_id:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.BLOCKED,
            item_id=str(decision_id),
            category="decision",
            reason="Decision belongs to a different project",
        )
        raise ForgetError(
            f"Decision {decision_id} belongs to project '{row['project_id']}', "
            f"not '{project_id}'"
        )

    # Delete the decision
    with conn.cursor() as cur:
        cur.execute("DELETE FROM decisions WHERE id = %s", (decision_id,))
        deleted_count = cur.rowcount

    conn.commit()

    audit.log_memory_delete(
        project_id=project_id,
        status=AuditStatus.SUCCESS,
        item_id=str(decision_id),
        item_count=deleted_count,
        category="decision",
    )

    return ForgetResult(
        deleted=True,
        count=deleted_count,
        dry_run=False,
        items=[
            {
                "id": str(decision_id),
                "title": row["title"],
                "status": row["status"],
            }
        ],
        message=f"Deleted decision {decision_id}",
    )


def forget_by_query(
    conn: Connection,
    *,
    project_id: str,
    category: str | None = None,
    file_path_pattern: str | None = None,
    dry_run: bool = True,
    limit: int = 100,
) -> ForgetResult:
    """Delete chunks matching a query pattern.

    For safety, this defaults to dry_run=True. Set dry_run=False to
    actually delete the matching chunks.

    Args:
        conn: Database connection.
        project_id: Project ID (required).
        category: Optional chunk_type to filter by.
        file_path_pattern: Optional LIKE pattern for file_path.
        dry_run: If True, only return what would be deleted.
        limit: Maximum number of items to delete in one operation.

    Returns:
        ForgetResult with deletion status and matched items.

    Raises:
        ForgetError: If the query is too broad or invalid.
    """
    audit = get_audit_logger()

    if not project_id or not project_id.strip():
        raise ForgetError("project_id is required for query-based deletion")

    # Require at least one filter besides project_id
    if not category and not file_path_pattern:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.BLOCKED,
            reason="Query-based deletion requires at least category or file_path_pattern",
        )
        raise ForgetError(
            "Query-based deletion requires at least one filter "
            "(category or file_path_pattern) to prevent accidental bulk deletion"
        )

    # Build the query
    conditions = ["project_id = %s"]
    params: list[Any] = [project_id]

    if category:
        conditions.append("chunk_type = %s")
        params.append(category)

    if file_path_pattern:
        conditions.append("file_path LIKE %s")
        params.append(file_path_pattern)

    where_clause = " AND ".join(conditions)

    # Find matching chunks
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT id, file_path, chunk_index, chunk_type
            FROM chunks
            WHERE {where_clause}
            ORDER BY file_path, chunk_index
            LIMIT %s
            """,
            (*params, limit),
        )
        rows = cur.fetchall()

    if not rows:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.SUCCESS,
            item_count=0,
            category=category,
            dry_run=dry_run,
            reason="No matching chunks found",
        )
        return ForgetResult(
            deleted=False,
            count=0,
            dry_run=dry_run,
            items=[],
            message="No chunks matched the query",
        )

    items = [
        {
            "id": str(row["id"]),
            "file_path": row["file_path"],
            "chunk_index": row["chunk_index"],
            "chunk_type": row["chunk_type"],
        }
        for row in rows
    ]

    if dry_run:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.SUCCESS,
            item_count=len(items),
            category=category,
            dry_run=True,
        )
        return ForgetResult(
            deleted=False,
            count=len(items),
            dry_run=True,
            items=items,
            message=f"Would delete {len(items)} chunks (dry run)",
        )

    # Actually delete the chunks
    chunk_ids = [row["id"] for row in rows]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            DELETE FROM chunks
            WHERE {where_clause}
            LIMIT %s
            """,
            (*params, limit),
        )
        deleted_count = cur.rowcount

    conn.commit()

    audit.log_memory_delete(
        project_id=project_id,
        status=AuditStatus.SUCCESS,
        item_count=deleted_count,
        category=category,
        dry_run=False,
    )

    return ForgetResult(
        deleted=True,
        count=deleted_count,
        dry_run=False,
        items=items,
        message=f"Deleted {deleted_count} chunks",
    )


def forget_document(
    conn: Connection,
    *,
    document_id: UUID,
    project_id: str,
) -> ForgetResult:
    """Delete a document and all its chunks by document ID.

    Args:
        conn: Database connection.
        document_id: The UUID of the document to delete.
        project_id: Project ID for validation and audit.

    Returns:
        ForgetResult with deletion status.

    Raises:
        ForgetError: If the document doesn't exist or doesn't belong to the project.
    """
    audit = get_audit_logger()

    # Verify the document exists and belongs to the project
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, project_id, path, title
            FROM documents
            WHERE id = %s
            """,
            (document_id,),
        )
        row = cur.fetchone()

    if not row:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.FAILED,
            item_id=str(document_id),
            reason="Document not found",
        )
        raise ForgetError(f"Document with ID {document_id} not found")

    if row["project_id"] != project_id:
        audit.log_memory_delete(
            project_id=project_id,
            status=AuditStatus.BLOCKED,
            item_id=str(document_id),
            reason="Document belongs to a different project",
        )
        raise ForgetError(
            f"Document {document_id} belongs to project '{row['project_id']}', "
            f"not '{project_id}'"
        )

    # Count chunks that will be deleted
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_id = %s",
            (document_id,),
        )
        chunk_count = cur.fetchone()[0]  # type: ignore

    # Delete the document (chunks cascade automatically)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        deleted_count = cur.rowcount

    conn.commit()

    audit.log_memory_delete(
        project_id=project_id,
        status=AuditStatus.SUCCESS,
        item_id=str(document_id),
        item_count=chunk_count + 1,  # Document + chunks
        reason=f"Deleted document and {chunk_count} chunks",
    )

    return ForgetResult(
        deleted=True,
        count=chunk_count + 1,
        dry_run=False,
        items=[
            {
                "id": str(document_id),
                "path": row["path"],
                "title": row["title"],
                "chunks_deleted": chunk_count,
            }
        ],
        message=f"Deleted document {document_id} and {chunk_count} chunks",
    )
