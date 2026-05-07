"""MCP server exposing agent-brain memory tools.

This module provides a thin MCP layer over existing search and decision-memory
business logic. It intentionally avoids re-implementing indexing or retrieval.
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Any
from uuid import UUID

import requests
from psycopg import connect
from psycopg.rows import dict_row

from app.audit import AuditStatus, get_audit_logger
from app.config import (
    DATABASE_URL,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    OLLAMA_BASE_URL,
    SUPPORTED_DIMENSIONS,
)
from app.decisions import add_decision, list_project_decisions
from app.forget import (
    forget_by_chunk_id,
    forget_by_decision_id,
    forget_by_query,
    forget_document,
)
from app.pdf_ingestion import ingest_pdf
from app.policy import WriteRequest, get_policy, validate_write
from app.search import search_project_memory
from app.vector_store import get_embedding_status

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    FastMCP = None
    _MCP_IMPORT_ERROR = exc
else:
    _MCP_IMPORT_ERROR = None


def _get_app_version() -> str:
    try:
        return metadata.version("agent-brain")
    except metadata.PackageNotFoundError:
        return "development"


def _db_reachable() -> bool:
    try:
        with connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
    except Exception:
        return False


def _ollama_reachable() -> bool | None:
    if EMBEDDING_PROVIDER != "ollama":
        return None
    try:
        response = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=5)
        return response.ok
    except requests.RequestException:
        return False


def _serialize_chunk(chunk: Any) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk.chunk_id),
        "project_id": chunk.project_id,
        "document_id": str(chunk.document_id),
        "file_path": chunk.file_path,
        "chunk_index": chunk.chunk_index,
        "chunk_type": chunk.chunk_type,
        "content": chunk.content,
        "metadata": chunk.metadata,
        "provider": chunk.provider,
        "model": chunk.model,
        "distance": chunk.distance,
    }


def _serialize_decision(decision: Any) -> dict[str, Any]:
    return {
        "id": str(decision.id),
        "project_id": decision.project_id,
        "title": decision.title,
        "decision": decision.decision,
        "reason": decision.reason,
        "alternatives": decision.alternatives,
        "status": decision.status,
        "source": decision.source,
        "created_at": decision.created_at.isoformat(),
    }


def build_server() -> Any:
    if FastMCP is None:  # pragma: no cover
        raise RuntimeError(
            "MCP SDK is not installed in this Python environment. "
            "Use Python 3.12+ and install requirements, then run again."
        ) from _MCP_IMPORT_ERROR

    mcp = FastMCP("agent-brain")

    @mcp.tool()
    def search_project_context(
        project_id: str,
        query: str,
        top_k: int = 8,
        include_decisions: bool = True,
    ) -> dict[str, Any]:
        """Search semantic project context and optionally include active decisions."""
        if not project_id.strip():
            raise ValueError("project_id is required")
        if not query.strip():
            raise ValueError("query is required")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        try:
            with connect(DATABASE_URL) as conn:
                chunks, decisions = search_project_memory(
                    conn,
                    project_id=project_id,
                    query_text=query,
                    limit=top_k,
                    include_decisions=include_decisions,
                )
        except Exception as exc:
            raise RuntimeError(f"search_project_context failed: {exc}") from None

        return {
            "project_id": project_id,
            "query": query,
            "provider": EMBEDDING_PROVIDER,
            "model": EMBEDDING_MODEL,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
            "chunks": [_serialize_chunk(chunk) for chunk in chunks],
            "decisions": [_serialize_decision(decision) for decision in decisions],
        }

    @mcp.tool()
    def get_project_decisions(project_id: str) -> dict[str, Any]:
        """Return active and recent decisions for a project."""
        if not project_id.strip():
            raise ValueError("project_id is required")

        try:
            with connect(DATABASE_URL) as conn:
                active = list_project_decisions(
                    conn,
                    project_id=project_id,
                    status="active",
                    limit=50,
                )
                recent = list_project_decisions(
                    conn,
                    project_id=project_id,
                    limit=50,
                )
        except Exception as exc:
            raise RuntimeError(f"get_project_decisions failed: {exc}") from None

        return {
            "project_id": project_id,
            "active_decisions": [_serialize_decision(record) for record in active],
            "recent_decisions": [_serialize_decision(record) for record in recent],
        }

    @mcp.tool()
    def save_project_decision(
        project_id: str,
        title: str,
        decision: str,
        reason: str = "",
        alternatives: str = "",
        status: str = "active",
        source: str = "mcp",
        category: str = "confirmed_decisions",
    ) -> dict[str, Any]:
        """Persist a decision for long-term project memory."""
        if not project_id.strip():
            raise ValueError("project_id is required")
        if not title.strip():
            raise ValueError("title is required")
        if not decision.strip():
            raise ValueError("decision is required")

        audit = get_audit_logger()

        # Validate write policy
        policy = get_policy()
        request = WriteRequest(
            category=category,
            source=source,
            context=reason if reason else None,
        )
        validation = validate_write(request, policy)

        if not validation.allowed:
            audit.log_policy_blocked(
                project_id=project_id,
                category=category,
                source=source,
                reason=validation.reason,
            )
            raise ValueError(f"Write blocked by policy: {validation.reason}")

        try:
            with connect(DATABASE_URL) as conn:
                record = add_decision(
                    conn,
                    project_id=project_id,
                    title=title,
                    decision=decision,
                    reason=reason,
                    alternatives=alternatives,
                    status=status,
                    source=source,
                )
                conn.commit()

                audit.log_decision_save(
                    project_id=project_id,
                    status=AuditStatus.SUCCESS,
                    title=title,
                    decision=decision,
                    source=source,
                    item_id=str(record.id),
                )
        except Exception as exc:
            audit.log_decision_save(
                project_id=project_id,
                status=AuditStatus.FAILED,
                title=title,
                decision=decision,
                source=source,
                reason=str(exc),
            )
            raise RuntimeError(f"save_project_decision failed: {exc}") from None

        return {
            "saved": True,
            "decision": _serialize_decision(record),
        }

    @mcp.tool()
    def system_status() -> dict[str, Any]:
        """Return runtime health and active provider configuration."""
        return {
            "database_reachable": _db_reachable(),
            "provider": EMBEDDING_PROVIDER,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
            "supported_dimensions": sorted(SUPPORTED_DIMENSIONS),
            "ollama_reachable": _ollama_reachable(),
            "app_version": _get_app_version(),
        }

    @mcp.tool()
    def embedding_status(project_id: str) -> dict[str, Any]:
        """Return embedding coverage per provider/model for a project."""
        if not project_id.strip():
            raise ValueError("project_id is required")

        try:
            with connect(DATABASE_URL) as conn:
                rows = get_embedding_status(conn, project_id=project_id)
        except Exception as exc:
            raise RuntimeError(f"embedding_status failed: {exc}") from None

        return {
            "project_id": project_id,
            "entries": [
                {
                    "provider": r.provider,
                    "model": r.model,
                    "dimensions": r.dimensions,
                    "indexed": r.indexed,
                    "embedding_count": r.embedding_count,
                    "chunk_count": r.chunk_count,
                    "missing_count": r.missing_count,
                }
                for r in rows
            ],
        }

    @mcp.tool()
    def list_projects() -> dict[str, Any]:
        """List known projects from the projects table."""
        try:
            with connect(DATABASE_URL) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT id, name, type, root_path, description, created_at
                        FROM projects
                        ORDER BY created_at DESC
                        """
                    )
                    rows = cur.fetchall()
        except Exception as exc:
            raise RuntimeError(f"list_projects failed: {exc}") from None

        return {
            "projects": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "type": row["type"],
                    "root_path": row["root_path"],
                    "description": row["description"],
                    "created_at": row["created_at"].isoformat(),
                }
                for row in rows
            ]
        }

    @mcp.tool()
    def forget_memory(
        project_id: str,
        chunk_id: str | None = None,
        decision_id: str | None = None,
        document_id: str | None = None,
        category: str | None = None,
        file_path_pattern: str | None = None,
        dry_run: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Safely delete memory items with audit logging.

        Supports deletion by:
        - chunk_id: Delete a single chunk
        - decision_id: Delete a single decision
        - document_id: Delete a document and all its chunks
        - category + file_path_pattern: Query-based deletion (requires dry_run first)

        For safety, query-based deletion defaults to dry_run=True.
        """
        if not project_id.strip():
            raise ValueError("project_id is required")

        # Must specify exactly one target type
        targets = [chunk_id, decision_id, document_id, (category or file_path_pattern)]
        specified = sum(1 for t in targets if t)

        if specified == 0:
            raise ValueError(
                "Must specify one of: chunk_id, decision_id, document_id, "
                "or category/file_path_pattern"
            )

        try:
            with connect(DATABASE_URL) as conn:
                if chunk_id:
                    result = forget_by_chunk_id(
                        conn,
                        chunk_id=UUID(chunk_id),
                        project_id=project_id,
                    )
                elif decision_id:
                    result = forget_by_decision_id(
                        conn,
                        decision_id=UUID(decision_id),
                        project_id=project_id,
                    )
                elif document_id:
                    result = forget_document(
                        conn,
                        document_id=UUID(document_id),
                        project_id=project_id,
                    )
                else:
                    result = forget_by_query(
                        conn,
                        project_id=project_id,
                        category=category,
                        file_path_pattern=file_path_pattern,
                        dry_run=dry_run,
                        limit=limit,
                    )
        except Exception as exc:
            raise RuntimeError(f"forget_memory failed: {exc}") from None

        return {
            "deleted": result.deleted,
            "count": result.count,
            "dry_run": result.dry_run,
            "items": result.items,
            "message": result.message,
        }

    @mcp.tool()
    def ingest_pdf_document(
        project_id: str,
        file_path: str,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
        skip_duplicates: bool = True,
        category: str = "pdf_content",
    ) -> dict[str, Any]:
        """Ingest a PDF document into project memory.

        Extracts text, chunks with page references, generates embeddings,
        and stores in the project memory with full audit logging.
        """
        if not project_id.strip():
            raise ValueError("project_id is required")
        if not file_path.strip():
            raise ValueError("file_path is required")

        try:
            with connect(DATABASE_URL) as conn:
                result = ingest_pdf(
                    conn,
                    file_path=Path(file_path),
                    project_id=project_id,
                    source="mcp",
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    skip_duplicates=skip_duplicates,
                    category=category,
                )
        except Exception as exc:
            raise RuntimeError(f"ingest_pdf failed: {exc}") from None

        return {
            "success": result.success,
            "document_id": str(result.document_id) if result.document_id else None,
            "chunk_count": result.chunk_count,
            "pages_processed": result.pages_processed,
            "skipped": result.skipped,
            "message": result.message,
        }

    return mcp


def main() -> None:
    try:
        server = build_server()
        server.run()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()