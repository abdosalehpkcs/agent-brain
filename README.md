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
- Content-hash deduplication: unchanged documents are skipped on re-index.
- Provider switching: index the same project under multiple providers without data loss.
- Embedding status CLI: inspect coverage per provider/model/dimension.
- MCP server tools:
  - search_project_context
  - get_project_decisions
  - save_project_decision
  - embedding_status
  - system_status
  - list_projects
- Docker Compose stack for PostgreSQL + Ollama + model bootstrap.

## Provider Support

Supported embedding providers:

- ollama (default)
- openai
- azure

Provider selection is controlled by environment variables in `.env`.

Each provider produces embeddings with a specific model and dimension. Embeddings are stored per (provider, model, dimension) — they never mix. Switching providers adds new embeddings alongside existing ones.

### Default Configuration

```env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768
```

## Vector Dimension Rules

Supported dimensions:

| Dimension | Status | Index Type | Example Model |
|-----------|--------|------------|---------------|
| 768 | Supported | ivfflat ANN | nomic-embed-text (Ollama) |
| 1536 | Supported | ivfflat ANN | text-embedding-3-small (OpenAI/Azure) |
| 3072 | Experimental | Exact scan | text-embedding-3-large (OpenAI/Azure) |

- 768 and 1536 have ivfflat ANN indexes for fast approximate search.
- 3072 is stored in `VECTOR(3072)` and searched with exact scan (pgvector ANN indexes support up to 2000 dimensions for the `vector` type).
- 3072 works but is flagged as experimental. A warning is emitted at startup.

**Do not mix vectors from different providers/models in the same retrieval path.**

## Provider Switching

Switching providers does not destroy existing embeddings. The workflow:

1. Update `.env` with the new provider, model, and dimensions.
2. Re-run the indexer for each project.
3. Only missing embeddings for the new provider/model are created.
4. Old embeddings remain in their dimension-specific tables.

```bash
# Switch to OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# Re-index — skips unchanged content, creates only missing embeddings
python -m app.indexer examples/project-configs/test-docs.yaml
```

### Check Embedding Status

```bash
python -m app.vector_store status --project-id test-docs
```

Output shows provider, model, dimension, index type, and coverage:

```
provider         model                          dim indexed  embeddings   chunks  missing
--------------------------------------------------------------------------------
ollama           nomic-embed-text               768 ANN              42       42        0
openai           text-embedding-3-small        1536 ANN              42       42        0
```

## Re-indexing Behavior

The indexer uses content-hash deduplication:

- Each document is hashed (SHA-256) on read.
- If the hash matches the stored hash, the document is skipped.
- If content changed, old chunks and embeddings are deleted, then re-created.
- On provider switch, unchanged documents still get new embeddings for the active provider/model.
- Chunks are never duplicated; the `(document_id, chunk_index)` constraint prevents it.

## Embedding Metadata

Every embedding row includes:

- `provider` — which API produced the vector (ollama, openai, azure)
- `model` — the specific model name
- `dimensions` — inferred from the table (768, 1536, or 3072)
- `created_at` — timestamp

Search always filters by `(project_id, provider, model)` to prevent cross-model contamination.

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

## Quick Start

1. Create a Python virtual environment and install dependencies.
2. Copy `.env.example` to `.env` and set provider settings.
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

5. Check embedding status:

```bash
python -m app.vector_store status --project-id test-docs
```

6. Decision memory check:

```bash
python -m app.decisions list --project-id test-code
```

## MCP Setup

Use the global setup guide:

- docs/global-mcp-setup.md

Related docs:

- docs/diagram.md
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

python -m app.vector_store status --project-id test-docs
python -m app.vector_store status --project-id test-code

python -m app.decisions list --project-id test-code

python app/mcp_server.py

pytest
```

## Azure OpenAI Setup

### 1. Prerequisites

- An Azure OpenAI resource provisioned in the Azure portal.
- An embedding model deployment (e.g. `text-embedding-3-small`).
- The deployment name, API key, and endpoint URL.

### 2. Environment Configuration

Create or update `.env` with Azure-specific variables:

```env
# Database (unchanged)
DATABASE_URL=postgresql://agent:agentpass@localhost:5432/agent_memory

# Azure OpenAI provider
EMBEDDING_PROVIDER=azure
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# Azure credentials
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com
AZURE_OPENAI_API_KEY=YOUR_API_KEY_HERE
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=YOUR_DEPLOYMENT_NAME

# Ollama not used — leave blank or remove
OLLAMA_BASE_URL=
```

| Variable | Description |
|----------|-------------|
| `EMBEDDING_PROVIDER` | Set to `azure` |
| `EMBEDDING_MODEL` | Model name matching your Azure deployment |
| `EMBEDDING_DIMENSIONS` | `1536` for text-embedding-3-small |
| `AZURE_OPENAI_ENDPOINT` | Full URL of your Azure OpenAI resource |
| `AZURE_OPENAI_API_KEY` | API key from Azure portal → Keys and Endpoint |
| `AZURE_OPENAI_API_VERSION` | API version string (default: `2024-02-01`) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Deployment name you created in Azure |

### 3. Docker Configuration

When using Azure OpenAI, Ollama services are not needed. Comment out or remove the `ollama` and `ollama-init` services in `docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: agent-brain-postgres
    # ... postgres config unchanged ...

  # --- Ollama not needed for Azure OpenAI ---
  # ollama:
  #   image: ollama/ollama:latest
  #   container_name: agent-brain-ollama
  #   ...

  # ollama-init:
  #   image: ollama/ollama:latest
  #   container_name: agent-brain-ollama-init
  #   ...

volumes:
  agent-brain-postgres-data:
  # agent-brain-ollama-data:
```

Only the `postgres` service is required. The Python application connects to Azure OpenAI directly over HTTPS.

### 4. Running the Project

```bash
# 1. Start only PostgreSQL
docker compose up -d postgres

# 2. Verify the database is running
docker ps --format "table {{.Names}}\t{{.Status}}"

# 3. Index a project
python -m app.indexer examples/project-configs/test-docs.yaml

# 4. Verify Azure OpenAI is being used
python -m app.vector_store status --project-id test-docs
```

Expected status output confirms `azure` as provider:

```
provider         model                          dim indexed  embeddings   chunks  missing
--------------------------------------------------------------------------------
azure            text-embedding-3-small        1536 ANN              42       42        0
```

### 5. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required` | Missing deployment name in `.env` | Set `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` to your Azure deployment name |
| `Failed to fetch embedding from Azure OpenAI` | Wrong endpoint URL or network issue | Verify `AZURE_OPENAI_ENDPOINT` matches your Azure portal URL |
| `401 Unauthorized` | Invalid or expired API key | Regenerate the key in Azure portal → Keys and Endpoint |
| Embeddings still show `ollama` as provider | Old `.env` or Docker cache | Confirm `EMBEDDING_PROVIDER=azure` in `.env`, then `docker compose down && docker compose up -d postgres` |
| `Embedding dimension mismatch` | Model output doesn't match `EMBEDDING_DIMENSIONS` | Ensure dimensions match the model (1536 for text-embedding-3-small) |
| Container uses stale config | Docker layer cache | Run `docker compose up -d --force-recreate postgres` |
