# Testing Guide

## Run all tests

```bash
pytest
```

## Test scope

Current suite covers:

- config validation
- project path resolution
- vector-store table and guard behavior
- decision input validation
- search flow orchestration
- embedding validation helpers

## Notes

- External provider calls are mocked.
- Tests are deterministic and run without network access.
- Ollama integration tests can be added separately if needed.
