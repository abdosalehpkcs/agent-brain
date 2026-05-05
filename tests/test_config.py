from __future__ import annotations

import importlib
import os

import pytest


RELEVANT_ENV = [
    "DATABASE_URL",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "OLLAMA_BASE_URL",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
]


def _reload_config(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> object:
    for key in RELEVANT_ENV:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import app.config as config

    return importlib.reload(config)


def test_default_settings_load(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(monkeypatch, {})
    assert config.EMBEDDING_PROVIDER == "ollama"
    assert config.EMBEDDING_DIMENSIONS == 768


def test_invalid_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(Exception):
        _reload_config(monkeypatch, {"EMBEDDING_PROVIDER": "invalid-provider"})


def test_invalid_dimensions_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(Exception):
        _reload_config(monkeypatch, {"EMBEDDING_DIMENSIONS": "999"})


def test_custom_dimensions_load(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(
        monkeypatch,
        {
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_DIMENSIONS": "1536",
        },
    )
    assert config.EMBEDDING_PROVIDER == "openai"
    assert config.EMBEDDING_DIMENSIONS == 1536


def test_experimental_dimensions_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        config = _reload_config(monkeypatch, {"EMBEDDING_DIMENSIONS": "3072"})
    assert config.EMBEDDING_DIMENSIONS == 3072
    assert any("experimental" in str(w.message).lower() for w in caught)
