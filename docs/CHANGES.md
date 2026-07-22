# Changes

## [2026-07-22] — Wrote High_Level_Overview.md from full codebase audit
- Documented all backend modules, ORM models, API endpoints, LangGraph pipelines (chat agent + deep research), frontend architecture, and data flows in `docs/High_Level_Overview.md`.
- Covers infrastructure (Docker Compose, env vars), all 14 agent tools, the 7-node research pipeline, evidence/citation system, briefing service, and frontend component tree.
- Added maintenance rules for both `High_Level_Overview.md` and `CHANGES.md` to `.gemini/instructions.md`.

## [2026-07-22] — Setup documentation tracking
- Added High_Level_Overview.md and CHANGES.md to `dev/docs/`
- Why: To maintain structured architectural context and a rolling changelog.
- Updated project instructions with rules for maintaining these files.
