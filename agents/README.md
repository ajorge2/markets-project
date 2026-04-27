# Agents

This directory holds two agent systems that share a folder:

1. **The original markets-project brainstorming team** — Orchestrator, Systems Architect, Quant Strategist, Data Infra Engineer, Adversarial Critic, Portfolio Narrator, Finance Mentor. See the top-level `CLAUDE.md` for how those are invoked. Their prompts are the `*.md` files directly in this directory.

2. **The credit-valuation three-agent system** — Diagrammer, Debugger, Critic. Documented below. The Diagrammer and Debugger live in the subdirectories `diagrammer/` and `debugger/`. The Critic reuses the existing `adversarial-critic.md` prompt — there is no separate `critic/` directory.

---

# Three-Agent Credit-Valuation System

Three agents, each invoked as a separate Claude Code session by a human. They never run simultaneously. "Learning" across runs is file-based: each agent reads a markdown rules file at the start of every run, and the file is injected into the next prompt by being read first.

**No fine-tuning, no background processes, no shared memory — just markdown files on disk.**

## The three agents

| Agent | Prompt | Rules file it reads | Writes to |
|---|---|---|---|
| Diagrammer | `diagrammer/agent.md` | `diagrammer/rules.md` | `.architecture/*.json`, `diagrammer/rules.md`, `debugger/rules.md` |
| Debugger | `debugger/agent.md` | `debugger/rules.md` | `src/**` (code patches only) |
| Critic | `adversarial-critic.md` | `debugger/rules.md` + `last-seen-debugger-rules.md` | `last-seen-debugger-rules.md` only |

The Critic's three-agent-system protocol is appended directly to `adversarial-critic.md` ("Role in the Credit-Valuation Three-Agent System"). The snapshot file lives at `agents/last-seen-debugger-rules.md`, next to the prompt.

## Information flow

```
human corrections
      │
      ▼
  Diagrammer ──writes──► .architecture/*.json  (diagrams)
      │
      ├──writes──► diagrammer/rules.md         (its own style/behavior rules)
      │
      └──writes──► debugger/rules.md           (architectural facts for the Debugger)
                          │
                          ▼
                      Debugger                  (reads rules, patches code)
                          │
                          ▼
                      Critic                    (reads rules, diffs against last-seen, stress-tests)
                          │
                          └──writes──► last-seen-debugger-rules.md  (snapshot only)
```

Information flows **Diagrammer → Debugger → Critic**. There is no back-edge. The Critic is a sink.

## The rules-file convention

Both `diagrammer/rules.md` and `debugger/rules.md` follow the same rules:

- **Append-only.** New entries go at the bottom.
- **Dated.** Every entry starts with `### YYYY-MM-DD — short title`.
- **Never deleted.** To retract or change a rule, write a new dated entry whose body begins with `Supersedes: <title of older rule>`.
- **Binding on read.** An agent reading its rules file treats every non-superseded entry as a hard requirement for that run.

The exact entry format is documented at the top of each rules file.

## The Diagrammer → Debugger write relationship

This is the main cross-agent mechanic. After the Diagrammer produces or updates a diagram, it decides whether the run yielded a new **architectural fact** about the code — something that is not a style preference and that a debugger would need to know. Examples:

- "The `risk/` module reads from `market_data/`, not from `pricing/`."
- "This pipeline is the PD pipeline. There is no LGD pipeline yet."
- "FRED ingestion writes to JSONL first and is loaded into the DB by a separate step."

If the run produced such facts, the Diagrammer appends each as a dated entry to `debugger/rules.md`. Style corrections ("use swimlanes," "color DBs amber") go only into `diagrammer/rules.md`.

The Debugger never edits its own rules file. If it sees a contradiction between the rules file and the code, it flags the contradiction in its output for the human to resolve — it does not silently choose a side.

## The Critic's diff mechanic

The Critic maintains one file: `agents/last-seen-debugger-rules.md`, a verbatim snapshot of `debugger/rules.md` from the previous Critic run. On each run the Critic:

1. Reads both files.
2. Diffs them.
3. Treats any new or superseded entries as **new architectural information** and incorporates them into the critique — new failure modes, new hidden assumptions, revised blast radius.
4. Overwrites `last-seen-debugger-rules.md` with the current rules-file contents.

On the first Critic run, the last-seen file does not exist. Treat the entire current rules file as new, then create the snapshot.

## What does not exist yet

- `.architecture/` — the Diagrammer populates this on its first run.
- `agents/last-seen-debugger-rules.md` — the Critic creates it on its first run.

## Invocation (for humans)

```
Read agents/diagrammer/agent.md and follow its protocol. Bug/correction context: ...
Read agents/debugger/agent.md and follow its protocol. Bug: ...
Read agents/adversarial-critic.md and follow its protocol, including the three-agent-system section at the bottom.
```
