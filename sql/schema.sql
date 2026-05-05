-- Create the application user role if it doesn't exist
-- Note: This uses hardcoded credentials for development; in production,
-- inject credentials via environment variables or secrets management.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'agent') THEN
        CREATE ROLE agent WITH LOGIN PASSWORD 'agentpass';
    END IF;
    ALTER ROLE agent CREATEDB;
END
$$;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO agent;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- projects stores top-level workspace identities and metadata.
-- It provides the tenancy boundary for all memory records so data can be
-- isolated, queried, and managed per coding or research project.
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('coding', 'research')),
    root_path TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- documents captures source artifacts (files, notes, docs) ingested from a project.
-- It enables traceability from derived memory chunks back to the original source,
-- supporting refresh, deduplication, and auditability workflows.
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    path TEXT NOT NULL,
    title TEXT,
    content_hash TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- chunks stores segmented text units prepared for semantic retrieval.
-- Each chunk can hold a vector embedding for similarity search, making this table
-- the core memory layer used for context recall and relevance ranking.
-- Warning: VECTOR dimension must match the active embedding provider and model.
-- If provider or model changes later, schema migration and re-indexing may be required.
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_type TEXT,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chunks_document_chunk_index_key UNIQUE (document_id, chunk_index)
);

-- chunk_embeddings_768 stores embeddings for models that output 768 dimensions
-- (for example, Ollama nomic-embed-text). This enables provider/model-specific
-- search while preserving coexistence with other model families.
CREATE TABLE IF NOT EXISTS chunk_embeddings_768 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chunk_embeddings_768_chunk_provider_model_key
        UNIQUE (chunk_id, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_768_project_provider_model
    ON chunk_embeddings_768 (project_id, provider, model);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_768_embedding
    ON chunk_embeddings_768 USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- chunk_embeddings_1536 stores embeddings for 1536-dimension models
-- (for example, OpenAI text-embedding-3-small).
CREATE TABLE IF NOT EXISTS chunk_embeddings_1536 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chunk_embeddings_1536_chunk_provider_model_key
        UNIQUE (chunk_id, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_1536_project_provider_model
    ON chunk_embeddings_1536 (project_id, provider, model);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_1536_embedding
    ON chunk_embeddings_1536 USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- chunk_embeddings_3072 stores embeddings for 3072-dimension models (experimental).
-- pgvector ANN indexes (ivfflat/hnsw) on the vector type support up to 2000 dimensions,
-- so this table uses exact-search semantics with provider/model filtering.
-- Prefer 768 or 1536 for production workloads.
CREATE TABLE IF NOT EXISTS chunk_embeddings_3072 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chunk_embeddings_3072_chunk_provider_model_key
        UNIQUE (chunk_id, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_3072_project_provider_model
    ON chunk_embeddings_3072 (project_id, provider, model);

-- decisions stores durable architecture and operational choices per project.
-- Agents use this table to preserve rationale, alternatives, and status across sessions.
CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT,
    alternatives TEXT,
    status TEXT,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_project_id ON chunks (project_id);
CREATE INDEX IF NOT EXISTS idx_decisions_project_id ON decisions (project_id);
