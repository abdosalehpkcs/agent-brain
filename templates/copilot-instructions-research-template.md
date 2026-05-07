# Copilot Instructions Template — Research Project

<!-- Copy this file to `.github/copilot-instructions.md` or the equivalent project instruction file. -->
<!-- Replace placeholder values before committing. -->

## Project Identity

Project Name: <PROJECT_NAME>
Project ID: <PROJECT_ID>

This project is connected to agent-brain research memory.

The `Project ID` should match:

- the `project_id` registered in agent-brain
- the project root `.agent-brain.yml` file, when used

## Research Purpose

Research Area: <RESEARCH_AREA>
Primary Output Type: <REPORT / BRIEF / REVIEW / DATASET / NOTES / OTHER>
Audience: <AUDIENCE>
Citation Style: <APA / IEEE / MLA / CHICAGO / OTHER>
Source Standard: <PRIMARY_SOURCES_ONLY / HIGH_QUALITY_SECONDARY_ALLOWED / MIXED>

## How Copilot Should Work Here

1. Separate facts, interpretations, assumptions, and recommendations.
2. Prefer primary sources, official documentation, standards, datasets, and direct evidence.
3. Use secondary sources only when primary sources are unavailable or when synthesis is needed.
4. Record publication date and access date when relevant.
5. Preserve conflicting evidence instead of hiding it.
6. Do not treat a claim as validated unless evidence supports it.
7. Mark uncertainty clearly.
8. Avoid overclaiming.
9. Keep research notes traceable to sources.
10. Update documentation or research notes when conclusions change.

## Chat Output Rules

Keep chat responses short.

Do not repeat long research notes in chat.

Write detailed evidence, source summaries, literature notes, and analysis into Markdown files.

Final chat responses should only include:

- files changed
- sources added or reviewed
- key findings
- unresolved questions
- risks or limitations
- next required research step, if any

Do not duplicate full source notes in chat.

Do not present unsupported conclusions.

## Use agent-brain Memory

Use agent-brain tools when available in the current session.

- `search_project_context`
  Use to find prior notes, source summaries, validated findings, open questions, and past conclusions.

- `get_project_decisions`
  Use to check previous research direction, methodology decisions, scope decisions, and source-selection decisions.

- `save_project_decision`
  Use only for durable research decisions, such as scope, methodology, inclusion/exclusion criteria, or final interpretation rules.

- `<FORGET_MEMORY_TOOL>`
  Use only when the user asks to delete memory or when stale/incorrect research memory must be removed. Prefer dry-run mode first.

- `<PDF_INGESTION_TOOL>`
  Use when the user provides a paper, report, standard, manual, or dataset documentation PDF that should become searchable.

Expected workflow:

1. Search existing project memory before starting a new research thread.
2. Check prior decisions if the work affects scope, methodology, or conclusions.
3. Ingest relevant source documents when provided.
4. Extract claims with source references.
5. Save only durable, useful findings after checking write policy.
6. Mark uncertain or conflicting findings clearly.
7. Do not save unsourced claims as validated findings.

## Write Policy Rules

Before writing memory, respect:

```text
brain-write-policy.yml
```

Recommended research memory categories:

- `source_notes`
- `validated_findings`
- `literature_findings`
- `hypotheses`
- `open_questions`
- `conflicting_evidence`
- `methodology_decisions`
- `dataset_notes`
- `experiment_notes`
- `temporary_notes`

Do not save:

- unsourced claims as validated findings
- weak assumptions as facts
- source summaries without enough context
- sensitive private data
- copyrighted long excerpts
- duplicate notes already present in project docs

When saving research memory, include where possible:

- source title
- author or organization
- publication date
- access date
- URL or file path
- page number or section
- confidence level
- short reason why it matters

## Source Quality Rules

Prefer this order:

1. Peer-reviewed papers
2. Official standards and specifications
3. Government or institutional datasets
4. Official documentation
5. Books from reputable publishers
6. High-quality industry reports
7. Reputable journalism
8. Blogs, forums, and social media only as weak evidence or for leads

Do not rely on one weak source for an important conclusion.

For current or unstable facts, verify with recent sources.

For high-stakes topics, use stronger source standards and mark uncertainty.

## Citation Rules

Cite all non-obvious factual claims in research outputs.

For each source note, record:

- title
- author/publisher
- date published
- date accessed
- link or file path
- page/section when available
- relevant claim
- confidence level

Do not fabricate citations.

Do not cite a source for a claim it does not support.

Do not quote long copyrighted text. Prefer paraphrase with citation.

## Analysis Rules

When analyzing research material:

1. Extract the central claim.
2. Identify evidence used.
3. Identify method or data source.
4. Identify limitations.
5. Compare with other sources.
6. Mark agreement, disagreement, or uncertainty.
7. Separate what the source says from what you infer.
8. Record open questions.

Use this structure for source notes:

```md
## Source Note: <TITLE>

- Source type:
- Author/publisher:
- Date:
- Link/file:
- Page/section:
- Central claim:
- Evidence:
- Method:
- Limitations:
- Relevance:
- Confidence:
- Related sources:
- Open questions:
```

## Documentation Rules

Use Markdown files for durable research output.

Recommended structure:

```text
research/
├── sources/
├── notes/
├── literature-review.md
├── findings.md
├── open-questions.md
├── methodology.md
├── datasets.md
└── decisions.md
```

Update documentation when:

- a new source changes the conclusion
- a finding becomes validated
- evidence conflicts
- scope changes
- methodology changes
- dataset version changes

## Privacy and Safety Rules

Do not store sensitive raw personal data in memory.

Do not save secrets, credentials, private identifiers, or confidential source material unless the project explicitly allows it and the storage policy permits it.

Do not claim local-only privacy unless the configured embedding provider is local.

If cloud embeddings are configured, assume sent text may leave the machine according to provider settings.

## Example Prompts

- Search research memory for existing notes on <TOPIC>.
- Ingest this report and create source notes with page references.
- Compare these two sources and identify conflicts.
- Save this methodology decision for future research sessions.
- Build an evidence table for the current findings.
- Identify which claims are unsupported.
- Review open questions before continuing the literature review.

## Notes For Maintainers

- Keep this file focused on research behavior.
- Store full research notes in Markdown files, not in this instruction file.
- Keep memory categories aligned with `brain-write-policy.yml`.
- Keep source standards strict enough for the project’s risk level.
