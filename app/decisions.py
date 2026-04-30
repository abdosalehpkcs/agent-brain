"""Decision memory storage and CLI helpers.

Decision memory persists long-lived project choices so agents and developers can
reuse architecture rationale across sessions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg import Connection, connect
from psycopg.rows import dict_row

from app.config import DATABASE_URL
from app.errors import DecisionMemoryError


@dataclass(frozen=True)
class DecisionRecord:
    id: UUID
    project_id: str
    title: str
    decision: str
    reason: str | None
    alternatives: str | None
    status: str | None
    source: str | None
    created_at: datetime


def _get_connection() -> Connection:
    return connect(DATABASE_URL)


def add_decision(
    conn: Connection,
    *,
    project_id: str,
    title: str,
    decision: str,
    reason: str | None = None,
    alternatives: str | None = None,
    status: str | None = None,
    source: str | None = None,
) -> DecisionRecord:
    normalized_project_id = project_id.strip()
    normalized_title = title.strip()
    normalized_decision = decision.strip()

    if not normalized_project_id:
        raise DecisionMemoryError("project_id cannot be empty")
    if not normalized_title:
        raise DecisionMemoryError("title cannot be empty")
    if not normalized_decision:
        raise DecisionMemoryError("decision cannot be empty")

    query = """
        INSERT INTO decisions (
            project_id,
            title,
            decision,
            reason,
            alternatives,
            status,
            source
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            project_id,
            title,
            decision,
            reason,
            alternatives,
            status,
            source,
            created_at
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            query,
            (
                normalized_project_id,
                normalized_title,
                normalized_decision,
                _normalize_optional(reason),
                _normalize_optional(alternatives),
                _normalize_optional(status),
                _normalize_optional(source),
            ),
        )
        row = cur.fetchone()

    if not row:
        raise RuntimeError("Failed to insert decision")

    return _row_to_decision(row)


def list_project_decisions(
    conn: Connection,
    *,
    project_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[DecisionRecord]:
    normalized_project_id = project_id.strip()
    if not normalized_project_id:
        raise DecisionMemoryError("project_id cannot be empty")
    if limit <= 0:
        raise DecisionMemoryError("limit must be greater than zero")

    if status and status.strip():
        query = """
            SELECT
                id,
                project_id,
                title,
                decision,
                reason,
                alternatives,
                status,
                source,
                created_at
            FROM decisions
            WHERE project_id = %s
              AND status = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        params = (normalized_project_id, status.strip(), limit)
    else:
        query = """
            SELECT
                id,
                project_id,
                title,
                decision,
                reason,
                alternatives,
                status,
                source,
                created_at
            FROM decisions
            WHERE project_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        params = (normalized_project_id, limit)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [_row_to_decision(row) for row in rows]


def get_decision_by_id(conn: Connection, *, decision_id: UUID) -> DecisionRecord | None:
    query = """
        SELECT
            id,
            project_id,
            title,
            decision,
            reason,
            alternatives,
            status,
            source,
            created_at
        FROM decisions
        WHERE id = %s
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (decision_id,))
        row = cur.fetchone()

    return _row_to_decision(row) if row else None


def update_decision_status(
    conn: Connection,
    *,
    decision_id: UUID,
    status: str,
) -> DecisionRecord | None:
    normalized_status = status.strip()
    if not normalized_status:
        raise DecisionMemoryError("status cannot be empty")

    query = """
        UPDATE decisions
        SET status = %s
        WHERE id = %s
        RETURNING
            id,
            project_id,
            title,
            decision,
            reason,
            alternatives,
            status,
            source,
            created_at
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (normalized_status, decision_id))
        row = cur.fetchone()

    return _row_to_decision(row) if row else None


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _row_to_decision(row: dict) -> DecisionRecord:
    return DecisionRecord(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        decision=row["decision"],
        reason=row["reason"],
        alternatives=row["alternatives"],
        status=row["status"],
        source=row["source"],
        created_at=row["created_at"],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Decision memory CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a decision")
    add_parser.add_argument("--project-id", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--decision", required=True)
    add_parser.add_argument("--reason")
    add_parser.add_argument("--alternatives")
    add_parser.add_argument("--status")
    add_parser.add_argument("--source")

    list_parser = subparsers.add_parser("list", help="List project decisions")
    list_parser.add_argument("--project-id", required=True)
    list_parser.add_argument("--status")
    list_parser.add_argument("--limit", type=int, default=50)

    get_parser = subparsers.add_parser("get", help="Get a decision by ID")
    get_parser.add_argument("--id", required=True)

    status_parser = subparsers.add_parser("status", help="Update decision status")
    status_parser.add_argument("--id", required=True)
    status_parser.add_argument("--status", required=True)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    with _get_connection() as conn:
        if args.command == "add":
            record = add_decision(
                conn,
                project_id=args.project_id,
                title=args.title,
                decision=args.decision,
                reason=args.reason,
                alternatives=args.alternatives,
                status=args.status,
                source=args.source,
            )
            conn.commit()
            print(f"Added decision: {record.id}")
            return

        if args.command == "list":
            records = list_project_decisions(
                conn,
                project_id=args.project_id,
                status=args.status,
                limit=args.limit,
            )
            if not records:
                print("No decisions found")
                return
            for record in records:
                status_text = record.status or "unknown"
                print(f"{record.id} | {status_text} | {record.title}")
            return

        if args.command == "get":
            decision_id = UUID(args.id)
            record = get_decision_by_id(conn, decision_id=decision_id)
            if not record:
                print("Decision not found")
                return
            print(f"id: {record.id}")
            print(f"project_id: {record.project_id}")
            print(f"title: {record.title}")
            print(f"decision: {record.decision}")
            print(f"reason: {record.reason or ''}")
            print(f"alternatives: {record.alternatives or ''}")
            print(f"status: {record.status or ''}")
            print(f"source: {record.source or ''}")
            print(f"created_at: {record.created_at}")
            return

        if args.command == "status":
            decision_id = UUID(args.id)
            record = update_decision_status(
                conn,
                decision_id=decision_id,
                status=args.status,
            )
            if not record:
                print("Decision not found")
                return
            conn.commit()
            print(f"Updated decision status: {record.id} -> {record.status}")
            return

        raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()