# Copilot Instructions Template — PhD / Academic Research Project

<!-- Copy this file to `.github/copilot-instructions.md` or the equivalent project instruction file. -->
<!-- Replace placeholder values before committing. -->

## Project Identity

Project Name: <PROJECT_NAME>
Project ID: <PROJECT_ID>

This project is connected to agent-brain academic research memory.

The `Project ID` should match:

- the `project_id` registered in agent-brain
- the project root `.agent-brain.yml` file, when used

## PhD Research Context

Research Field: <FIELD>
Thesis Topic: <THESIS_TOPIC>
Research Questions: <RESEARCH_QUESTIONS>
Methodology: <QUALITATIVE / QUANTITATIVE / MIXED / THEORETICAL / COMPUTATIONAL / OTHER>
Citation Style: <APA / IEEE / CHICAGO / HARVARD / OTHER>
Reference Manager: <ZOTERO / MENDELEY / BIBTEX / OTHER>
Target Output: <THESIS / CHAPTER / PAPER / SYSTEMATIC REVIEW / EXPERIMENT / DATASET>

## Core Academic Rules

1. Separate evidence, interpretation, critique, and speculation.
2. Prefer peer-reviewed papers, books, official datasets, standards, and primary sources.
3. Track exact bibliographic metadata for every source.
4. Preserve page numbers, section numbers, DOI, arXiv ID, or other stable identifiers when available.
5. Do not invent citations.
6. Do not cite a paper for a claim it does not support.
7. Do not hide contradictory evidence.
8. Mark confidence and limitations clearly.
9. Keep methodology and inclusion/exclusion criteria explicit.
10. Keep research outputs reproducible.

## Chat Output Rules

Keep chat responses short.

Do not dump long literature summaries in chat.

Write detailed notes, evidence tables, paper summaries, chapter drafts, and methodology records into Markdown files.

Final chat responses should only include:

- files changed
- papers/sources reviewed
- key findings
- conflicts or gaps found
- methods or criteria changed
- tests/analysis run, if applicable
- known limitations

Do not repeat full paper summaries in chat when they are written to Markdown.

Do not present interpretation as fact.

## Use agent-brain Memory

Use agent-brain tools when available in the current session.

- `search_project_context`
  Use to find prior paper notes, concepts, hypotheses, evidence tables, research gaps, experiment notes, and chapter decisions.

- `get_project_decisions`
  Use before changing research questions, methodology, inclusion/exclusion criteria, theoretical framing, dataset selection, experiment design, or thesis structure.

- `save_project_decision`
  Use for durable academic decisions only.

- `<FORGET_MEMORY_TOOL>`
  Use only when stale, incorrect, duplicated, or retracted research memory should be removed. Prefer dry-run mode first.

- `<PDF_INGESTION_TOOL>`
  Use when the user provides papers, theses, standards, reports, or dataset documentation.

Expected workflow:

1. Search existing memory before analyzing new papers.
2. Check methodology and scope decisions before changing analysis direction.
3. Ingest source PDFs when provided.
4. Extract bibliographic metadata and core claims.
5. Create structured paper notes.
6. Compare claims against existing literature notes.
7. Update evidence tables and open questions.
8. Save only durable findings or decisions after checking write policy.
9. Mark unresolved conflicts and weak evidence clearly.

## Write Policy Rules

Before writing memory, respect:

```text
brain-write-policy.yml
```

Recommended academic memory categories:

- `paper_notes`
- `literature_findings`
- `validated_findings`
- `theoretical_frameworks`
- `research_questions`
- `hypotheses`
- `methodology_decisions`
- `inclusion_exclusion_criteria`
- `dataset_notes`
- `experiment_logs`
- `analysis_results`
- `conflicting_evidence`
- `research_gaps`
- `open_questions`
- `chapter_notes`
- `writing_decisions`
- `temporary_notes`

Do not save:

- unsourced claims as validated findings
- early ideas as confirmed conclusions
- copied long excerpts from papers
- private participant data
- confidential review material
- duplicate notes without added value
- claims from retracted or weak papers without warning

When saving memory, include where possible:

- source title
- authors
- year
- venue
- DOI/arXiv/URL/file path
- page or section
- claim
- evidence or method
- limitation
- relevance to thesis
- confidence level
- relation to research questions

## Paper Analysis Workflow

For every important paper, create a structured note.

Use this format:

```md
# Paper Note: <TITLE>

## Bibliographic Data
- Authors:
- Year:
- Venue:
- DOI / URL:
- File path:
- Citation key:
- Access date:

## Research Problem
- Problem addressed:
- Gap claimed by authors:
- Research questions or hypotheses:

## Methodology
- Study type:
- Data:
- Sample:
- Instruments/tools:
- Procedure:
- Analysis method:

## Main Claims
1. Claim:
   - Evidence:
   - Page/section:
   - Strength:

## Results
- Key result 1:
- Key result 2:
- Statistical/technical details where relevant:

## Limitations
- Author-stated limitations:
- Additional limitations:
- Threats to validity:

## Relevance to My Research
- Supports:
- Contradicts:
- Extends:
- Related research question:

## Critical Evaluation
- Strengths:
- Weaknesses:
- Assumptions:
- Missing evidence:

## Links to Other Work
- Agrees with:
- Conflicts with:
- Builds on:
- Cited by / citing:

## Memory Candidates
- Validated finding:
- Open question:
- Possible citation use:
```

## Literature Review Rules

When building or updating a literature review:

1. Group papers by theme, method, theory, or research question.
2. Compare papers, not just summarize them one by one.
3. Identify consensus, disagreement, and gaps.
4. Track chronology when the field evolved over time.
5. Distinguish seminal papers from incremental papers.
6. Track definitions of key terms across sources.
7. Do not claim a gap exists without checking recent literature.
8. Keep a clear evidence table.

Recommended files:

```text
phd/
├── bibliography/
│   ├── references.bib
│   └── citation-keys.md
├── papers/
│   └── paper-notes/
├── literature-review/
│   ├── themes.md
│   ├── evidence-table.md
│   ├── research-gaps.md
│   └── conflicting-evidence.md
├── methodology/
│   ├── methodology.md
│   ├── inclusion-exclusion.md
│   └── validity-threats.md
├── experiments/
│   ├── experiment-log.md
│   └── analysis-results.md
├── thesis/
│   ├── outline.md
│   ├── chapter-notes.md
│   └── writing-decisions.md
└── open-questions.md
```

## Evidence Table Format

Use this format when comparing literature:

```md
| Claim | Supporting Sources | Conflicting Sources | Method Strength | Limitations | Confidence | Relevance |
|---|---|---|---|---|---|---|
| <claim> | <sources> | <sources> | <high/medium/low> | <limits> | <high/medium/low> | <RQ/chapter> |
```

## Methodology Rules

When working on methodology:

- State the research design clearly.
- Record inclusion and exclusion criteria.
- Track dataset versions and licenses.
- Track software versions, models, prompts, instruments, and parameters.
- Keep experiment logs reproducible.
- Separate pilot results from final results.
- Record failed experiments when they affect future decisions.
- Track threats to validity.
- Avoid changing methodology silently after seeing results.

## Writing Rules

When drafting thesis or paper text:

1. Use cautious academic language.
2. Avoid unsupported generalizations.
3. Cite claims.
4. Link paragraphs to research questions.
5. Make the contribution clear.
6. Avoid excessive passive voice where clarity suffers.
7. Keep definitions consistent.
8. Preserve distinction between prior work and own contribution.
9. Do not fabricate results or citations.
10. Mark placeholders clearly.

Use placeholders like:

```text
[CITATION NEEDED]
[VERIFY PAGE NUMBER]
[CHECK AGAINST LATEST LITERATURE]
[RESULT NOT YET VALIDATED]
```

## Source Quality Rules

Preferred source order:

1. Peer-reviewed journal articles
2. Top conference papers in the field
3. Academic books and book chapters
4. Official standards
5. Government or institutional datasets
6. Preprints, marked as not peer-reviewed
7. Technical reports from credible institutions
8. Industry reports, used with caution
9. Blogs and forums only for leads or practitioner context

For critical claims, prefer multiple independent sources.

For recent fields, check the latest papers before declaring the state of the art.

## Citation and Copyright Rules

- Do not invent references.
- Do not create fake DOIs.
- Do not quote long copyrighted excerpts.
- Prefer paraphrase with citation.
- Keep direct quotations short and purposeful.
- Always verify page numbers before final thesis or paper use.
- Track citation keys consistently.
- Mark missing metadata clearly.

## Data and Experiment Rules

When analyzing data or experiments:

- Record dataset name, version, source, license, and retrieval date.
- Record preprocessing steps.
- Record code version or commit when possible.
- Record environment, package versions, and random seeds when relevant.
- Preserve raw data separately from processed data.
- Keep analysis reproducible.
- Mark exploratory analysis separately from confirmatory analysis.
- Do not overstate statistical or experimental results.

## Privacy and Ethics Rules

- Do not store private participant data in memory unless explicitly allowed by the research protocol.
- Do not store identifiable personal data unnecessarily.
- Respect consent, IRB/ethics requirements, licenses, and confidentiality.
- Flag ethical risks when research uses human data, scraping, surveillance, medical data, financial data, or sensitive topics.
- Do not claim local-only privacy unless the configured provider is local.

## Example Prompts

- Analyze this paper and create a structured paper note.
- Compare these three papers and update the evidence table.
- Search memory for work related to research question 2.
- Identify gaps in the current literature review.
- Check whether this claim is supported by the cited paper.
- Save this methodology decision for future sessions.
- Ingest this thesis PDF and preserve page references.
- Build a chapter outline from the validated findings.
- Find conflicting evidence for this hypothesis.
- Review experiment logs and identify threats to validity.

## Notes For Maintainers

- Keep this file focused on academic behavior.
- Store full paper notes and thesis content in Markdown files.
- Keep memory categories aligned with `brain-write-policy.yml`.
- Keep citation style consistent with the project.
- Do not let convenience weaken source quality.
