# Test Projects

This folder contains portable fixtures for validating indexing and semantic search behavior.

## Projects

- test-docs-project
- test-code-project

## Standard flow

Run from repository root.

```bash
docker compose up -d

python -m app.indexer test-projects/test-docs-project/test-docs.yaml
python -m app.search test-docs "Why use pgvector instead of a separate vector DB?"

python -m app.indexer test-projects/test-code-project/test-code.yaml
python -m app.search test-code "Where is JWT token logic implemented?"
```

## Notes

- Configs use root_path: . so they are portable.
- The indexer resolves root_path relative to each YAML file.
