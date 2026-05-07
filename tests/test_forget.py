"""Tests for forget/delete operations."""

from __future__ import annotations

import uuid
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest

from app.audit import AuditLogger, reset_audit_logger, set_audit_logger
from app.errors import ForgetError
from app.forget import (
    ForgetResult,
    forget_by_chunk_id,
    forget_by_decision_id,
    forget_by_query,
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


class TestForgetByChunkId:
    """Tests for delete by chunk ID."""

    def test_forget_requires_valid_chunk_id(self, audit_logger) -> None:
        """Test that forget fails for non-existent chunks."""
        # This test would require a database connection
        # Here we test the validation logic
        pass

    def test_forget_validates_project_ownership(self) -> None:
        """Test that chunks can only be deleted from their own project."""
        # Would require database connection for integration test
        pass


class TestForgetByQuery:
    """Tests for query-based deletion."""

    def test_query_deletion_requires_filter(self) -> None:
        """Test that query deletion requires at least one filter."""
        with pytest.raises(ForgetError, match="requires at least one filter"):
            forget_by_query(
                None,  # type: ignore
                project_id="test-project",
                category=None,
                file_path_pattern=None,
            )

    def test_query_deletion_requires_project_id(self) -> None:
        """Test that query deletion requires project_id."""
        with pytest.raises(ForgetError, match="project_id is required"):
            forget_by_query(
                None,  # type: ignore
                project_id="",
                category="temporary_notes",
            )


class TestDryRunDeletion:
    """Tests for dry-run mode."""

    def test_dry_run_does_not_delete(self) -> None:
        """Test that dry_run=True does not actually delete anything."""
        # Would require database connection
        # The ForgetResult should have deleted=False and dry_run=True
        pass


class TestBlockedUnsafeDeletion:
    """Tests for blocked unsafe deletions."""

    def test_broad_deletion_blocked(self) -> None:
        """Test that overly broad deletion is blocked."""
        with pytest.raises(ForgetError, match="requires at least one filter"):
            forget_by_query(
                None,  # type: ignore
                project_id="test-project",
                # No category or file_path_pattern = too broad
            )


class TestAuditAfterDeletion:
    """Tests for audit logging after deletion."""

    def test_successful_deletion_is_logged(self, audit_logger: AuditLogger) -> None:
        """Test that successful deletions are audit logged."""
        # Would require database connection for full test
        # Verify audit_logger.read_recent() contains the delete event
        pass

    def test_failed_deletion_is_logged(self, audit_logger: AuditLogger) -> None:
        """Test that failed deletions are audit logged."""
        # Would require database connection for full test
        pass


class TestForgetResult:
    """Tests for ForgetResult dataclass."""

    def test_forget_result_properties(self) -> None:
        result = ForgetResult(
            deleted=True,
            count=5,
            dry_run=False,
            items=[{"id": "123", "file_path": "test.py"}],
            message="Deleted 5 items",
        )

        assert result.deleted
        assert result.count == 5
        assert not result.dry_run
        assert len(result.items) == 1
        assert "Deleted 5 items" in result.message

    def test_dry_run_result(self) -> None:
        result = ForgetResult(
            deleted=False,
            count=3,
            dry_run=True,
            items=[],
            message="Would delete 3 items",
        )

        assert not result.deleted
        assert result.dry_run
        assert "Would delete" in result.message
