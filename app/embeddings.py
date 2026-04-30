"""Provider-agnostic embedding access.

All indexing and search code should call get_embedding(text) so provider-specific
logic stays isolated in one place.

Warning: embedding vector dimensions depend on the configured provider and model.
Examples include nomic-embed-text = 768, text-embedding-3-small = 1536, and
text-embedding-3-large = 3072. PostgreSQL VECTOR(N) must match the active model
output size. If the provider or model changes later, schema migration and
re-indexing may be required.
"""

from __future__ import annotations

from typing import Any

import requests
from openai import APIConnectionError, APIError, AzureOpenAI, OpenAI

from app.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    OPENAI_API_KEY,
    OLLAMA_BASE_URL,
)
from app.errors import EmbeddingProviderError


def get_embedding(text: str) -> list[float]:
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Cannot generate an embedding for empty text")

    if EMBEDDING_PROVIDER == "ollama":
        embedding = _get_ollama_embedding(normalized_text)
    elif EMBEDDING_PROVIDER == "openai":
        embedding = _get_openai_embedding(normalized_text)
    elif EMBEDDING_PROVIDER == "azure":
        embedding = _get_azure_embedding(normalized_text)
    else:
        raise ValueError(
            "Unsupported EMBEDDING_PROVIDER. Expected one of: ollama, openai, azure"
        )

    _validate_embedding_size(embedding)
    return embedding


def _get_ollama_embedding(text: str) -> list[float]:
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text},
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to connect to Ollama at {OLLAMA_BASE_URL}") from exc

    payload = response.json()
    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError("Ollama response did not contain a valid embedding vector")

    return _coerce_embedding(embedding)


def _get_openai_embedding(text: str) -> list[float]:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    except (APIConnectionError, APIError) as exc:
        raise RuntimeError("Failed to fetch embedding from OpenAI") from exc

    if not response.data:
        raise RuntimeError("OpenAI returned no embedding data")

    return _coerce_embedding(response.data[0].embedding)


def _get_azure_embedding(text: str) -> list[float]:
    if not AZURE_OPENAI_ENDPOINT:
        raise ValueError(
            "AZURE_OPENAI_ENDPOINT is required when EMBEDDING_PROVIDER=azure"
        )
    if not AZURE_OPENAI_API_KEY:
        raise ValueError(
            "AZURE_OPENAI_API_KEY is required when EMBEDDING_PROVIDER=azure"
        )
    if not AZURE_OPENAI_EMBEDDING_DEPLOYMENT:
        raise ValueError(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required when EMBEDDING_PROVIDER=azure"
        )

    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
    )

    try:
        response = client.embeddings.create(
            model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            input=text,
        )
    except (APIConnectionError, APIError) as exc:
        raise RuntimeError("Failed to fetch embedding from Azure OpenAI") from exc

    if not response.data:
        raise RuntimeError("Azure OpenAI returned no embedding data")

    return _coerce_embedding(response.data[0].embedding)


def _coerce_embedding(values: list[Any]) -> list[float]:
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise EmbeddingProviderError("Embedding response contained non-numeric values") from exc


def _validate_embedding_size(embedding: list[float]) -> None:
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise EmbeddingProviderError(
            "Embedding dimension mismatch: "
            f"expected {EMBEDDING_DIMENSIONS}, got {len(embedding)}. "
            "Update EMBEDDING_DIMENSIONS and PostgreSQL VECTOR(N) so they match the active model."
        )