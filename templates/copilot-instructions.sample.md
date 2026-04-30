# Copilot Instructions Template

<!-- Copy this file to .github/copilot-instructions.md in a project repository. -->
<!-- Replace placeholder values before committing. -->

## Project Identity

Project Name: <PROJECT_NAME>

<!-- Replace PROJECT_ID with the indexed project id used by agent-brain. -->
Project ID: <PROJECT_ID>

This repository is connected to agent-brain project memory. The `Project ID` above
should match the `project_id` registered in agent-brain and, when used, the
repository root `.agent-brain.yml` file.

## How Copilot Should Work Here

1. Before implementing medium or large changes, consult project memory and active decisions.
2. Search for existing code patterns before introducing new abstractions, helpers, or frameworks.
3. Respect the current architecture unless the task explicitly asks for redesign.
4. Reuse existing utilities, services, and modules before creating new ones.
5. Prefer minimal diffs that solve the problem at the correct layer.
6. Keep naming, file layout, and error-handling style consistent with the repository.
7. If context is missing or requirements are ambiguous, state assumptions or ask for clarification before making risky changes.
8. Avoid speculative cleanup, drive-by refactors, and broad rewrites unless requested.

## Use agent-brain Memory

Use agent-brain tools when they are available in the current Copilot session.

- `search_project_context`
	Use before coding when you need architectural context, prior implementation notes, domain behavior, or repository-specific patterns.
- `get_project_decisions`
	Use before changing architecture, interfaces, infrastructure, data models, or core workflows to understand active and recent decisions.
- `save_project_decision`
	Use after a meaningful architecture or workflow choice is made so future sessions can reuse the reasoning.

Expected workflow:

1. For medium or large tasks, check `get_project_decisions` first.
2. If implementation context is still missing, query `search_project_context` with focused terms.
3. Only call `save_project_decision` for decisions that affect future engineering choices, not routine edits.

## Coding Standards Placeholder

<!-- Replace these placeholders with repository defaults. -->

- Language: <LANGUAGE>
- Framework: <FRAMEWORK>
- Package manager: <PACKAGE_MANAGER>
- Test command: <TEST_COMMAND>
- Lint command: <LINT_COMMAND>
- Typecheck command: <TYPECHECK_COMMAND>
- Build command: <BUILD_COMMAND>

Repository-specific standards:

- Follow the existing style, formatting, and module boundaries already present in the codebase.
- Add tests for behavior changes when the repository has test coverage in that area.
- Prefer small, readable functions over deep abstraction layers.

## Architecture Guardrails

<!-- Replace or trim these examples to match the repository. -->

- Do not bypass the auth or permission layer.
- Do not duplicate business logic that already exists in services, domain modules, or shared libraries.
- Prefer established service boundaries over cross-layer shortcuts.
- Preserve backward compatibility for public APIs, events, schemas, and CLI behavior when possible.
- Keep persistence, transport, and domain concerns separated.
- Introduce new dependencies only when the existing stack cannot solve the problem cleanly.

## Decision Memory Rules

When a meaningful technical decision is made:

1. Save it to agent-brain with `save_project_decision`.
2. Write a short title that will still make sense in a future session.
3. Record the decision itself, why it was chosen, and the main alternatives considered.
4. Prefer updating memory for architectural, operational, security, or workflow choices that affect future work.
5. Do not save trivial implementation details or temporary debugging notes as project decisions.

## Safe Delivery Rules

- Prefer small, reviewable changes over large multi-concern edits.
- Run relevant tests, linting, or type checks when available and when the change warrants it.
- Avoid broad refactors unless the task explicitly requests them.
- Preserve public contracts unless the change intentionally updates them.
- Call out assumptions, risks, and incomplete verification when they exist.
- Update documentation when behavior, setup, or architectural expectations change.

## Example Prompts

<!-- These are examples teams can keep or adapt for their repository. -->

- Use agent-brain memory and explain the current auth flow for this repository.
- Search existing JWT refresh implementation before changing auth.
- Check project decisions before modifying the event schema.
- Save a decision that feature flags remain centralized in the platform configuration layer.
- Use project memory to find existing retry logic before introducing a new network client abstraction.

## Notes For Maintainers

- Keep this file concise. It should guide behavior, not restate full project documentation.
- Prefer stable instructions that remain true across many tasks.
- Store repo-specific setup details in normal docs and reserve this file for working rules, architecture constraints, and memory usage.
