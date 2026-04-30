"""Project config path resolution and file discovery helpers."""

from __future__ import annotations

from pathlib import Path

from app.errors import ProjectResolutionError


def resolve_project_root(root_path_raw: str, *, config_path: Path) -> Path:
    """Resolve *root_path_raw* relative to *config_path*'s parent directory.

    Returns the resolved absolute Path. Raises ProjectResolutionError if the
    resulting path does not exist.
    """
    root = Path(root_path_raw)
    if not root.is_absolute():
        root = (config_path.parent / root).resolve()
    else:
        root = root.resolve()

    if not root.exists():
        raise ProjectResolutionError(
            f"Project root '{root}' does not exist (resolved from '{root_path_raw}' "
            f"relative to config '{config_path}')."
        )
    return root


def normalize_patterns(
    value: list[str],
    *,
    field_name: str,
    required: bool,
) -> list[str]:
    """Validate and normalize a list of glob patterns.

    Raises ProjectResolutionError when *required* is True and the list is empty.
    """
    patterns = [p.strip() for p in (value or []) if p.strip()]
    if required and not patterns:
        raise ProjectResolutionError(
            f"'{field_name}' must contain at least one non-empty pattern."
        )
    return patterns


def discover_project_files(
    root_path: Path,
    include: list[str],
    exclude: list[str],
) -> list[Path]:
    """Return a sorted list of files matching *include* patterns minus *exclude* patterns."""
    excluded: set[Path] = set()
    for pattern in exclude:
        excluded.update(root_path.glob(pattern))

    matched: list[Path] = []
    for pattern in include:
        for path in root_path.glob(pattern):
            if path.is_file() and path not in excluded:
                matched.append(path)

    return sorted(set(matched))
