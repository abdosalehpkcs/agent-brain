from __future__ import annotations

import pytest

from app.errors import VectorStoreError
from app.vector_store import (
    EmbeddingStatus,
    get_embedding_table,
    is_ann_indexed_dimension,
    search_embeddings,
    upsert_embedding,
)


def test_get_embedding_table_supported() -> None:
    assert get_embedding_table(768) == "chunk_embeddings_768"
    assert get_embedding_table(1536) == "chunk_embeddings_1536"
    assert get_embedding_table(3072) == "chunk_embeddings_3072"


def test_get_embedding_table_unsupported_raises() -> None:
    with pytest.raises(VectorStoreError):
        get_embedding_table(42)


def test_ann_indexed_dimension_policy() -> None:
    assert is_ann_indexed_dimension(768) is True
    assert is_ann_indexed_dimension(1536) is True
    assert is_ann_indexed_dimension(3072) is False


def test_search_embeddings_validation_errors() -> None:
    with pytest.raises(VectorStoreError):
        search_embeddings(None, query_embedding=[], project_id="p", provider="a", model="m")

    with pytest.raises(VectorStoreError):
        search_embeddings(
            None,
            query_embedding=[0.1] * 768,
            project_id="p",
            provider="a",
            model="m",
            limit=0,
        )


def test_upsert_embedding_empty_vector_raises() -> None:
    with pytest.raises(VectorStoreError):
        upsert_embedding(
            None,
            chunk_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            project_id="p",
            provider="a",
            model="m",
            embedding=[],
        )


def test_embedding_status_dataclass() -> None:
    status = EmbeddingStatus(
        project_id="p",
        provider="ollama",
        model="nomic-embed-text",
        dimensions=768,
        indexed=True,
        chunk_count=10,
        embedding_count=8,
        missing_count=2,
    )
    assert status.indexed is True
    assert status.missing_count == 2


def test_get_embedding_status_empty_project_raises() -> None:
    with pytest.raises(VectorStoreError):
        from app.vector_store import get_embedding_status

        get_embedding_status(None, project_id="  ")  # type: ignore[arg-type]
