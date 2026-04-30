# Security Notes

## Secrets

- Do not commit .env.
- Keep API keys in environment variables or secret managers.
- Avoid logging sensitive config values.

## Logging policy

- Use module loggers for operational events.
- Do not log credentials, tokens, or full user secrets.
- CLI output can be user-facing, but should remain concise.

## Database safety

- Scope all retrieval by project_id.
- Keep provider/model filters in search queries to prevent vector mixing.
- Validate dimensions before writes and queries.

## Production hardening recommendations

- Use managed secrets for API keys.
- Enable TLS for remote database connections.
- Apply least-privilege database roles.
- Add backup and restore validation drills.
