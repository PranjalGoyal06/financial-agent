# Main Worktree Reference

`/Users/pranjal/Projects/financial-agent/main` is an older exploratory worktree.
Use it for reference only. The primary implementation target is
`/Users/pranjal/Projects/financial-agent/dev`.

Current state of `main`:

- It contains a larger FastAPI backend under `backend/app` with chat,
  portfolio, artifact, market data, news, and repository modules.
- The chat path includes persistent session files, a reactive graph package, and
  a separate simple tool-agent path. These may be useful as references for API
  shape or event handling, but they should not be treated as the current
  architecture.
- Portfolio import and valuation exist, but holdings are backed by in-memory
  repositories rather than durable database tables.
- Chroma-like retrieval and several repositories are in-memory placeholders.
- The frontend is a larger Vite React app with dashboard, chat, portfolio, and
  research-oriented surfaces. It is more advanced than the current `dev`
  product surface and should not be copied wholesale.
- The `main` worktree is dirty at the time of this note, including frontend
  changes for chat rendering keys and portfolio CSV export helpers.
- Tests in `main` can be useful for behavior ideas, but they were written around
  the older implementation and should be ported deliberately.

Reusable candidates from `main`, after review:

- CSV import schema validation ideas.
- Portfolio CSV export helper tests.
- Chat SSE parsing and rendering patterns.
- Selected frontend table or layout techniques, if they fit the simpler `dev`
  codebase.

Avoid reusing from `main` without redesign:

- In-memory repositories for durable application state.
- Broad multi-route UI structure that is ahead of the current product.
- Placeholder retrieval or research behavior.
- Any product copy or identifiers that expose internal planning vocabulary.
