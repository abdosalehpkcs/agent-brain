---
title: "Local Brain Access for Project Memory"
description: "Use agent-brain MCP tools for semantic search, decision persistence, and safe memory management."
category: "Knowledge Management"
keywords: ["brain", "memory", "search", "decisions", "recall", "mcp", "semantic"]
difficulty: "Beginner"
estimated_time: "5 minutes"
published: true
---

# Local Brain Access for Project Memory

## What This Skill Does

This skill teaches you to use the agent-brain MCP tools to:

- **Search project memory** — semantic retrieval of indexed content and decisions
- **Persist decisions** — store architecture choices with rationale for long-term recall
- **Manage memory safely** — delete with dry-run preview and audit logging
- **Check system health** — verify database and embedding provider status

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server                             │
│  search_project_context, save_project_decision,            │
│  forget_memory, ingest_pdf_document, system_status         │
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

**Key Properties:**
- All data is project-scoped — no cross-project contamination
- Write policy validates every save operation
- Every mutation is audit logged with content hash (not raw content)
- Embeddings are provider/model-scoped

---

## Privacy Warning

| Provider | Data Location | Privacy Level |
|----------|---------------|---------------|
| Ollama | Local machine | ✅ Fully local |
| OpenAI | OpenAI servers | ⚠️ Cloud — text sent externally |
| Azure OpenAI | Azure infrastructure | ⚠️ Cloud — check data residency |

**Check active provider before sensitive operations:**

```json
{ "tool": "system_status", "arguments": {} }
```

**Local-only mode requires Ollama.** When OpenAI/Azure is configured, text is sent to external APIs.

---

## Tool Reference

### search_project_context

Semantic search over project memory with optional decision inclusion.

```json
{
  "tool": "search_project_context",
  "arguments": {
    "project_id": "my-project",
    "query": "authentication OAuth implementation",
    "top_k": 8,
    "include_decisions": true
  }
}
```

**Returns:**
- `chunks` — semantically similar indexed content with distance scores
- `decisions` — active decisions if `include_decisions: true`

**Tip:** Lower `distance` = more relevant. Filter by `distance < 0.5` for high-confidence matches.

---

### save_project_decision

Persist a decision with policy validation and audit logging.

```json
{
  "tool": "save_project_decision",
  "arguments": {
    "project_id": "my-project",
    "title": "Use PostgreSQL for storage",
    "decision": "We will use PostgreSQL with pgvector extension for vector storage",
    "reason": "Mature ecosystem, ACID compliance, native vector support",
    "alternatives": "Considered: SQLite + ChromaDB, Pinecone, Weaviate",
    "status": "active",
    "source": "architecture_review_2026-05",
    "category": "confirmed_decisions"
  }
}
```

**Required for some categories:**
- `source` — where the decision came from
- `reason` (as `context`) — why this decision was made

**Policy will block if required fields are missing.**

---

### get_project_decisions

Retrieve active and recent decisions for a project.

```json
{
  "tool": "get_project_decisions",
  "arguments": { "project_id": "my-project" }
}
```

**Returns:**
- `active_decisions` — decisions with `status: active`
- `recent_decisions` — all recent decisions regardless of status

---

### forget_memory

Safe deletion with dry-run support and audit logging.

**Delete by ID (immediate):**
```json
{
  "tool": "forget_memory",
  "arguments": {
    "project_id": "my-project",
    "chunk_id": "uuid-of-chunk-to-delete"
  }
}
```

**Query-based deletion (dry-run first):**
```json
// Step 1: Preview
{
  "tool": "forget_memory",
  "arguments": {
    "project_id": "my-project",
    "category": "temporary_notes",
    "dry_run": true
  }
}
// Returns: {"count": 5, "dry_run": true, "items": [...]}

// Step 2: Execute (only if count is expected)
{
  "tool": "forget_memory",
  "arguments": {
    "project_id": "my-project",
    "category": "temporary_notes",
    "dry_run": false
  }
}
```

**Safety:** Query-based deletion requires at least one filter and defaults to `dry_run: true`.

---

### system_status

Check runtime health and configuration.

```json
{ "tool": "system_status", "arguments": {} }
```

**Returns:**
- `database_reachable` — PostgreSQL connectivity
- `provider` — active embedding provider (ollama/openai/azure)
- `ollama_reachable` — Ollama API status (if using Ollama)
- `embedding_dimensions` — vector size (768/1536/3072)

---

### embedding_status

Check embedding coverage for a project.

```json
{
  "tool": "embedding_status",
  "arguments": { "project_id": "my-project" }
}
```

**Returns:** Count of embeddings per provider/model/dimension.

---

## Workflow Patterns

### Before Saving a Decision

Always check if similar decision already exists:

```
1. search_project_context for "<topic> decision"
2. If active decision found → Update status or skip
3. If no decision found → save_project_decision
```

### Before Deleting Memory

Always use dry-run for query-based deletion:

```
1. forget_memory with dry_run: true
2. Review count and items
3. If expected → forget_memory with dry_run: false
4. Verify with search_project_context
```

### Checking Knowledge Gaps

```
1. search_project_context for "<topic>"
2. If no results → Knowledge gap, need to index content
3. If results have chunk_index but no section metadata → Only bulk-indexed
4. If results include decisions with rich metadata → Fully covered
```

---

## Write Policy Categories

The default policy (`brain-write-policy.yml`) defines these categories:

| Category | Requires Source | Requires Context | Allows Overwrite |
|----------|-----------------|------------------|------------------|
| `confirmed_decisions` | ✅ | ❌ | ❌ |
| `validated_findings` | ✅ | ✅ | ✅ |
| `architecture_notes` | ❌ | ✅ | ✅ |
| `action_items` | ❌ | ❌ | ✅ |
| `temporary_notes` | ❌ | ❌ | ✅ |
| `pdf_content` | ✅ | ❌ | ✅ |

**Blocked write example:**
```
Error: Write blocked by policy: Category 'confirmed_decisions' requires a source
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Search returns nothing | Project not indexed | Run indexer or ingest documents first |
| Search returns irrelevant chunks | Query too vague | Add specific keywords, section references |
| Save blocked by policy | Missing required field | Check category requirements; add `source` or `reason` |
| Database unreachable | PostgreSQL not running | `docker compose up -d` |
| Ollama unreachable | Ollama service down | Check `ollama serve` is running |
| Embedding dimension mismatch | Provider changed | Re-index with new provider |

---

## Audit Log Inspection

All operations logged to `agent-brain-audit.jsonl`:

```bash
# Recent activity
tail -20 agent-brain-audit.jsonl | jq .

# Failed operations
grep '"status":"failed"' agent-brain-audit.jsonl | jq .

# Policy-blocked writes
grep "policy_blocked" agent-brain-audit.jsonl | jq .

# Deletions
grep "memory_delete" agent-brain-audit.jsonl | jq .
```

**Audit entries include:** timestamp, operation, project_id, status, content_hash (never raw content).

---

## Common Mistakes to Avoid

| Mistake | Why It's Wrong | Correct Approach |
|---------|----------------|------------------|
| Saving without checking existing | Creates duplicates | Search first, update if exists |
| Bulk delete without dry-run | Accidental data loss | Always preview with `dry_run: true` |
| Ignoring policy errors | Write silently fails | Read error message, add required fields |
| Assuming local-only | Data may go to cloud | Check `system_status` for provider |
| Vague search queries | Poor recall quality | Include document name, section, keywords |

---

## Quick Reference

```json
// Search memory
{ "tool": "search_project_context", "arguments": { "project_id": "X", "query": "..." } }

// Save decision
{ "tool": "save_project_decision", "arguments": { "project_id": "X", "title": "...", "decision": "...", "source": "..." } }

// Get decisions
{ "tool": "get_project_decisions", "arguments": { "project_id": "X" } }

// Safe delete (preview)
{ "tool": "forget_memory", "arguments": { "project_id": "X", "category": "...", "dry_run": true } }

// System health
{ "tool": "system_status", "arguments": {} }
```
