"""Tests for audit logging."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.audit import (
    AuditEvent,
    AuditLogger,
    AuditOperation,
    AuditStatus,
    get_audit_logger,
    reset_audit_logger,
    set_audit_logger,
)


@pytest.fixture
def temp_audit_dir():
    """Create a temporary directory for audit logs."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def audit_logger(temp_audit_dir):
    """Create a test audit logger."""
    logger = AuditLogger(log_dir=temp_audit_dir)
    set_audit_logger(logger)
    yield logger
    reset_audit_logger()


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_event_to_dict_excludes_none(self) -> None:
        event = AuditEvent(
            timestamp="2025-01-01T00:00:00Z",
            operation="test",
            project_id="proj1",
            status="success",
            category=None,
            source=None,
        )

        data = event.to_dict()

        assert "category" not in data
        assert "source" not in data
        assert data["timestamp"] == "2025-01-01T00:00:00Z"

    def test_event_to_json(self) -> None:
        event = AuditEvent(
            timestamp="2025-01-01T00:00:00Z",
            operation="memory_write",
            project_id="proj1",
            status="success",
            content_hash="abc123",
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["operation"] == "memory_write"
        assert data["content_hash"] == "abc123"


class TestAuditLoggerSuccessfulWrite:
    """Tests for audit logging on successful writes."""

    def test_log_memory_write_success(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_memory_write(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            category="architecture_notes",
            source="user",
            content="Test content for hashing",
            provider="ollama",
            model="nomic-embed-text",
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.operation == AuditOperation.MEMORY_WRITE.value
        assert event.status == AuditStatus.SUCCESS.value
        assert event.project_id == "test-project"
        assert event.category == "architecture_notes"
        assert event.content_hash is not None
        assert event.embedding_provider == "ollama"

    def test_log_decision_save_success(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_decision_save(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            title="Use PostgreSQL",
            decision="We will use PostgreSQL for storage",
            source="team_meeting",
            item_id="decision-123",
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.operation == AuditOperation.DECISION_SAVE.value
        assert event.status == AuditStatus.SUCCESS.value
        assert event.content_hash is not None
        assert "postgres" not in event.content_hash.lower()  # Content not in hash


class TestAuditLoggerBlockedWrite:
    """Tests for audit logging on blocked writes."""

    def test_log_policy_blocked(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_policy_blocked(
            project_id="test-project",
            category="blocked_category",
            source="mcp",
            reason="Category 'blocked_category' is not allowed",
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.operation == AuditOperation.POLICY_BLOCKED.value
        assert event.status == AuditStatus.BLOCKED.value
        assert "not allowed" in event.reason


class TestAuditLoggerFailedWrite:
    """Tests for audit logging on failed writes."""

    def test_log_embedding_failure(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_embedding_failure(
            project_id="test-project",
            reason="Connection to Ollama failed",
            provider="ollama",
            model="nomic-embed-text",
            source="indexer",
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.operation == AuditOperation.EMBEDDING_FAILURE.value
        assert event.status == AuditStatus.FAILED.value
        assert "Ollama" in event.reason

    def test_log_memory_write_failed(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_memory_write(
            project_id="test-project",
            status=AuditStatus.FAILED,
            category="architecture_notes",
            reason="Database connection failed",
        )

        events = audit_logger.read_recent(1)
        event = events[0]

        assert event.status == AuditStatus.FAILED.value
        assert event.reason == "Database connection failed"


class TestAuditLoggerDelete:
    """Tests for audit logging on delete operations."""

    def test_log_memory_delete(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_memory_delete(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            item_id="chunk-456",
            category="temporary_notes",
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.operation == AuditOperation.MEMORY_DELETE.value
        assert event.status == AuditStatus.SUCCESS.value
        assert event.item_id == "chunk-456"

    def test_log_memory_delete_dry_run(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_memory_delete(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            item_count=5,
            category="temporary_notes",
            dry_run=True,
        )

        events = audit_logger.read_recent(1)
        event = events[0]

        assert event.status == AuditStatus.DRY_RUN.value
        assert event.item_count == 5


class TestAuditLoggerPDFIngest:
    """Tests for audit logging on PDF ingestion."""

    def test_log_pdf_ingest_success(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_pdf_ingest(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            source="/path/to/document.pdf",
            chunk_count=15,
            provider="ollama",
            model="nomic-embed-text",
            metadata={"pages": 10, "title": "Technical Spec"},
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.operation == AuditOperation.PDF_INGEST.value
        assert event.status == AuditStatus.SUCCESS.value
        assert event.source == "/path/to/document.pdf"
        assert event.item_count == 15
        assert event.metadata.get("pages") == 10

    def test_log_pdf_ingest_failure(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_pdf_ingest(
            project_id="test-project",
            status=AuditStatus.FAILED,
            source="/path/to/corrupted.pdf",
            reason="Failed to extract text: PDF is encrypted",
        )

        events = audit_logger.read_recent(1)
        event = events[0]

        assert event.status == AuditStatus.FAILED.value
        assert "encrypted" in event.reason


class TestAuditLoggerPersistence:
    """Tests for audit log file persistence."""

    def test_multiple_events_persisted(self, audit_logger: AuditLogger) -> None:
        for i in range(5):
            audit_logger.log_memory_write(
                project_id=f"project-{i}",
                status=AuditStatus.SUCCESS,
                content=f"Content {i}",
            )

        events = audit_logger.read_recent(10)
        assert len(events) == 5

        # Events should be in reverse chronological order
        assert events[0].project_id == "project-4"
        assert events[4].project_id == "project-0"

    def test_audit_log_file_format(self, audit_logger: AuditLogger) -> None:
        audit_logger.log_memory_write(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            content="Test content",
        )

        # Read the raw file
        content = audit_logger.log_path.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 1

        # Each line should be valid JSON
        data = json.loads(lines[0])
        assert data["project_id"] == "test-project"


class TestAuditLoggerNoSensitiveData:
    """Tests to verify sensitive data is not stored in audit logs."""

    def test_content_not_stored_raw(self, audit_logger: AuditLogger) -> None:
        sensitive_content = "API_KEY=super_secret_key_12345"

        audit_logger.log_memory_write(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            content=sensitive_content,
        )

        # Read the raw file content
        raw_content = audit_logger.log_path.read_text()

        # The raw sensitive content should NOT appear
        assert "super_secret_key" not in raw_content
        assert "API_KEY" not in raw_content

        # But a hash should be present
        events = audit_logger.read_recent(1)
        assert events[0].content_hash is not None
        assert len(events[0].content_hash) == 64  # SHA-256 hash length
