# Project Resolution

agent-brain indexes projects from YAML config files.

## Required fields

- id
- name
- type (coding or research)
- root_path
- include (non-empty list)

## Path behavior

- Absolute root_path values are used as-is.
- Relative root_path values are resolved relative to the YAML file location.
- Missing or invalid root_path raises a project resolution error.

## Include and exclude behavior

- include patterns select candidate files.
- exclude patterns remove files from candidates.
- only regular files are indexed.
- final file list is deterministic (sorted).

## Recommended pattern

Keep project configs near the projects they target to make relative paths portable across machines.
