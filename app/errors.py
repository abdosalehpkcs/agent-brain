"""Domain exceptions for the agent-brain backend.

All custom exceptions derive from AgentBrainError so callers can catch
the whole hierarchy or individual subtypes as needed.
"""

from __future__ import annotations


class AgentBrainError(Exception):
    """Base class for all agent-brain errors."""


class ConfigError(AgentBrainError):
    """Raised when configuration is invalid or incomplete."""


class DatabaseError(AgentBrainError):
    """Raised when a database operation fails."""


class EmbeddingProviderError(AgentBrainError):
    """Raised when an embedding provider call fails or returns invalid data."""


class VectorStoreError(AgentBrainError):
    """Raised when a vector-store operation fails."""


class IndexerError(AgentBrainError):
    """Raised when the indexer encounters an unrecoverable error."""


class SearchError(AgentBrainError):
    """Raised when a search operation fails."""


class DecisionMemoryError(AgentBrainError):
    """Raised when a decision memory operation fails validation or I/O."""


class ProjectResolutionError(AgentBrainError):
    """Raised when a project config cannot be resolved to a valid path."""


class MCPServerError(AgentBrainError):
    """Raised when the MCP server encounters a startup or tool error."""
