# Diagrammer Rules

This file accumulates binding rules for the Diagrammer agent. Every rule here is followed on every future run without re-prompting.

## Format
Append new entries to the bottom. Never reorder or delete (supersede instead). Each entry:

```
### YYYY-MM-DD — short title
Rule: <one-sentence binding rule, imperative>
Source: <human correction, self-derived, spec, etc.>
Scope: <style | correctness | naming | layout | architectural-fact>
```

If a rule is **architectural-fact** scope, the Diagrammer must also append a matching entry to `agents/debugger/rules.md` in the same run.

Supersede an older rule by writing a new dated entry that says `Supersedes: <title of older rule>` on its own line, followed by the new rule.

---

<!-- Appended rules go below this line. -->

### 2026-04-25 — Keep Q&A answers short
Rule: In Q&A mode, default to the shortest answer that's still complete. Lead with the direct answer in 1-3 sentences. Only add context, examples, tables, or caveats if the user asks a follow-up or the answer would be wrong without them. No multi-section essays unless explicitly requested.
Why: Human said responses were overwhelming. They want concise answers, not thorough ones by default.
How to apply: Q&A mode only — diagrams and rule entries can stay precise. Trust the user to ask for more if they want more. If you're tempted to add a "honest critique" or "three options" section unprompted, don't.
Source: human correction
Scope: style

### 2026-04-25 — Use shared product-prefix labels for paired services
Rule: When two or more service/component/client nodes collectively make up one logical product, prefix every member's label with the product name and an em-dash separator (e.g. `Credit Dashboard — API`, `Credit Dashboard — Refresh Worker`, `Credit Dashboard — Frontend`). The path goes on a second line below the prefixed label, per the path-labeling rule.
Why: Human flagged that the scheduler and the FastAPI service looked like two unrelated services on the system diagram even though they are paired pieces of one product. They are independent processes (deployment shape) but one product from the user's perspective; in the absence of a visual grouping primitive in the spec, a shared label prefix is what conveys the pairing.
How to apply: Apply only when ≥2 nodes collectively *constitute* the same product (e.g. a dashboard's web tier + worker + frontend). Do not apply just because nodes share infrastructure (e.g. multiple writers to the same DB do not all become "Postgres — Writer N"). Shared infra components used by multiple products get a "(shared)" suffix instead, e.g. `Ingestion layer (shared)`.
Source: human correction
Scope: naming

### 2026-04-25 — Always include source path in node labels
Rule: Every node whose label maps to a code artifact must include its path relative to the project root in the label (e.g. `src/ingestion/fred_ingest.py`, not just `fred_ingest.py`). Externals (third-party APIs, services not in the repo) are exempt — no path. Drilldown summary nodes that stand in for a whole directory use the directory path with a trailing slash (e.g. `src/ingestion/`). Databases reference the schema file when one exists (e.g. `Postgres\n(schema: src/schema.sql)` or `Postgres\n(table: acquisitions)` when the diagram is scoped to one table).
Why: Human flagged that file references were inconsistent across diagrams — some nodes had paths, some didn't. The agent prompt's "no mystery boxes" principle means consistency is required, not optional.
How to apply: Apply on every diagram in every mode. When unsure whether to include a path, include it. The only legitimate reasons to omit are (1) the node is external, (2) the node is a person/role/actor, or (3) no code artifact exists yet (status: proposed).
Source: human correction
Scope: naming

