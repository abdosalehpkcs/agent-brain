# agent-brain

agent-brain is a project-scoped memory backend for coding and research assistants. It stores content in PostgreSQL + pgvector, generates embeddings through configurable providers, enforces write policies, maintains audit logs, and serves memory/search through CLI modules and MCP tools.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server                             │
│  search_project_context, save_project_decision,            │
│  forget_memory, ingest_pdf_document, ...                   │
└─────────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Policy    │  │    Audit    │  │  Embedding  │
│  Validator  │  │   Logger    │  │  Provider   │
└─────────────┘  └─────────────┘  └─────────────┘
         │                │                │
         └────────────────┼────────────────┘
                          ▼
              ┌─────────────────────┐
              │  PostgreSQL + pgvector  │
              │  (project-scoped data)  │
              └─────────────────────┘
```

### Core Components

- **Storage**: PostgreSQL 16 with pgvector extension
- **Embeddings**: Provider-agnostic router for Ollama, OpenAI, and Azure OpenAI
- **Isolation**: Project-level partitioning with provider/model-scoped retrieval
- **Write Policy**: YAML-based rules controlling what memories can be stored
- **Audit Logging**: JSON-lines audit trail for all memory operations
- **MCP Server**: Tools for Copilot and other MCP-compatible agents

## Privacy Implications

**Important**: Data privacy depends on your configured embedding provider:

| Provider | Data Location | Privacy Level |
|----------|---------------|---------------|
| Ollama | Local machine | Fully local - no external API calls |
| OpenAI | OpenAI servers | Cloud - text sent to OpenAI API |
| Azure OpenAI | Azure infrastructure | Cloud - check your Azure data residency |

**Local-only mode is possible ONLY when using Ollama.** When OpenAI or Azure providers are configured, your text content is sent to external APIs for embedding generation.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `search_project_context` | Semantic search over project memory |
| `get_project_decisions` | Retrieve active/recent decisions |
| `save_project_decision` | Store a decision with policy validation |
| `forget_memory` | Safe deletion with dry-run support |
| `ingest_pdf_document` | PDF extraction and ingestion |
| `embedding_status` | Check embedding coverage |
| `system_status` | Runtime health and configuration |
| `list_projects` | List all known projects |

## Write Policy

The write policy (`brain-write-policy.yml`) controls what memories can be stored:

```yaml
default_allowed: false
require_category: true

categories:
  confirmed_decisions:
    allowed: true
    requires_source: true
    requires_context: false
    allow_overwrite: false
    description: "Final architecture decisions"

  temporary_notes:
    allowed: true
    requires_expiry: true
    description: "Short-lived notes"
```

### Policy Rules

| Rule | Effect |
|------|--------|
| `allowed: false` | Category is blocked entirely |
| `requires_source: true` | Write must specify a source |
| `requires_context: true` | Write must include context |
| `allow_overwrite: false` | Cannot overwrite existing memories |
| `requires_expiry: true` | Must specify an expiry date |

### Example: Allowed Write

```json
{
  "tool": "save_project_decision",
  "arguments": {
    "project_id": "my-project",
    "title": "Use PostgreSQL",
    "decision": "We will use PostgreSQL for storage",
    "source": "architecture_review",
    "category": "confirmed_decisions"
  }
}
```

### Example: Blocked Write

```json
{
  "tool": "save_project_decision",
  "arguments": {
    "project_id": "my-project",
    "title": "Quick note",
    "decision": "...",
    "category": "confirmed_decisions"
    // Missing required "source" field
  }
}
// Error: "Write blocked by policy: Category 'confirmed_decisions' requires a source"
```

## Audit Logging

All memory-changing operations are logged to `agent-brain-audit.jsonl`:

```json
{
  "timestamp": "2025-05-05T10:30:00Z",
  "operation": "decision_save",
  "project_id": "my-project",
  "status": "success",
  "category": "confirmed_decisions",
  "source": "mcp",
  "content_hash": "sha256...",
  "embedding_provider": "ollama",
  "embedding_model": "nomic-embed-text"
}
```

**Sensitive content is NOT stored** in audit logs — only content hashes.

### Audited Operations

- Memory writes
- Decision saves
- Memory deletions
- PDF ingestions
- Policy-blocked attempts
- Embedding generation failures

### Inspecting Audit Logs

```bash
# View recent audit events
tail -20 agent-brain-audit.jsonl | jq .

# Filter by operation
grep "decision_save" agent-brain-audit.jsonl | jq .

# Find blocked writes
grep "policy_blocked" agent-brain-audit.jsonl | jq .
```

## PDF Ingestion

### How to Ingest a PDF

```bash
# CLI
python -m app.pdf_ingestion /path/to/document.pdf my-project

# MCP Tool
{
  "tool": "ingest_pdf_document",
  "arguments": {
    "project_id": "my-project",
    "file_path": "/path/to/document.pdf"
  }
}
```

### Ingestion Behavior

1. Extracts text from PDF pages
2. Checks write policy for `pdf_content` category
3. Computes content hash for duplicate detection
4. Chunks text with page reference preservation
5. Generates embeddings for each chunk
6. Stores chunks with metadata
7. Logs operation to audit trail

### Page Reference Preservation

Search results include page numbers:

```json
{
  "chunk": {
    "content": "Authentication must use OAuth 2.0...",
    "metadata": {
      "source_type": "pdf",
      "start_page": 5,
      "end_page": 6
    }
  }
}
```

## Safe Forget/Delete

### Delete by ID

```json
{
  "tool": "forget_memory",
  "arguments": {
    "project_id": "my-project",
    "chunk_id": "uuid-of-chunk"
  }
}
```

### Query-Based Deletion (Dry Run First)

```json
// Step 1: Preview what will be deleted
{
  "tool": "forget_memory",
  "arguments": {
    "project_id": "my-project",
    "category": "temporary_notes",
    "dry_run": true
  }
}
// Returns: {"count": 5, "dry_run": true, "items": [...]}

// Step 2: Actually delete
{
  "tool": "forget_memory",
  "arguments": {
    "project_id": "my-project",
    "category": "temporary_notes",
    "dry_run": false
  }
}
```

### Safety Constraints

- Query-based deletion requires at least one filter (category or file_path_pattern)
- Defaults to `dry_run: true` to prevent accidental deletion
- All deletions are audit logged
- Cross-project deletion is blocked

## Quick Start

### Automated Setup (Recommended)

```bash
./setup.sh
```

The setup script will:
- Check prerequisites (Python, Docker)
- Validate environment configuration
- Create virtualenv and install dependencies
- Start Docker services
- Apply database schema
- Run tests
- Verify the full setup

Options:
```bash
./setup.sh --help       # Show help
./setup.sh --clean      # Clean previous setup first
./setup.sh --test-only  # Run tests only
./setup.sh --skip-docker # Skip Docker (use external DB)
```

### Manual Setup

#### 1. Setup Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. Configure Provider

Copy `.env.example` to `.env` and configure:

```env
# Local mode (Ollama)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768
OLLAMA_BASE_URL=http://localhost:11434

# Or OpenAI mode
# EMBEDDING_PROVIDER=openai
# EMBEDDING_MODEL=text-embedding-3-small
# EMBEDDING_DIMENSIONS=1536
# OPENAI_API_KEY=sk-...

# Or Azure OpenAI mode
# EMBEDDING_PROVIDER=azure
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

#### 3. Start Infrastructure

```bash
docker compose up -d
```

#### 4. Index and Search

```bash
# Index a project
python -m app.indexer examples/project-configs/test-docs.yaml

# Search
python -m app.search test-docs "Why use pgvector?"

# Ingest a PDF
python -m app.pdf_ingestion /path/to/doc.pdf my-project
```

#### 5. Run MCP Server

```bash
python -m app.mcp_server
```

## Vector Dimensions

| Dimension | Status | Index Type | Example Model |
|-----------|--------|------------|---------------|
| 768 | Supported | ivfflat ANN | nomic-embed-text (Ollama) |
| 1536 | Supported | ivfflat ANN | text-embedding-3-small (OpenAI/Azure) |
| 3072 | Experimental | Exact scan | text-embedding-3-large (OpenAI/Azure) |

## Provider Switching

Switching providers does not destroy existing embeddings:

```bash
# 1. Update .env with new provider
# 2. Re-index projects (only new embeddings created)
python -m app.indexer examples/project-configs/test-docs.yaml

# 3. Check status
python -m app.vector_store status --project-id test-docs
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose ps

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Ollama Connection Issues

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Pull the model
ollama pull nomic-embed-text
```

### Policy Errors

```bash
# Check write policy file exists
cat brain-write-policy.yml

# Verify YAML syntax
python -c "import yaml; yaml.safe_load(open('brain-write-policy.yml'))"
```

### Audit Log Issues

```bash
# Check audit log exists and is writable
touch agent-brain-audit.jsonl
ls -la agent-brain-audit.jsonl

# View recent entries
tail agent-brain-audit.jsonl | jq .
```

## Testing

```bash
pytest
```

## Documentation

- [Global MCP Setup](docs/global-mcp-setup.md)
- [Project Resolution](docs/project-resolution.md)
- [Testing Guide](docs/testing-guide.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Security](docs/security.md)

## Skills

Agent skills are documented in the `skills/` directory:

- [PDF Ingestion](skills/pdf-ingestion/SKILL.md) - How to ingest PDFs
- [Local Brain Access](skills/local-brain-access/SKILL.md) - How to use the MCP tools
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
