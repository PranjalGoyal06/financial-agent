# Codex Instructions

Use `/Users/pranjal/Projects/financial-agent/dev` as the primary worktree for
implementation unless the user explicitly instructs otherwise.

Treat `/Users/pranjal/Projects/financial-agent/main` as a reference worktree
only. Do not edit it as part of normal development. It may be inspected for
context or for small reusable snippets, but copied code must be reviewed,
simplified, and adapted to the cleaner `dev` implementation.

This repository contains product code for SCALE Finance Agent. Keep product
surface, source code, comments, tests, package metadata, and generated
documentation free of internal planning terminology.

Do not introduce references to iteration labels, roadmap phases, planning
documents, implementation milestones, or process scaffolding in application UI,
API payloads, source identifiers, comments, tests, package names, or README
text. Treat `docs/SPRINT_PLAN.md` as private planning context only; it must not
be reflected in product-facing language or source vocabulary.

Use product-neutral names such as `chat runtime`, `local response`,
`development user`, `run_start`, or domain-specific feature names instead of
planning labels. Before closing work that touches copy or identifiers, run a
targeted scan for internal planning terms outside `docs/SPRINT_PLAN.md`.
