# Troubleshooting

## Search returns no results

- Confirm indexing completed successfully.
- Confirm project_id matches the indexed project.
- Confirm provider/model/dimensions match the indexed embeddings.

## Missing embedding tables

If schema setup failed midway, table creation may have been skipped.

Re-run schema inside postgres:

```bash
docker compose exec -T postgres psql -U agent -d agent_memory -f /docker-entrypoint-initdb.d/01-schema.sql
```

## Slow 3072-dimensional search

This is expected for large datasets.

- 3072 vectors are stored and queried exactly.
- ANN indexes are currently used for 768 and 1536 dimensions.

If 3072 throughput becomes a bottleneck, consider:

- halfvec migration strategy
- provider-side lower-dimensional embeddings where supported
- dual-index strategy with rerank

## Docker naming mismatch after pull

Run:

```bash
docker compose config
docker ps -a --format "table {{.Names}}\t{{.Status}}"
docker volume ls
```

Older resources are not deleted automatically.
