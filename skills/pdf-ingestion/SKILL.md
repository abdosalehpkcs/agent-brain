---
title: "PDF Ingestion for Queryable Project Memory"
description: "Ingest PDF documents into agent-brain with section-aware metadata for reliable semantic recall."
category: "Knowledge Management"
keywords: ["pdf", "ingestion", "brain", "memory", "sections", "audit", "semantic-search"]
difficulty: "Intermediate"
estimated_time: "10 minutes"
published: true
---

# PDF Ingestion for Queryable Project Memory

## What This Skill Does

This skill teaches you to ingest PDF documents into agent-brain so that:

- **Sections are individually queryable** — recall returns specific chapters/sections, not random mid-document chunks
- **Metadata enables precise retrieval** — entries tagged with document name, section, page range, and topic tags
- **Recall is deterministic** — "architecture decisions section 3.2" finds the right content reliably
- **Re-ingestion is safe** — content-hash deduplication prevents duplicates
- **Privacy is respected** — write policy and audit logging enforced

---

## The Problem with Naive PDF Ingestion

```json
{
  "tool": "ingest_pdf_document",
  "arguments": {
    "project_id": "my-project",
    "file_path": "/path/to/TechnicalSpec.pdf"
  }
}
```

**Result:** 42 chunks with `chunk_index` metadata — no section labels.

**Symptom:** `search_project_context` for "authentication section 5.3" returns nothing useful, even though the PDF contains that exact section.

**Why:** Automatic chunking splits by character count, not document structure. Section boundaries fall randomly inside chunks.

---

## Two-Phase Ingestion Strategy

### Phase 1 — Bulk Ingest (Baseline Coverage)

Use `ingest_pdf_document` to index all text content as a searchable baseline:

```json
{
  "tool": "ingest_pdf_document",
  "arguments": {
    "project_id": "research-project",
    "file_path": "/docs/TechnicalSpecification-v2.0.pdf",
    "category": "pdf_content"
  }
}
```

This creates chunk-level coverage. Check with `embedding_status`:

```json
{
  "tool": "embedding_status",
  "arguments": { "project_id": "research-project" }
}
```

### Phase 2 — Structured Section Decisions

For key sections that need precise recall, persist as **decisions** with rich metadata:

```json
{
  "tool": "save_project_decision",
  "arguments": {
    "project_id": "research-project",
    "title": "Authentication Architecture (TechSpec §5.3)",
    "decision": "<extracted section 5.3 text here>",
    "reason": "Section extracted for precise recall during implementation",
    "source": "TechnicalSpecification-v2.0.pdf pages 45-48",
    "category": "architecture_notes"
  }
}
```

---

## Metadata Schema for Queryable PDF Sections

When persisting a PDF section as a decision, structure the title and reason for searchability:

| Field | Purpose | Example |
|-------|---------|---------|
| `title` | Document + section identifier | `"Auth Requirements (TechSpec §5.3)"` |
| `decision` | Extracted section content | Full text of section |
| `reason` | Context for why this was captured | `"Key section for OAuth implementation"` |
| `source` | Document path + page range | `"TechSpec-v2.0.pdf pages 45-48"` |
| `alternatives` | Related sections | `"See also §5.4 for token refresh"` |
| `status` | `active` for current references | `"active"` |

**Tip:** Include section number, topic keywords, and page range in `title` for better semantic matching.

---

## Search Patterns That Work After Phase 2

```json
// By document + section
{
  "tool": "search_project_context",
  "arguments": {
    "project_id": "research-project",
    "query": "TechSpec section 5.3 authentication OAuth",
    "include_decisions": true
  }
}

// By topic across documents
{
  "tool": "search_project_context",
  "arguments": {
    "project_id": "research-project",
    "query": "backup encryption data protection requirements",
    "include_decisions": true
  }
}

// Direct decision retrieval
{
  "tool": "get_project_decisions",
  "arguments": { "project_id": "research-project" }
}
```

---

## Agent Workflow: Check Before Ingest

Before extracting and persisting a section:

```
1. search_project_context for "<document> <section> <topic>"
2. If result found with source containing page range → REUSE existing
3. If only chunk_index results (no section metadata) → Extract and persist as decision
4. Verify with search_project_context after persistence
```

**Example check:**

```json
{
  "tool": "search_project_context",
  "arguments": {
    "project_id": "research-project",
    "query": "TechnicalSpec authentication section 5.3",
    "top_k": 3,
    "include_decisions": true
  }
}
```

If results only contain `chunk_index` in metadata (no section info), Phase 2 is needed.

---

## CLI Usage

### Bulk Ingestion (Phase 1)

```bash
python -m app.pdf_ingestion /path/to/document.pdf my-project
```

Options:
- `--chunk-size 1200` — Characters per chunk (default: 1200)
- `--chunk-overlap 150` — Overlap between chunks (default: 150)
- `--allow-duplicates` — Re-ingest even if content hash matches

### Check Coverage

```bash
python -m app.vector_store status --project-id my-project
```

---

## Write Policy Compliance

PDF ingestion respects `brain-write-policy.yml`:

| Category | Default Rules |
|----------|---------------|
| `pdf_content` | Allowed, requires source, allows overwrite |
| `architecture_notes` | Allowed, requires context |

If policy blocks the write:
```
Error: Write blocked by policy: Category 'pdf_content' requires a source
```

**Fix:** Ensure `source` parameter is provided for categories that require it.

---

## Duplicate Detection

Content-hash deduplication prevents re-ingesting identical files:

```json
{
  "success": true,
  "skipped": true,
  "message": "Skipped: duplicate of document abc-123-def"
}
```

To force re-ingestion after file changes:
- The content hash will differ automatically
- Or use `--allow-duplicates` flag (CLI)
- Or set `skip_duplicates: false` (MCP tool)

---

## Page Reference Preservation

Every chunk includes page metadata for citation:

```json
{
  "content": "The authentication system must support OAuth 2.0...",
  "metadata": {
    "source_type": "pdf",
    "start_page": 45,
    "end_page": 46
  }
}
```

When presenting results, include page references:

```
Found in TechnicalSpec-v2.0.pdf (pages 45-46):
> The authentication system must support OAuth 2.0...
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Search returns generic chunks with `chunk_index` | Only Phase 1 done | Persist key sections as decisions with rich metadata |
| Search returns nothing | Document not indexed | Check `embedding_status`; run bulk ingest first |
| `ingest_pdf_document` fails | File path invalid or PDF corrupted | Verify path; check if PDF opens in reader |
| "PDF is encrypted" error | Password-protected PDF | Decrypt PDF before ingestion |
| No text extracted | Image-only PDF (scanned) | OCR not supported; use text-based PDF |
| Write blocked by policy | Category not allowed | Check `brain-write-policy.yml`; use allowed category |
| Embedding failure logged | Provider unreachable | Check `system_status` for Ollama/OpenAI connectivity |

---

## Audit Log Inspection

All PDF operations are logged to `agent-brain-audit.jsonl`:

```bash
# View all PDF ingestion events
grep "pdf_ingest" agent-brain-audit.jsonl | jq .

# Find failed ingestions
grep "pdf_ingest" agent-brain-audit.jsonl | jq 'select(.status == "failed")'

# Check recent activity
tail -20 agent-brain-audit.jsonl | jq 'select(.operation == "pdf_ingest")'
```

Audit entries include:
- `timestamp`, `project_id`, `status`
- `source` (file path)
- `item_count` (chunks created)
- `reason` (for failures)

---

## Coverage Gap Detection

To check if a document has structured section entries vs. only bulk chunks:

```json
{
  "tool": "search_project_context",
  "arguments": {
    "project_id": "my-project",
    "query": "<document-name> section",
    "include_decisions": true
  }
}
```

**If results show:**
- `chunk_index` in metadata, no `section` → Only Phase 1 coverage
- Decision entries with section info in title → Phase 2 complete

---

## Privacy Reminder

Data privacy depends on your embedding provider:

| Provider | Data Location |
|----------|---------------|
| Ollama | Local only — no external API calls |
| OpenAI | Sent to OpenAI servers |
| Azure OpenAI | Sent to Azure infrastructure |

Check active provider:
```json
{ "tool": "system_status", "arguments": {} }
```

**Do not ingest sensitive PDFs when using cloud embedding providers.**
