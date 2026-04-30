# Global MCP Setup

This guide configures agent-brain as a shared MCP server for VS Code Copilot.

## Prerequisites

- Python 3.10+
- Docker Desktop
- A cloned copy of this repository

## 1. Prepare runtime

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

## 2. Start infrastructure

```bash
docker compose up -d
```

Expected containers:

- agent-brain-postgres
- agent-brain-ollama
- agent-brain-ollama-init

## 3. Configure VS Code user MCP config

Open command palette:

- MCP: Open User Configuration

Add a server entry using absolute paths:

```json
{
  "servers": {
    "agent-brain": {
      "type": "stdio",
      "command": "/ABSOLUTE/PATH/TO/agent-brain/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/ABSOLUTE/PATH/TO/agent-brain",
      "env": {
        "PYTHONPATH": "/ABSOLUTE/PATH/TO/agent-brain"
      }
    }
  }
}
```

Reference template:

- examples/vscode/mcp.sample.json

## 4. Verify

Run in Copilot agent mode:

- call system_status

Expected fields include database_reachable, provider, embedding_model, and app_version.

## Troubleshooting highlights

- If tools are missing, verify command and cwd paths in MCP config.
- If database_reachable is false, run docker compose up -d and verify DATABASE_URL.
- If Ollama model bootstrap is still running, inspect logs from agent-brain-ollama-init.

## Naming migration note

If older local compose resources still exist (for example agent-memory-postgres or postgres_data), this repo does not remove them automatically.

Inspect and clean up old resources manually when safe:

```bash
docker ps -a --format "table {{.Names}}\t{{.Status}}"
docker volume ls
```
