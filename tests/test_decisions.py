from __future__ import annotations

import uuid

import pytest

from app.decisions import add_decision, list_project_decisions, update_decision_status
from app.errors import DecisionMemoryError


def test_add_decision_requires_fields() -> None:
    with pytest.raises(DecisionMemoryError):
        add_decision(None, project_id="", title="t", decision="d")  # type: ignore[arg-type]

    with pytest.raises(DecisionMemoryError):
        add_decision(None, project_id="p", title="", decision="d")  # type: ignore[arg-type]

    with pytest.raises(DecisionMemoryError):
        add_decision(None, project_id="p", title="t", decision="")  # type: ignore[arg-type]


def test_list_decisions_validates_inputs() -> None:
    with pytest.raises(DecisionMemoryError):
        list_project_decisions(None, project_id="", limit=10)  # type: ignore[arg-type]

    with pytest.raises(DecisionMemoryError):
        list_project_decisions(None, project_id="p", limit=0)  # type: ignore[arg-type]


def test_update_decision_status_requires_non_empty_status() -> None:
    with pytest.raises(DecisionMemoryError):
        update_decision_status(
            None,  # type: ignore[arg-type]
            decision_id=uuid.uuid4(),
            status="   ",
        )
