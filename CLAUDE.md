# Markets Project — Agent Team

## Purpose
A multi-agent system for designing, critiquing, and building a project that demonstrates elite-level thinking across systems engineering, real-time data infrastructure, and financial markets. The final output is a working system, a portfolio artifact, and a publishable technical writeup.

## Agent Roster

| Agent | File | Role |
|---|---|---|
| Orchestrator | `agents/orchestrator.md` | Coordinates sessions, manages debate, synthesizes consensus |
| Systems Architect | `agents/systems-architect.md` | Low-latency infra, distributed systems, kernel-level design |
| Quant Strategist | `agents/quant-strategist.md` | Market microstructure, alpha, risk, financial modeling |
| Data Infrastructure Engineer | `agents/data-infra-engineer.md` | Real-time pipelines, tick DBs, streaming, storage |
| Adversarial Critic | `agents/adversarial-critic.md` | Stress-tests every assumption, finds second-order failures |
| Portfolio Narrator | `agents/portfolio-narrator.md` | Shapes output into elite-tier portfolio and writeup |
| Finance Mentor | `agents/finance-mentor.md` | Socratic finance teacher tuned to the user's specific learning style |

## How to Run a Session

To start a brainstorm, invoke the orchestrator:

```
Read agents/orchestrator.md and follow its protocol to kick off a full team session on [topic].
```

Each specialist agent can also be invoked independently:

```
Read agents/systems-architect.md, then [task].
```

## Session Artifacts

All outputs go into `sessions/` with ISO timestamps:
- `sessions/YYYY-MM-DD_topic/architecture.md`
- `sessions/YYYY-MM-DD_topic/critique.md`
- `sessions/YYYY-MM-DD_topic/decisions.md`
- `sessions/YYYY-MM-DD_topic/narrative.md`

## Ground Rules

1. No agent defers to consensus if they have a principled objection — disagreement is a feature, not a bug.
2. Every technical claim must cite a real mechanism (not vibes). "This is faster" requires a reason.
3. The Adversarial Critic has veto power to force a re-architecture pass before any decision is finalized.
4. The Orchestrator breaks ties by forcing explicit tradeoff documentation, never by fiat.
