# Copilot Instructions Guide

This guide explains how to use the reusable Copilot instructions template in a
future repository connected to agent-brain.

## Purpose

The template gives GitHub Copilot Agent Mode a stable set of repository-level
working rules so it can:

- consult project memory before larger changes
- check existing decisions before altering architecture
- reuse established patterns instead of duplicating logic
- prefer small, safe changes with clear assumptions
- capture important decisions for future sessions

## Files

- Template source: `templates/copilot-instructions.sample.md`
- Destination in a target repository: `.github/copilot-instructions.md`
- Optional project identity file: `.agent-brain.yml`

## How To Apply It In A Future Repository

1. Copy `templates/copilot-instructions.sample.md` into the target repository as `.github/copilot-instructions.md`.
2. Replace placeholder values such as `<PROJECT_NAME>`, `<PROJECT_ID>`, `<LANGUAGE>`, and `<TEST_COMMAND>`.
3. Trim the guardrails so they reflect the real repository architecture.
4. Keep the agent-brain memory section if the repository can access the MCP tools.
5. Commit the final `.github/copilot-instructions.md` so the team shares the same guidance.

## Project Identity Guidance

`Project ID` should match the identifier stored in agent-brain for that project.
If the repository uses a root `.agent-brain.yml` file, keep the values aligned.

Example:

```yaml
project_id: billing-api
name: Billing API
```

## Customization Guidance

Keep the template focused on durable working rules.

Good content to keep:

- architecture constraints that should not be bypassed
- required validation commands
- naming or layering rules
- when to consult or save project memory

Content better suited for normal docs:

- long onboarding instructions
- environment setup details
- full architectural overviews
- task-specific delivery checklists

## Recommended Maintenance Rule

When the repository adopts a new architectural rule or recurring decision that
Copilot should consistently respect, update both:

1. `.github/copilot-instructions.md` for current repository behavior
2. agent-brain decision memory for durable cross-session context

This keeps short-form instructions and long-lived project memory aligned.