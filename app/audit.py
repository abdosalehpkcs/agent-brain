"""Audit logging for agent-brain memory operations.

This module provides structured audit logging for all memory-changing operations.
Audit events are stored in JSON-lines format for easy parsing and analysis.

Design choice: JSON-lines file over database table because:
1. Audit logs should be independent of the main data store
2. Easier to ship/archive logs externally
3. No risk of audit failures blocking memory operations
4. Simpler disaster recovery and forensics

Note: Raw content is NOT stored in audit logs. Only content hashes are logged
to protect potentially sensitive information.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app.errors import AuditError


class AuditOperation(str, Enum):
    """Types of operations that are audited."""

    MEMORY_WRITE = "memory_write"
    DECISION_SAVE = "decision_save"
    MEMORY_DELETE = "memory_delete"
    PDF_INGEST = "pdf_ingest"
    BULK_IMPORT = "bulk_import"
    POLICY_BLOCKED = "policy_blocked"
    EMBEDDING_FAILURE = "embedding_failure"


class AuditStatus(str, Enum):
    """Status of an audited operation."""

    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    DRY_RUN = "dry_run"


@dataclass
class AuditEvent:
    """Represents a single audit log entry."""

    timestamp: str
    operation: str
    project_id: str
    status: str
    category: str | None = None
    source: str | None = None
    content_hash: str | None = None
    reason: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    item_id: str | None = None
    item_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                result[key] = value
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """Thread-safe audit logger that writes to JSON-lines files."""

    def __init__(
        self,
        log_dir: Path | str | None = None,
        log_file: str = "agent-brain-audit.jsonl",
    ):
        if log_dir is None:
            log_dir = Path(os.getenv("AUDIT_LOG_DIR", "."))

        self.log_dir = Path(log_dir)
        self.log_file = log_file
        self._lock = threading.Lock()
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        """Create log directory if it doesn't exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        """Full path to the audit log file."""
        return self.log_dir / self.log_file

    def log(self, event: AuditEvent) -> None:
        """Write an audit event to the log file."""
        with self._lock:
            try:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(event.to_json() + "\n")
            except OSError as exc:
                # Don't let audit failures block operations
                # Log to stderr as fallback
                import sys

                print(
                    f"[AUDIT_ERROR] Failed to write audit log: {exc}",
                    file=sys.stderr,
                )

    def log_memory_write(
        self,
        *,
        project_id: str,
        status: AuditStatus,
        category: str | None = None,
        source: str | None = None,
        content: str | None = None,
        reason: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a memory write operation."""
        event = AuditEvent(
            timestamp=_now_iso(),
            operation=AuditOperation.MEMORY_WRITE.value,
            project_id=project_id,
            status=status.value,
            category=category,
            source=source,
            content_hash=_hash_content(content) if content else None,
            reason=reason,
            embedding_provider=provider,
            embedding_model=model,
            item_id=item_id,
            metadata=metadata or {},
        )
        self.log(event)
        return event

    def log_decision_save(
        self,
        *,
        project_id: str,
        status: AuditStatus,
        title: str,
        decision: str,
        source: str | None = None,
        reason: str | None = None,
        item_id: str | None = None,
    ) -> AuditEvent:
        """Log a decision save operation."""
        # Combine title and decision for the content hash
        content = f"{title}\n{decision}"
        event = AuditEvent(
            timestamp=_now_iso(),
            operation=AuditOperation.DECISION_SAVE.value,
            project_id=project_id,
            status=status.value,
            category="decision",
            source=source,
            content_hash=_hash_content(content),
            reason=reason,
            item_id=item_id,
        )
        self.log(event)
        return event

    def log_memory_delete(
        self,
        *,
        project_id: str,
        status: AuditStatus,
        item_id: str | None = None,
        item_count: int | None = None,
        category: str | None = None,
        reason: str | None = None,
        dry_run: bool = False,
    ) -> AuditEvent:
        """Log a memory delete/forget operation."""
        actual_status = AuditStatus.DRY_RUN if dry_run else status
        event = AuditEvent(
            timestamp=_now_iso(),
            operation=AuditOperation.MEMORY_DELETE.value,
            project_id=project_id,
            status=actual_status.value,
            category=category,
            item_id=item_id,
            item_count=item_count,
            reason=reason,
        )
        self.log(event)
        return event

    def log_pdf_ingest(
        self,
        *,
        project_id: str,
        status: AuditStatus,
        source: str,
        chunk_count: int | None = None,
        reason: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Log a PDF ingestion operation."""
        event = AuditEvent(
            timestamp=_now_iso(),
            operation=AuditOperation.PDF_INGEST.value,
            project_id=project_id,
            status=status.value,
            category="pdf_content",
            source=source,
            item_count=chunk_count,
            reason=reason,
            embedding_provider=provider,
            embedding_model=model,
            metadata=metadata or {},
        )
        self.log(event)
        return event

    def log_policy_blocked(
        self,
        *,
        project_id: str,
        category: str | None,
        source: str | None = None,
        reason: str,
    ) -> AuditEvent:
        """Log a policy-blocked write attempt."""
        event = AuditEvent(
            timestamp=_now_iso(),
            operation=AuditOperation.POLICY_BLOCKED.value,
            project_id=project_id,
            status=AuditStatus.BLOCKED.value,
            category=category,
            source=source,
            reason=reason,
        )
        self.log(event)
        return event

    def log_embedding_failure(
        self,
        *,
        project_id: str,
        reason: str,
        provider: str | None = None,
        model: str | None = None,
        source: str | None = None,
    ) -> AuditEvent:
        """Log an embedding generation failure."""
        event = AuditEvent(
            timestamp=_now_iso(),
            operation=AuditOperation.EMBEDDING_FAILURE.value,
            project_id=project_id,
            status=AuditStatus.FAILED.value,
            reason=reason,
            embedding_provider=provider,
            embedding_model=model,
            source=source,
        )
        self.log(event)
        return event

    def read_recent(self, count: int = 100) -> list[AuditEvent]:
        """Read the most recent audit events from the log file.

        Returns events in reverse chronological order (newest first).
        """
        if not self.log_path.exists():
            return []

        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []

        events = []
        for line in reversed(lines[-count:]):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                events.append(
                    AuditEvent(
                        timestamp=data.get("timestamp", ""),
                        operation=data.get("operation", ""),
                        project_id=data.get("project_id", ""),
                        status=data.get("status", ""),
                        category=data.get("category"),
                        source=data.get("source"),
                        content_hash=data.get("content_hash"),
                        reason=data.get("reason"),
                        embedding_provider=data.get("embedding_provider"),
                        embedding_model=data.get("embedding_model"),
                        item_id=data.get("item_id"),
                        item_count=data.get("item_count"),
                        metadata=data.get("metadata", {}),
                    )
                )
            except json.JSONDecodeError:
                continue

        return events

    def clear(self) -> None:
        """Clear the audit log file (use with caution)."""
        with self._lock:
            if self.log_path.exists():
                self.log_path.unlink()


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def set_audit_logger(logger: AuditLogger) -> None:
    """Set a custom audit logger (useful for testing)."""
    global _audit_logger
    _audit_logger = logger


def reset_audit_logger() -> None:
    """Reset the global audit logger (useful for testing)."""
    global _audit_logger
    _audit_logger = None


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _hash_content(content: str) -> str:
    """Generate a SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
