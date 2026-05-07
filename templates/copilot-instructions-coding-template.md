# Copilot Instructions Template — Coding Project

<!-- Copy this file to `.github/copilot-instructions.md` in a software repository. -->
<!-- Replace placeholder values before committing. -->

## Project Identity

Project Name: <PROJECT_NAME>
Project ID: <PROJECT_ID>

This repository is connected to agent-brain project memory.

The `Project ID` should match:

- the `project_id` registered in agent-brain
- the repository root `.agent-brain.yml` file, when used

## How Copilot Should Work Here

1. Before implementing medium or large changes, consult project memory and active decisions.
2. Search for existing code patterns before introducing new abstractions, helpers, frameworks, or dependencies.
3. Respect the current architecture unless the task explicitly asks for redesign.
4. Reuse existing utilities, services, and modules before creating new ones.
5. Prefer minimal diffs that solve the problem at the correct layer.
6. Keep naming, file layout, and error-handling style consistent with the repository.
7. If context is missing or requirements are ambiguous, state assumptions or ask for clarification before making risky changes.
8. Avoid speculative cleanup, drive-by refactors, and broad rewrites unless requested.
9. Update documentation when behavior, setup, architecture, tools, or workflows change.

## Chat Output Rules

Keep chat responses short.

Do not repeat long implementation summaries in chat.

Write detailed explanations into README files, skill docs, migration notes, or other Markdown files instead of chat.

Final chat responses should only include:

- files changed
- new tools or commands added
- manual setup steps
- tests added or updated
- known limitations

Do not duplicate documentation content in chat.

Do not explain every internal code change unless it affects setup, usage, compatibility, or review risk.

## Use agent-brain Memory

Use agent-brain tools when available in the current Copilot session.

- `search_project_context`
  Use before coding when architectural context, prior implementation notes, domain behavior, or repository-specific patterns are needed.

- `get_project_decisions`
  Use before changing architecture, interfaces, infrastructure, data models, or core workflows.

- `save_project_decision`
  Use after a meaningful architecture or workflow choice is made.

- `<FORGET_MEMORY_TOOL>`
  Use only when the user asks to delete memory or when stale/incorrect memory must be removed. Prefer dry-run mode before destructive deletion.

- `<PDF_INGESTION_TOOL>`
  Use when the user provides a PDF that should become searchable project context.

Expected workflow:

1. For medium or large tasks, check `get_project_decisions` first.
2. If implementation context is still missing, query `search_project_context` with focused terms.
3. Search existing code before adding new patterns.
4. Only call `save_project_decision` for decisions that affect future engineering choices.
5. Respect `brain-write-policy.yml` before writing memory.
6. Use safe delete/forget workflow for stale or incorrect memory.
7. Trust audit logging to record writes, deletes, and ingestion. Do not duplicate audit details in chat.

## Write Policy Rules

Before writing memory, respect:

```text
brain-write-policy.yml
```

Do not save arbitrary memories.

Common memory categories may include:

- `confirmed_decisions`
- `validated_findings`
- `architecture_notes`
- `action_items`
- `agreed_next_steps`
- `prompt_response_essence`
- `rejected_ideas`
- `temporary_notes`

Do not save:

- trivial implementation details
- temporary debugging notes unless explicitly requested
- uncertain assumptions as confirmed decisions
- sensitive secrets, credentials, tokens, or private personal data
- duplicated information already present in project docs

If a write is blocked by policy, report the reason briefly.

## Coding Standards Placeholder

- Language: <LANGUAGE>
- Framework: <FRAMEWORK>
- Package manager: <PACKAGE_MANAGER>
- Test command: <TEST_COMMAND>
- Lint command: <LINT_COMMAND>
- Typecheck command: <TYPECHECK_COMMAND>
- Build command: <BUILD_COMMAND>

Repository-specific standards:

- Follow existing style, formatting, and module boundaries.
- Add tests for behavior changes when test coverage exists in that area.
- Prefer small, readable functions over deep abstraction layers.
- Keep configuration, policy, audit, storage, embedding, and transport concerns separated.

## Architecture Guardrails

- Do not bypass auth, permission, policy, or validation layers.
- Do not bypass write-policy validation for memory writes.
- Do not duplicate business logic already present in services, domain modules, or shared libraries.
- Prefer established service boundaries over cross-layer shortcuts.
- Preserve backward compatibility for public APIs, events, schemas, MCP tools, and CLI behavior when possible.
- Keep persistence, transport, and domain concerns separated.
- Keep MCP server code focused on tool wiring. Put business logic in service modules.
- Introduce dependencies only when the existing stack cannot solve the problem cleanly.
- Do not hardcode machine-specific paths.
- Do not store secrets, tokens, credentials, or sensitive raw content in logs.

## Documentation Rules

Update documentation when changing:

- setup
- configuration
- MCP tools
- CLI commands
- database migrations
- embedding providers
- write policy behavior
- audit logging behavior
- PDF ingestion behavior
- safe delete/forget behavior
- privacy expectations

Put detailed behavior in:

- `README.md`
- `skills/*/SKILL.md`
- migration notes
- configuration examples

## Safe Delivery Rules

- Prefer small, reviewable changes over large multi-concern edits.
- Run relevant tests, linting, type checks, or builds when available.
- Avoid broad refactors unless explicitly requested.
- Preserve public contracts unless intentionally changing them.
- Call out assumptions, risks, and incomplete verification when they exist.
- Do not invent unsupported features in docs.
- Do not overclaim implementation status.

## Example Prompts

- Use agent-brain memory and explain the current auth flow for this repository.
- Search existing JWT refresh implementation before changing auth.
- Check project decisions before modifying the event schema.
- Save a decision that feature flags remain centralized in platform configuration.
- Use project memory to find existing retry logic before introducing a new client abstraction.

## Notes For Maintainers

- Keep this file concise.
- Store repo-specific setup details in normal docs.
- Reserve this file for working rules, architecture constraints, memory usage, and output behavior.
- Keep tool names accurate. Replace placeholder tool names after implementation.
