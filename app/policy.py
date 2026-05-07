"""Write policy enforcement for agent-brain memory operations.

This module loads and validates write policies that control what types of
memory can be written, what metadata is required, and whether overwrites
are allowed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.errors import PolicyError


@dataclass(frozen=True)
class CategoryPolicy:
    """Policy rules for a single memory category."""

    name: str
    allowed: bool = True
    requires_source: bool = False
    requires_context: bool = False
    allow_overwrite: bool = True
    requires_expiry: bool = False
    description: str = ""


@dataclass(frozen=True)
class WritePolicy:
    """Container for all category policies and global settings."""

    categories: dict[str, CategoryPolicy] = field(default_factory=dict)
    default_allowed: bool = False
    require_category: bool = True

    def get_category(self, name: str) -> CategoryPolicy | None:
        """Return the policy for a category, or None if not defined."""
        return self.categories.get(name)

    def is_category_allowed(self, name: str) -> bool:
        """Check if a category is allowed for writes."""
        policy = self.get_category(name)
        if policy is None:
            return self.default_allowed
        return policy.allowed


# Global policy instance, loaded once at startup
_active_policy: WritePolicy | None = None


def load_policy(config_path: Path | str | None = None) -> WritePolicy:
    """Load write policy from a YAML file.

    Args:
        config_path: Path to the policy YAML file. If None, looks for
            brain-write-policy.yml in the current directory and common
            config locations.

    Returns:
        WritePolicy instance with loaded categories.

    Raises:
        PolicyError: If the policy file is invalid or cannot be parsed.
    """
    global _active_policy

    if config_path is None:
        config_path = _find_policy_file()

    if config_path is None:
        # No policy file found; use permissive defaults
        _active_policy = _default_policy()
        return _active_policy

    path = Path(config_path)
    if not path.exists():
        raise PolicyError(f"Policy file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise PolicyError(f"Invalid YAML in policy file: {exc}") from exc

    if not isinstance(data, dict):
        raise PolicyError("Policy file must contain a YAML object")

    _active_policy = _parse_policy(data)
    return _active_policy


def _find_policy_file() -> Path | None:
    """Search for the policy file in standard locations."""
    search_paths = [
        Path("brain-write-policy.yml"),
        Path("brain-write-policy.yaml"),
        Path.cwd() / "brain-write-policy.yml",
        Path.cwd() / "brain-write-policy.yaml",
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def _default_policy() -> WritePolicy:
    """Return a permissive default policy when no config file exists."""
    return WritePolicy(
        categories={},
        default_allowed=True,
        require_category=False,
    )


def _parse_policy(data: dict[str, Any]) -> WritePolicy:
    """Parse raw YAML data into a WritePolicy."""
    categories: dict[str, CategoryPolicy] = {}

    raw_categories = data.get("categories", {})
    if not isinstance(raw_categories, dict):
        raise PolicyError("'categories' must be a mapping")

    for name, rules in raw_categories.items():
        if not isinstance(name, str):
            raise PolicyError(f"Category name must be a string, got: {type(name)}")

        if not isinstance(rules, dict):
            raise PolicyError(f"Category '{name}' rules must be a mapping")

        categories[name] = CategoryPolicy(
            name=name,
            allowed=bool(rules.get("allowed", True)),
            requires_source=bool(rules.get("requires_source", False)),
            requires_context=bool(rules.get("requires_context", False)),
            allow_overwrite=bool(rules.get("allow_overwrite", True)),
            requires_expiry=bool(rules.get("requires_expiry", False)),
            description=str(rules.get("description", "")),
        )

    return WritePolicy(
        categories=categories,
        default_allowed=bool(data.get("default_allowed", False)),
        require_category=bool(data.get("require_category", True)),
    )


def get_policy() -> WritePolicy:
    """Return the active policy, loading from default location if needed."""
    global _active_policy
    if _active_policy is None:
        load_policy()
    return _active_policy  # type: ignore[return-value]


def reset_policy() -> None:
    """Reset the cached policy (useful for testing)."""
    global _active_policy
    _active_policy = None


@dataclass(frozen=True)
class WriteRequest:
    """Represents a memory write request to be validated."""

    category: str | None = None
    source: str | None = None
    context: str | None = None
    expiry: str | None = None
    is_overwrite: bool = False
    content: str = ""


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a write request against policy."""

    allowed: bool
    reason: str = ""
    category_policy: CategoryPolicy | None = None


def validate_write(request: WriteRequest, policy: WritePolicy | None = None) -> ValidationResult:
    """Validate a write request against the active policy.

    Args:
        request: The write request to validate.
        policy: Optional policy to use. If None, uses the active policy.

    Returns:
        ValidationResult indicating whether the write is allowed.
    """
    if policy is None:
        policy = get_policy()

    # Check if category is required
    if policy.require_category and not request.category:
        return ValidationResult(
            allowed=False,
            reason="Category is required by policy but not provided",
        )

    # If no category provided and not required, allow by default setting
    if not request.category:
        return ValidationResult(
            allowed=policy.default_allowed,
            reason="" if policy.default_allowed else "No category provided and default_allowed is false",
        )

    # Look up category policy
    category_policy = policy.get_category(request.category)

    if category_policy is None:
        if not policy.default_allowed:
            return ValidationResult(
                allowed=False,
                reason=f"Category '{request.category}' is not defined in policy",
            )
        return ValidationResult(allowed=True)

    # Check if category is allowed
    if not category_policy.allowed:
        return ValidationResult(
            allowed=False,
            reason=f"Category '{request.category}' is not allowed: {category_policy.description}",
            category_policy=category_policy,
        )

    # Check required fields
    if category_policy.requires_source and not request.source:
        return ValidationResult(
            allowed=False,
            reason=f"Category '{request.category}' requires a source to be specified",
            category_policy=category_policy,
        )

    if category_policy.requires_context and not request.context:
        return ValidationResult(
            allowed=False,
            reason=f"Category '{request.category}' requires context to be specified",
            category_policy=category_policy,
        )

    if category_policy.requires_expiry and not request.expiry:
        return ValidationResult(
            allowed=False,
            reason=f"Category '{request.category}' requires an expiry to be specified",
            category_policy=category_policy,
        )

    # Check overwrite permission
    if request.is_overwrite and not category_policy.allow_overwrite:
        return ValidationResult(
            allowed=False,
            reason=f"Category '{request.category}' does not allow overwriting existing memories",
            category_policy=category_policy,
        )

    return ValidationResult(
        allowed=True,
        category_policy=category_policy,
    )


def content_hash(content: str) -> str:
    """Generate a SHA-256 hash of content for audit logging."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
