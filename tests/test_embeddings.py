from __future__ import annotations

import pytest

from app import embeddings
from app.errors import EmbeddingProviderError


def test_coerce_embedding_numeric_values() -> None:
    values = embeddings._coerce_embedding([1, 2.5, "3.0"])
    assert values == [1.0, 2.5, 3.0]


def test_coerce_embedding_invalid_values() -> None:
    with pytest.raises(EmbeddingProviderError):
        embeddings._coerce_embedding([1, object()])


def test_validate_embedding_size(monkeypatch) -> None:
    monkeypatch.setattr(embeddings, "EMBEDDING_DIMENSIONS", 3)
    embeddings._validate_embedding_size([0.1, 0.2, 0.3])

    with pytest.raises(EmbeddingProviderError):
        embeddings._validate_embedding_size([0.1, 0.2])
