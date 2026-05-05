"""Configuration loading for the agent memory backend."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Dimensions that have ivfflat ANN indexes and are fully supported.
SUPPORTED_DIMENSIONS: frozenset[int] = frozenset({768, 1536})

# 3072 is stored but uses exact scan — treat as experimental.
EXPERIMENTAL_DIMENSIONS: frozenset[int] = frozenset({3072})

# Union of both for table lookup.
ALL_KNOWN_DIMENSIONS: frozenset[int] = SUPPORTED_DIMENSIONS | EXPERIMENTAL_DIMENSIONS

SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"ollama", "openai", "azure"})


load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_int_env(name: str) -> int:
    raw_value = _require_env(name)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc

    if value <= 0:
        raise ValueError(f"Environment variable {name} must be greater than zero")

    return value


def _get_int_env_with_default(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc

    if value <= 0:
        raise ValueError(f"Environment variable {name} must be greater than zero")

    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    ollama_base_url: str
    openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str
    azure_openai_embedding_deployment: str


def load_settings() -> Settings:
    provider = _get_env("EMBEDDING_PROVIDER", "ollama").lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER '{provider}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )

    dimensions = _get_int_env_with_default("EMBEDDING_DIMENSIONS", 768)
    if dimensions not in ALL_KNOWN_DIMENSIONS:
        raise ValueError(
            f"Unsupported EMBEDDING_DIMENSIONS {dimensions}. "
            f"Supported: {', '.join(str(d) for d in sorted(SUPPORTED_DIMENSIONS))}. "
            f"Experimental: {', '.join(str(d) for d in sorted(EXPERIMENTAL_DIMENSIONS))}."
        )

    if dimensions in EXPERIMENTAL_DIMENSIONS:
        import warnings
        warnings.warn(
            f"EMBEDDING_DIMENSIONS={dimensions} is experimental. "
            "No ANN index is available; searches use exact scan.",
            stacklevel=2,
        )

    return Settings(
        database_url=_get_env(
            "DATABASE_URL",
            "postgresql://agent:agentpass@localhost:5432/agent_memory",
        ),
        embedding_provider=provider,
        embedding_model=_get_env("EMBEDDING_MODEL", "nomic-embed-text"),
        embedding_dimensions=dimensions,
        ollama_base_url=_get_env("OLLAMA_BASE_URL", "http://localhost:11434"),
        openai_api_key=_get_env("OPENAI_API_KEY"),
        azure_openai_endpoint=_get_env("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_key=_get_env("AZURE_OPENAI_API_KEY"),
        azure_openai_api_version=_get_env("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_openai_embedding_deployment=_get_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    )


settings = load_settings()

DATABASE_URL = settings.database_url
EMBEDDING_PROVIDER = settings.embedding_provider
EMBEDDING_MODEL = settings.embedding_model
EMBEDDING_DIMENSIONS = settings.embedding_dimensions
OLLAMA_BASE_URL = settings.ollama_base_url
OPENAI_API_KEY = settings.openai_api_key
AZURE_OPENAI_ENDPOINT = settings.azure_openai_endpoint
AZURE_OPENAI_API_KEY = settings.azure_openai_api_key
AZURE_OPENAI_API_VERSION = settings.azure_openai_api_version
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = settings.azure_openai_embedding_deployment