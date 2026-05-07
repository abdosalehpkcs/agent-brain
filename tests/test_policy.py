"""Tests for write policy validation."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest

from app.errors import PolicyError
from app.policy import (
    CategoryPolicy,
    WritePolicy,
    WriteRequest,
    load_policy,
    reset_policy,
    validate_write,
)


@pytest.fixture(autouse=True)
def clean_policy():
    """Reset policy state before and after each test."""
    reset_policy()
    yield
    reset_policy()


class TestPolicyLoading:
    """Tests for policy file loading."""

    def test_load_valid_policy_file(self) -> None:
        policy_content = """
default_allowed: false
require_category: true
categories:
  confirmed_decisions:
    allowed: true
    requires_source: true
    description: "Final decisions"
  temporary_notes:
    allowed: true
    requires_expiry: true
"""
        with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(policy_content)
            f.flush()

            policy = load_policy(f.name)

            assert not policy.default_allowed
            assert policy.require_category
            assert "confirmed_decisions" in policy.categories
            assert "temporary_notes" in policy.categories
            assert policy.categories["confirmed_decisions"].requires_source

    def test_load_missing_policy_file(self) -> None:
        with pytest.raises(PolicyError, match="not found"):
            load_policy("/nonexistent/path/policy.yml")

    def test_load_invalid_yaml(self) -> None:
        with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(PolicyError, match="Invalid YAML"):
                load_policy(f.name)

    def test_load_non_object_yaml(self) -> None:
        with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("- list\n- not\n- object")
            f.flush()

            with pytest.raises(PolicyError, match="must contain a YAML object"):
                load_policy(f.name)

    def test_load_policy_from_default_location(self) -> None:
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # No policy file - should use permissive defaults
                reset_policy()
                policy = load_policy()
                assert policy.default_allowed

                # Create policy file
                policy_path = Path(tmpdir) / "brain-write-policy.yml"
                policy_path.write_text("default_allowed: false\ncategories: {}")

                reset_policy()
                policy = load_policy()
                assert not policy.default_allowed
            finally:
                os.chdir(original_cwd)


class TestAllowedWrites:
    """Tests for allowed write operations."""

    def test_allowed_write_with_valid_category(self) -> None:
        policy = WritePolicy(
            categories={
                "architecture_notes": CategoryPolicy(
                    name="architecture_notes",
                    allowed=True,
                )
            },
            require_category=True,
        )

        request = WriteRequest(category="architecture_notes", content="Test content")
        result = validate_write(request, policy)

        assert result.allowed
        assert result.reason == ""

    def test_allowed_write_with_required_source(self) -> None:
        policy = WritePolicy(
            categories={
                "validated_findings": CategoryPolicy(
                    name="validated_findings",
                    allowed=True,
                    requires_source=True,
                )
            },
        )

        request = WriteRequest(
            category="validated_findings",
            source="user_review",
            content="Finding content",
        )
        result = validate_write(request, policy)

        assert result.allowed

    def test_allowed_write_with_required_context(self) -> None:
        policy = WritePolicy(
            categories={
                "rejected_ideas": CategoryPolicy(
                    name="rejected_ideas",
                    allowed=True,
                    requires_context=True,
                )
            },
        )

        request = WriteRequest(
            category="rejected_ideas",
            context="Sprint planning discussion",
            content="Idea description",
        )
        result = validate_write(request, policy)

        assert result.allowed


class TestBlockedWrites:
    """Tests for blocked write operations."""

    def test_blocked_write_category_not_allowed(self) -> None:
        policy = WritePolicy(
            categories={
                "blocked_category": CategoryPolicy(
                    name="blocked_category",
                    allowed=False,
                    description="This category is disabled",
                )
            },
        )

        request = WriteRequest(category="blocked_category", content="Test")
        result = validate_write(request, policy)

        assert not result.allowed
        assert "not allowed" in result.reason

    def test_blocked_write_overwrite_not_allowed(self) -> None:
        policy = WritePolicy(
            categories={
                "confirmed_decisions": CategoryPolicy(
                    name="confirmed_decisions",
                    allowed=True,
                    allow_overwrite=False,
                )
            },
        )

        request = WriteRequest(
            category="confirmed_decisions",
            is_overwrite=True,
            content="Overwriting decision",
        )
        result = validate_write(request, policy)

        assert not result.allowed
        assert "overwriting" in result.reason.lower()


class TestMissingCategory:
    """Tests for missing category handling."""

    def test_missing_category_when_required(self) -> None:
        policy = WritePolicy(
            categories={},
            require_category=True,
        )

        request = WriteRequest(content="No category specified")
        result = validate_write(request, policy)

        assert not result.allowed
        assert "Category is required" in result.reason

    def test_missing_category_when_not_required_default_allowed(self) -> None:
        policy = WritePolicy(
            categories={},
            require_category=False,
            default_allowed=True,
        )

        request = WriteRequest(content="No category needed")
        result = validate_write(request, policy)

        assert result.allowed

    def test_undefined_category_with_default_disallowed(self) -> None:
        policy = WritePolicy(
            categories={
                "known_category": CategoryPolicy(name="known_category", allowed=True)
            },
            default_allowed=False,
        )

        request = WriteRequest(category="unknown_category", content="Test")
        result = validate_write(request, policy)

        assert not result.allowed
        assert "not defined" in result.reason


class TestMissingSource:
    """Tests for missing source when required."""

    def test_missing_source_when_required(self) -> None:
        policy = WritePolicy(
            categories={
                "validated_findings": CategoryPolicy(
                    name="validated_findings",
                    allowed=True,
                    requires_source=True,
                )
            },
        )

        request = WriteRequest(category="validated_findings", content="Finding")
        result = validate_write(request, policy)

        assert not result.allowed
        assert "requires a source" in result.reason


class TestMissingContext:
    """Tests for missing context when required."""

    def test_missing_context_when_required(self) -> None:
        policy = WritePolicy(
            categories={
                "architecture_notes": CategoryPolicy(
                    name="architecture_notes",
                    allowed=True,
                    requires_context=True,
                )
            },
        )

        request = WriteRequest(category="architecture_notes", content="Note")
        result = validate_write(request, policy)

        assert not result.allowed
        assert "requires context" in result.reason


class TestMissingExpiry:
    """Tests for missing expiry when required."""

    def test_missing_expiry_when_required(self) -> None:
        policy = WritePolicy(
            categories={
                "temporary_notes": CategoryPolicy(
                    name="temporary_notes",
                    allowed=True,
                    requires_expiry=True,
                )
            },
        )

        request = WriteRequest(category="temporary_notes", content="Temp note")
        result = validate_write(request, policy)

        assert not result.allowed
        assert "requires an expiry" in result.reason

    def test_expiry_provided_when_required(self) -> None:
        policy = WritePolicy(
            categories={
                "temporary_notes": CategoryPolicy(
                    name="temporary_notes",
                    allowed=True,
                    requires_expiry=True,
                )
            },
        )

        request = WriteRequest(
            category="temporary_notes",
            expiry="2025-12-31",
            content="Temp note",
        )
        result = validate_write(request, policy)

        assert result.allowed
