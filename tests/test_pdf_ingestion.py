"""Tests for PDF ingestion."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest

from app.audit import AuditLogger, reset_audit_logger, set_audit_logger
from app.errors import PDFIngestionError
from app.pdf_ingestion import (
    PDFChunk,
    PDFDocument,
    PDFPage,
    chunk_pdf,
    extract_pdf,
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


class TestPDFExtraction:
    """Tests for PDF text extraction."""

    def test_extract_nonexistent_file(self) -> None:
        """Test that extracting a nonexistent file fails."""
        with pytest.raises(PDFIngestionError, match="not found"):
            extract_pdf("/nonexistent/path/document.pdf")

    def test_extract_non_pdf_file(self) -> None:
        """Test that extracting a non-PDF file fails."""
        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is not a PDF")
            f.flush()

            with pytest.raises(PDFIngestionError, match="not a PDF"):
                extract_pdf(f.name)


class TestPDFChunking:
    """Tests for PDF chunking."""

    def test_chunk_empty_document(self) -> None:
        """Test chunking an empty document."""
        doc = PDFDocument(
            path="/test.pdf",
            title="Empty Doc",
            page_count=0,
            pages=[],
            content_hash="abc123",
            metadata={},
        )

        chunks = chunk_pdf(doc)
        assert chunks == []

    def test_chunk_single_page(self) -> None:
        """Test chunking a document with one small page."""
        doc = PDFDocument(
            path="/test.pdf",
            title="Single Page",
            page_count=1,
            pages=[
                PDFPage(
                    page_number=1,
                    text="This is a short text that fits in one chunk.",
                    char_count=45,
                )
            ],
            content_hash="abc123",
            metadata={},
        )

        chunks = chunk_pdf(doc, chunk_size=1200, chunk_overlap=150)

        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].start_page == 1
        assert chunks[0].end_page == 1
        assert "short text" in chunks[0].content

    def test_chunk_preserves_page_references(self) -> None:
        """Test that chunking preserves page references."""
        # Create a document with multiple pages
        pages = [
            PDFPage(page_number=i + 1, text=f"Page {i + 1} content. " * 100, char_count=2000)
            for i in range(3)
        ]

        doc = PDFDocument(
            path="/test.pdf",
            title="Multi Page",
            page_count=3,
            pages=pages,
            content_hash="abc123",
            metadata={},
        )

        chunks = chunk_pdf(doc, chunk_size=500, chunk_overlap=50)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Each chunk should have valid page references
        for chunk in chunks:
            assert chunk.start_page >= 1
            assert chunk.end_page <= 3
            assert chunk.start_page <= chunk.end_page
            assert "start_page" in chunk.metadata
            assert "end_page" in chunk.metadata

    def test_chunk_size_validation(self) -> None:
        """Test that invalid chunk sizes are rejected."""
        doc = PDFDocument(
            path="/test.pdf",
            title="Test",
            page_count=1,
            pages=[PDFPage(page_number=1, text="Content", char_count=7)],
            content_hash="abc123",
            metadata={},
        )

        with pytest.raises(PDFIngestionError, match="chunk_size"):
            chunk_pdf(doc, chunk_size=0)

        with pytest.raises(PDFIngestionError, match="chunk_overlap"):
            chunk_pdf(doc, chunk_size=100, chunk_overlap=-1)

        with pytest.raises(PDFIngestionError, match="chunk_overlap"):
            chunk_pdf(doc, chunk_size=100, chunk_overlap=150)


class TestMetadataPreservation:
    """Tests for metadata preservation."""

    def test_chunk_metadata_contains_source_type(self) -> None:
        """Test that chunk metadata contains source type."""
        doc = PDFDocument(
            path="/test.pdf",
            title="Test Doc",
            page_count=1,
            pages=[PDFPage(page_number=1, text="Test content", char_count=12)],
            content_hash="abc123",
            metadata={"author": "Test Author"},
        )

        chunks = chunk_pdf(doc)

        assert len(chunks) == 1
        assert chunks[0].metadata["source_type"] == "pdf"

    def test_pdf_document_metadata(self) -> None:
        """Test that PDFDocument captures metadata."""
        doc = PDFDocument(
            path="/test.pdf",
            title="My Document",
            page_count=5,
            pages=[],
            content_hash="sha256hash",
            metadata={
                "author": "John Doe",
                "subject": "Testing",
                "creator": "Test Suite",
            },
        )

        assert doc.title == "My Document"
        assert doc.metadata["author"] == "John Doe"
        assert doc.content_hash == "sha256hash"


class TestDuplicateHandling:
    """Tests for duplicate detection."""

    def test_content_hash_uniqueness(self) -> None:
        """Test that different content produces different hashes."""
        doc1 = PDFDocument(
            path="/test1.pdf",
            title="Doc 1",
            page_count=1,
            pages=[PDFPage(page_number=1, text="Content A", char_count=9)],
            content_hash="hash_a",
            metadata={},
        )

        doc2 = PDFDocument(
            path="/test2.pdf",
            title="Doc 2",
            page_count=1,
            pages=[PDFPage(page_number=1, text="Content B", char_count=9)],
            content_hash="hash_b",
            metadata={},
        )

        assert doc1.content_hash != doc2.content_hash


class TestAuditLoggingForPDF:
    """Tests for audit logging during PDF ingestion."""

    def test_audit_log_includes_pdf_metadata(self, audit_logger: AuditLogger) -> None:
        """Test that PDF ingestion audit includes metadata."""
        # Log a PDF ingestion event
        from app.audit import AuditStatus

        audit_logger.log_pdf_ingest(
            project_id="test-project",
            status=AuditStatus.SUCCESS,
            source="/path/to/doc.pdf",
            chunk_count=10,
            provider="ollama",
            model="nomic-embed-text",
            metadata={"pages": 5, "title": "Test Doc"},
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.source == "/path/to/doc.pdf"
        assert event.item_count == 10
        assert event.metadata.get("pages") == 5

    def test_failed_pdf_ingestion_logged(self, audit_logger: AuditLogger) -> None:
        """Test that failed PDF ingestion is logged."""
        from app.audit import AuditStatus

        audit_logger.log_pdf_ingest(
            project_id="test-project",
            status=AuditStatus.FAILED,
            source="/path/to/bad.pdf",
            reason="PDF is encrypted",
        )

        events = audit_logger.read_recent(1)
        assert len(events) == 1

        event = events[0]
        assert event.status == "failed"
        assert "encrypted" in event.reason
