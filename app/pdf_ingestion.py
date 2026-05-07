"""PDF ingestion pipeline for agent-brain.

This module provides PDF text extraction, chunking, and ingestion into the
memory system with proper metadata preservation and duplicate detection.

Uses pypdf for extraction (already in requirements.txt).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.audit import AuditStatus, get_audit_logger
from app.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, EMBEDDING_PROVIDER
from app.embeddings import get_embedding
from app.errors import PDFIngestionError
from app.indexer import index_chunk
from app.policy import WriteRequest, get_policy, validate_write
from app.vector_store import upsert_embedding


@dataclass(frozen=True)
class PDFPage:
    """Represents a single page extracted from a PDF."""

    page_number: int  # 1-indexed
    text: str
    char_count: int


@dataclass(frozen=True)
class PDFChunk:
    """Represents a chunk of text from a PDF."""

    chunk_index: int
    content: str
    start_page: int
    end_page: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PDFDocument:
    """Represents an extracted PDF document."""

    path: str
    title: str | None
    page_count: int
    pages: list[PDFPage]
    content_hash: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IngestionResult:
    """Result of a PDF ingestion operation."""

    success: bool
    document_id: UUID | None
    chunk_count: int
    pages_processed: int
    message: str
    skipped: bool = False


def extract_pdf(file_path: Path | str) -> PDFDocument:
    """Extract text and metadata from a PDF file.

    Args:
        file_path: Path to the PDF file.

    Returns:
        PDFDocument containing extracted text and metadata.

    Raises:
        PDFIngestionError: If the file cannot be read or parsed.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PDFIngestionError(
            "pypdf is required for PDF ingestion. Install it with: pip install pypdf"
        ) from exc

    path = Path(file_path)

    if not path.exists():
        raise PDFIngestionError(f"PDF file not found: {path}")

    if not path.suffix.lower() == ".pdf":
        raise PDFIngestionError(f"File is not a PDF: {path}")

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise PDFIngestionError(f"Failed to read PDF: {exc}") from exc

    pages: list[PDFPage] = []
    all_text_parts: list[str] = []

    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        pages.append(
            PDFPage(
                page_number=i + 1,
                text=text,
                char_count=len(text),
            )
        )
        all_text_parts.append(text)

    # Compute content hash from all text
    all_text = "\n".join(all_text_parts)
    content_hash = hashlib.sha256(all_text.encode("utf-8")).hexdigest()

    # Extract metadata
    pdf_metadata = reader.metadata or {}
    title = pdf_metadata.get("/Title", path.stem)

    return PDFDocument(
        path=str(path.absolute()),
        title=title,
        page_count=len(pages),
        pages=pages,
        content_hash=content_hash,
        metadata={
            "author": pdf_metadata.get("/Author"),
            "subject": pdf_metadata.get("/Subject"),
            "creator": pdf_metadata.get("/Creator"),
            "producer": pdf_metadata.get("/Producer"),
            "creation_date": str(pdf_metadata.get("/CreationDate", "")),
        },
    )


def chunk_pdf(
    document: PDFDocument,
    chunk_size: int = 1200,
    chunk_overlap: int = 150,
) -> list[PDFChunk]:
    """Split PDF content into chunks with page reference preservation.

    Args:
        document: Extracted PDF document.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between chunks.

    Returns:
        List of PDFChunk objects with page references.
    """
    if chunk_size <= 0:
        raise PDFIngestionError("chunk_size must be greater than zero")

    if chunk_overlap < 0:
        raise PDFIngestionError("chunk_overlap cannot be negative")

    if chunk_overlap >= chunk_size:
        raise PDFIngestionError("chunk_overlap must be less than chunk_size")

    chunks: list[PDFChunk] = []
    current_text = ""
    current_start_page = 1
    chunk_index = 0

    for page in document.pages:
        # Add page text with page marker
        page_text = page.text.strip()
        if not page_text:
            continue

        current_text += page_text + "\n"

        # Check if we need to emit chunks
        while len(current_text) >= chunk_size:
            # Find a good break point (end of sentence or paragraph)
            break_point = _find_break_point(current_text, chunk_size)

            chunk_content = current_text[:break_point].strip()
            if chunk_content:
                chunks.append(
                    PDFChunk(
                        chunk_index=chunk_index,
                        content=chunk_content,
                        start_page=current_start_page,
                        end_page=page.page_number,
                        metadata={
                            "source_type": "pdf",
                            "start_page": current_start_page,
                            "end_page": page.page_number,
                        },
                    )
                )
                chunk_index += 1

            # Keep overlap for context
            if len(current_text) > break_point:
                overlap_start = max(0, break_point - chunk_overlap)
                current_text = current_text[overlap_start:]
                current_start_page = page.page_number
            else:
                current_text = ""
                current_start_page = page.page_number + 1

    # Handle remaining text
    remaining = current_text.strip()
    if remaining:
        chunks.append(
            PDFChunk(
                chunk_index=chunk_index,
                content=remaining,
                start_page=current_start_page,
                end_page=document.page_count,
                metadata={
                    "source_type": "pdf",
                    "start_page": current_start_page,
                    "end_page": document.page_count,
                },
            )
        )

    return chunks


def _find_break_point(text: str, max_length: int) -> int:
    """Find a good break point in text, preferring sentence/paragraph boundaries."""
    if len(text) <= max_length:
        return len(text)

    # Look for paragraph break
    for i in range(max_length, max(max_length - 200, 0), -1):
        if text[i : i + 2] == "\n\n":
            return i + 2

    # Look for sentence end
    for i in range(max_length, max(max_length - 100, 0), -1):
        if text[i] in ".!?" and (i + 1 >= len(text) or text[i + 1] in " \n"):
            return i + 1

    # Look for any newline
    for i in range(max_length, max(max_length - 50, 0), -1):
        if text[i] == "\n":
            return i + 1

    # Fall back to word boundary
    for i in range(max_length, max(max_length - 30, 0), -1):
        if text[i] == " ":
            return i + 1

    # Last resort: hard break
    return max_length


def check_duplicate(
    conn: Connection,
    *,
    project_id: str,
    content_hash: str,
) -> UUID | None:
    """Check if a document with the same content hash already exists.

    Returns the document ID if a duplicate is found, None otherwise.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id FROM documents
            WHERE project_id = %s AND content_hash = %s
            """,
            (project_id, content_hash),
        )
        row = cur.fetchone()

    return row["id"] if row else None


def ingest_pdf(
    conn: Connection,
    *,
    file_path: Path | str,
    project_id: str,
    source: str = "pdf_ingestion",
    chunk_size: int = 1200,
    chunk_overlap: int = 150,
    skip_duplicates: bool = True,
    category: str = "pdf_content",
) -> IngestionResult:
    """Ingest a PDF file into the memory system.

    This function:
    1. Extracts text from the PDF
    2. Checks write policy
    3. Checks for duplicates
    4. Chunks the content with page references
    5. Stores chunks with embeddings
    6. Logs the operation to audit

    Args:
        conn: Database connection.
        file_path: Path to the PDF file.
        project_id: Target project ID.
        source: Source identifier for audit logging.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between chunks.
        skip_duplicates: If True, skip files with matching content hash.
        category: Memory category for write policy.

    Returns:
        IngestionResult with ingestion details.

    Raises:
        PDFIngestionError: If extraction or ingestion fails.
        PolicyError: If the write is blocked by policy.
    """
    audit = get_audit_logger()
    path = Path(file_path)

    # Validate write policy
    policy = get_policy()
    request = WriteRequest(
        category=category,
        source=source,
        content="",  # We don't validate content for PDFs
    )
    validation = validate_write(request, policy)

    if not validation.allowed:
        audit.log_policy_blocked(
            project_id=project_id,
            category=category,
            source=source,
            reason=validation.reason,
        )
        raise PDFIngestionError(f"Write blocked by policy: {validation.reason}")

    # Extract PDF
    try:
        document = extract_pdf(path)
    except PDFIngestionError as exc:
        audit.log_pdf_ingest(
            project_id=project_id,
            status=AuditStatus.FAILED,
            source=str(path),
            reason=str(exc),
        )
        raise

    # Check for duplicates
    if skip_duplicates:
        existing_id = check_duplicate(
            conn,
            project_id=project_id,
            content_hash=document.content_hash,
        )
        if existing_id:
            audit.log_pdf_ingest(
                project_id=project_id,
                status=AuditStatus.SUCCESS,
                source=str(path),
                reason="Skipped: duplicate content",
                metadata={"existing_document_id": str(existing_id)},
            )
            return IngestionResult(
                success=True,
                document_id=existing_id,
                chunk_count=0,
                pages_processed=document.page_count,
                message=f"Skipped: duplicate of document {existing_id}",
                skipped=True,
            )

    # Create document record
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO documents (
                project_id,
                source_type,
                path,
                title,
                content_hash,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                project_id,
                "pdf",
                str(path.absolute()),
                document.title,
                document.content_hash,
                Json(document.metadata),
            ),
        )
        row = cur.fetchone()
        document_id = row["id"]

    # Chunk the PDF
    chunks = chunk_pdf(document, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # Store chunks with embeddings
    chunk_count = 0
    for chunk in chunks:
        try:
            index_chunk(
                conn,
                project_id=project_id,
                document_id=document_id,
                file_path=str(path),
                chunk_index=chunk.chunk_index,
                chunk_type=category,
                content=chunk.content,
                metadata=chunk.metadata,
            )
            chunk_count += 1
        except Exception as exc:
            audit.log_embedding_failure(
                project_id=project_id,
                reason=str(exc),
                provider=EMBEDDING_PROVIDER,
                model=EMBEDDING_MODEL,
                source=str(path),
            )
            # Continue with other chunks

    conn.commit()

    audit.log_pdf_ingest(
        project_id=project_id,
        status=AuditStatus.SUCCESS,
        source=str(path),
        chunk_count=chunk_count,
        provider=EMBEDDING_PROVIDER,
        model=EMBEDDING_MODEL,
        metadata={
            "document_id": str(document_id),
            "page_count": document.page_count,
            "title": document.title,
        },
    )

    return IngestionResult(
        success=True,
        document_id=document_id,
        chunk_count=chunk_count,
        pages_processed=document.page_count,
        message=f"Ingested {chunk_count} chunks from {document.page_count} pages",
    )


def ingest_pdf_cli() -> None:
    """CLI entry point for PDF ingestion."""
    import argparse

    from psycopg import connect

    from app.config import DATABASE_URL

    parser = argparse.ArgumentParser(description="Ingest a PDF into agent-brain")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("project_id", help="Target project ID")
    parser.add_argument("--chunk-size", type=int, default=1200, help="Chunk size")
    parser.add_argument("--chunk-overlap", type=int, default=150, help="Chunk overlap")
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow ingesting duplicate PDFs",
    )

    args = parser.parse_args()

    with connect(DATABASE_URL) as conn:
        result = ingest_pdf(
            conn,
            file_path=args.pdf_path,
            project_id=args.project_id,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            skip_duplicates=not args.allow_duplicates,
        )

    if result.skipped:
        print(f"Skipped: {result.message}")
    elif result.success:
        print(f"Success: {result.message}")
        print(f"Document ID: {result.document_id}")
    else:
        print(f"Failed: {result.message}")


if __name__ == "__main__":
    ingest_pdf_cli()
