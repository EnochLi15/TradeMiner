# Domain Docs

TradeMiner uses a single-context documentation layout for agent workflows.

## Before Exploring, Read These

- `CONTEXT.md` at the repo root, if it exists.
- `docs/architecture/README.md` for the current architecture overview and invariants.
- Relevant files under `docs/adr/` for architecture decisions that touch the area being changed.

If `CONTEXT.md` does not exist, proceed silently. Domain-modeling and grilling workflows may create it later when project terminology becomes concrete.

## Architecture Persistence

Architecture-related work must follow the repository rule in `AGENTS.md`:

- Read persisted architecture state before analysis, design, refactoring, implementation, review, or planning.
- Update `docs/architecture/README.md` when current architecture context changes.
- Add or update ADRs under `docs/adr/` when decisions include meaningful trade-offs or long-term consequences.

Do not leave architecture knowledge only in chat history, transient plans, commit messages, or scratch files.

## Use The Glossary's Vocabulary

When output names a domain concept in an issue title, refactor proposal, hypothesis, or test name, use the term as defined in `CONTEXT.md` once that file exists.

If the concept is not in the glossary yet, either reconsider whether the term belongs in this project or note the gap for a domain-modeling or grilling workflow.

## Flag ADR Conflicts

If output contradicts an existing ADR, surface it explicitly rather than silently overriding it.
