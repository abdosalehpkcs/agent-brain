from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import patch

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


def _reload_config_with_env(env: dict[str, str]) -> object:
    """Reload config module with controlled environment variables.
    
    This directly manipulates os.environ and patches load_dotenv to prevent
    it from loading the actual .env file, ensuring tests run with predictable
    environment regardless of local config.
    """
    # Save original env vars
    original_env = {k: os.environ.get(k) for k in RELEVANT_ENV}
    
    try:
        # Clear all relevant env vars
        for key in RELEVANT_ENV:
            os.environ.pop(key, None)
        
        # Set the test env vars
        for key, value in env.items():
            os.environ[key] = value

        # Remove the config module from cache so it gets freshly imported
        # with our patched load_dotenv
        if "app.config" in sys.modules:
            del sys.modules["app.config"]

        # Patch dotenv.load_dotenv BEFORE importing the config module
        # This ensures the `from dotenv import load_dotenv` gets the mocked version
        with patch("dotenv.load_dotenv"):
            import app.config as config
            return config
    finally:
        # Restore original env vars
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


def test_default_settings_load() -> None:
    """Test that default settings are used when no env vars are set."""
    config = _reload_config_with_env({})
    assert config.EMBEDDING_PROVIDER == "ollama"
    assert config.EMBEDDING_DIMENSIONS == 768


def test_invalid_provider_raises() -> None:
    with pytest.raises(Exception):
        _reload_config_with_env({"EMBEDDING_PROVIDER": "invalid-provider"})


def test_invalid_dimensions_raises() -> None:
    with pytest.raises(Exception):
        _reload_config_with_env({"EMBEDDING_DIMENSIONS": "999"})


def test_custom_dimensions_load() -> None:
    config = _reload_config_with_env(
        {
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_DIMENSIONS": "1536",
        },
    )
    assert config.EMBEDDING_PROVIDER == "openai"
    assert config.EMBEDDING_DIMENSIONS == 1536


def test_experimental_dimensions_warns() -> None:
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        config = _reload_config_with_env({"EMBEDDING_DIMENSIONS": "3072"})
    assert config.EMBEDDING_DIMENSIONS == 3072
    assert any("experimental" in str(w.message).lower() for w in caught)
