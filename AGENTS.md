# AGENTS.md

## Repository Expectations

- Keep repository changes small, intentional, and aligned with the existing project structure.
- Prefer durable project documentation over relying on chat history or unstated assumptions.

## Architecture Persistence Rule

All project architecture-related work must use persistent storage and retrieval.

- Before architecture-related analysis, design, refactoring, implementation, review, or planning, read the relevant persisted architecture state from `docs/architecture/` and `docs/adr/`.
- Architecture-related work includes system design, module boundaries, runtime structure, dependency choices, data models, API contracts, integration points, deployment topology, cross-cutting concerns, and major refactors.
- When new architecture context is discovered, changed, proposed, accepted, or rejected, update the persistent documents in the same task:
  - Use `docs/architecture/README.md` for the current architecture overview, module map, data flow, invariants, and integration notes.
  - Use `docs/adr/` for architecture decisions that include meaningful trade-offs or long-term consequences.
- Do not leave architecture knowledge only in conversation, transient plans, commit messages, or local scratch files.
- If architecture documentation cannot be updated, stop and report the blocker before treating the architecture work as complete.
- Commits or pull requests with architecture impact must include matching updates under `docs/architecture/` or `docs/adr/`, or explicitly state that there is no architecture impact.

## Verification

- After architecture-related changes, check that the persisted architecture documents still match the code and intended design.
- Keep architecture documentation concise, current, and linked to concrete files or modules when those exist.

## Core Delivery Workflow Constraint

For demand design, feature development, testing, bug work, and architecture improvement, use this project-level main workflow:

```text
/ask-matt -> /grill-with-docs -> /to-prd -> /to-issues -> /prototype -> /triage -> /tdd -> /diagnosing-bugs -> /improve-codebase-architecture -> /handoff
```

Treat the sequence as a required workflow gate for substantial project work, not a loose recommendation.

- Start with `/ask-matt` to route the request and confirm whether the full flow, an on-ramp, or a smaller path applies.
- Use `/grill-with-docs` before committing to implementation scope so requirements, domain terms, and architecture decisions are clarified and persisted.
- Use `/to-prd` to turn the clarified demand into a durable PRD when the work is larger than a single obvious change.
- Use `/to-issues` to break approved PRDs or plans into independently-grabbable vertical slices on the issue tracker.
- Use `/prototype` when a design question needs a runnable answer, then keep only the learned decision and delete or absorb throwaway code.
- Use `/triage` for raw incoming issues, external requests, and bug reports. Do not re-triage issues already produced by `/to-issues` unless new information makes them ambiguous.
- Use `/tdd` for implementation: confirm the test seam, write a failing behavior test first, make it pass, then repeat one vertical slice at a time.
- Use `/diagnosing-bugs` for bugs, regressions, flakes, and performance issues; build a tight red-capable feedback loop before hypothesizing.
- Use `/improve-codebase-architecture` when implementation, tests, or diagnosis reveal shallow modules, missing seams, hidden coupling, or architecture friction.
- Use `/handoff` before changing sessions, compacting context, delegating work, or leaving unfinished reasoning that another agent must continue.

If a step is not applicable, explicitly state why in the working notes, issue, PRD, commit message, or handoff. Do not silently skip steps that affect requirements, tests, architecture, or cross-session continuity.

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `EnochLi15/TradeMiner`; use the `gh` CLI from this clone. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default `mattpocock/skills` triage label vocabulary unchanged. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain documentation layout for this repository. See `docs/agents/domain.md`.
