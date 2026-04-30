from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app import search


@dataclass(frozen=True)
class FakeChunk:
    chunk_id: object
    project_id: str
    document_id: object
    file_path: str
    chunk_index: int
    chunk_type: str | None
    content: str
    metadata: dict
    provider: str
    model: str
    distance: float


def test_search_project_chunks_calls_vector_search(monkeypatch) -> None:
    expected = [
        FakeChunk(
            chunk_id=uuid4(),
            project_id="p",
            document_id=uuid4(),
            file_path="a.md",
            chunk_index=0,
            chunk_type="text",
            content="hello",
            metadata={},
            provider="ollama",
            model="nomic-embed-text",
            distance=0.1,
        )
    ]

    monkeypatch.setattr(search, "EMBEDDING_DIMENSIONS", 768)
    monkeypatch.setattr(search, "get_embedding", lambda _text: [0.1] * 768)
    monkeypatch.setattr(search, "search_embeddings", lambda *args, **kwargs: expected)

    chunks = search.search_project_chunks(None, project_id="p", query_text="hello")  # type: ignore[arg-type]
    assert chunks == expected


def test_search_project_memory_includes_decisions(monkeypatch) -> None:
    monkeypatch.setattr(search, "search_project_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(search, "list_project_decisions", lambda *args, **kwargs: ["d1", "d2"])

    chunks, decisions = search.search_project_memory(
        None,  # type: ignore[arg-type]
        project_id="p",
        query_text="q",
        include_decisions=True,
    )
    assert chunks == []
    assert decisions == ["d1", "d2"]
