# agent-brain

agent-brain is a local-first memory backend for coding and research assistants. It stores project content in PostgreSQL + pgvector, generates embeddings through multiple providers, and serves memory/search through CLI modules and MCP tools.

## Architecture Summary

- Storage: PostgreSQL 16 with pgvector.
- Embeddings: provider-agnostic router for Ollama, OpenAI, and Azure OpenAI.
- Isolation: project-level partitioning plus provider/model-scoped retrieval.
- Retrieval: semantic search over dimension-specific embedding tables.
- MCP: optional shared server exposing memory tools to Copilot.

## Current Features

- Project indexing from YAML config files.
- Semantic search scoped by project, provider, model, and vector dimensions.
- Durable decision memory with CLI CRUD-style operations.
- MCP server tools:
  - search_project_context
  - get_project_decisions
  - save_project_decision
  - system_status
  - list_projects
- Docker Compose stack for PostgreSQL + Ollama + model bootstrap.

## Provider Support

Supported embedding providers:

- ollama
- openai
- azure

Provider selection is controlled by environment variables in .env.

## Vector Dimension Rules

Supported dimensions in this project:

- 768
- 1536
- 3072

Indexing behavior:

- 768 and 1536 use ivfflat ANN indexes.
- 3072 is stored in vector(3072) and searched exactly (no ivfflat/hnsw ANN index).

Rationale:

- Current pgvector ANN indexes for the vector type support up to 2000 dimensions.
- 3072 remains supported for correctness and compatibility, with exact search tradeoffs.

Do not mix vectors from different providers/models in the same retrieval path.

## Docker Setup

### Service and resource names

- Services: postgres, ollama, ollama-init
- Containers:
  - agent-brain-postgres
  - agent-brain-ollama
  - agent-brain-ollama-init
- Volumes:
  - agent-brain-postgres-data
  - agent-brain-ollama-data
- Network:
  - agent-brain-network

### Migration note for older local environments

If you previously used older compose naming (for example agent-memory-postgres, postgres_data, ollama_data), Docker may still have stopped containers and volumes with the old names.

This repository does not delete or migrate old resources automatically.

Safe manual cleanup steps:

1. Inspect old resources:
   - docker ps -a --format "table {{.Names}}\t{{.Status}}"
   - docker volume ls
2. Stop/remove only old containers you no longer use.
3. Remove old volumes only after confirming data is no longer needed.

## Quick Start

1. Create a Python virtual environment and install dependencies.
2. Copy .env.example to .env and set provider settings.
3. Start infrastructure:

```bash
docker compose up -d
```

4. Index and search sample projects:

```bash
python -m app.indexer examples/project-configs/test-docs.yaml
python -m app.search test-docs "Why use pgvector?"

python -m app.indexer examples/project-configs/test-code.yaml
python -m app.search test-code "Where is JWT token logic implemented?"
```

5. Decision memory check:

```bash
python -m app.decisions list --project-id test-code
```

## MCP Setup

Use the global setup guide:

- docs/global-mcp-setup.md

Related docs:

- docs/project-resolution.md
- docs/testing-guide.md
- docs/troubleshooting.md
- docs/security.md

## Testing

Run the test suite:

```bash
pytest
```

## Validation Commands

```bash
docker compose config
docker compose up -d
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

python -m app.indexer examples/project-configs/test-docs.yaml
python -m app.search test-docs "Why use pgvector?"

python -m app.indexer examples/project-configs/test-code.yaml
python -m app.search test-code "Where is JWT token logic implemented?"

python -m app.decisions list --project-id test-code

python app/mcp_server.py

pytest
```
