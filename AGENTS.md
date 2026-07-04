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

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `EnochLi15/TradeMiner`; use the `gh` CLI from this clone. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default `mattpocock/skills` triage label vocabulary unchanged. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain documentation layout for this repository. See `docs/agents/domain.md`.
