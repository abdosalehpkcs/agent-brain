from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import ProjectResolutionError
from app.project_resolution import discover_project_files, normalize_patterns, resolve_project_root


def test_resolve_project_root_relative(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("id: x", encoding="utf-8")

    project_dir = tmp_path / "projects" / "demo"
    project_dir.mkdir(parents=True)

    root = resolve_project_root("../projects/demo", config_path=config_path)
    assert root == project_dir.resolve()


def test_resolve_project_root_missing_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "project.yaml"
    config_path.write_text("id: x", encoding="utf-8")

    with pytest.raises(ProjectResolutionError):
        resolve_project_root("missing", config_path=config_path)


def test_normalize_patterns_requires_non_empty_include() -> None:
    with pytest.raises(ProjectResolutionError):
        normalize_patterns([], field_name="include", required=True)


def test_discover_project_files_applies_excludes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("print('a')", encoding="utf-8")
    (root / "ignore.py").write_text("print('b')", encoding="utf-8")

    files = discover_project_files(root, ["*.py"], ["ignore.py"])
    assert [path.name for path in files] == ["a.py"]
