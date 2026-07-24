# Changes

### [2026-07-24] — Implemented `/create-artifact` slash command subgraph
- Built `create_artifact_graph` to handle the `/create-artifact` command, incorporating intent parsing to decide if fresh market data grounding is needed.
- Integrated the command into `main.py` routing, enabling the unified SSE streaming protocol to emit conversational filler and `card_render` events for artifacts.
- Adopted the new `Artifact` database model (replacing `ResearchArtifact` for chat creations) to save generated markdown content and evidence metadata persistently.
### [2026-07-24] — Completed `/compare` command integration & card renderer
- Added `ComparisonCardRender.tsx` to render structured stock comparison cards into a formatted table with winner highlights instead of raw JSON.
- Connected `$ticker` autocomplete in chat composer to `/api/search/stocks` backend endpoint, fixing 422 errors on empty search queries.
- Handled non-string stream tokens in `main.py` to prevent `marked.js` array parameter crashes during LLM streaming.

### [2026-07-24] — Fixed sidebar health indicator CSS conflict
- Renamed conflicting `.status-dot` class to `.task-status-dot` in `styles.css`.
- Resolved an issue where a later CSS rule caused the backend health status dot to appear as a blue pulsing circle instead of the intended red error state.

### [2026-07-23] — Implemented chat response interruption ("Stop Generating")
- Added `AbortController` and `stopStreaming()` in frontend (`App.tsx`), replacing the send button with a stop button during active streaming and adding `Esc` key shortcut & auto-interrupt on new prompt.
- Added raw `Request` client disconnect checking (`raw_request.is_disconnected()`) in backend SSE stream generator (`main.py`) to halt LLM token generation and graph steps immediately.
- Finalized partial generated tokens cleanly into chat history upon interruption and marked running tool calls as interrupted.

## [2026-07-23] — Added Gemini & Ollama Cloud support with model switcher
- Integrated `langchain-google-genai` for Google Gemini and added `ollama_cloud` support with optional Bearer token headers.
- Added model selection options per provider (including `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemma4:31b-cloud`, `nemotron-3-super:cloud`) in both `SettingsZone` and the chat composer.
- Updated `/chat` endpoint and health checks to handle dynamic provider and model overrides.

## [2026-07-22] — Converted EQUITY_L.csv to stocks.json
- Converted raw `EQUITY_L.csv` into a structured JSON file at `backend/app/search/data/stocks.json` containing 2,387 stocks with fields `symbol`, `name`, `isin`, `series`, and `exchange: "NSE"`.
- Updated `backend/app/search/stocks_router.py` to load `stocks.json` instead of parsing CSV at runtime.

## [2026-07-22] — Implemented global stock search and chat integration
- Created `backend/app/search/stocks_router.py` providing `GET /api/search/stocks` which serves an in-memory cached list of equities from a local CSV.
- Created `frontend/src/components/StockSearch.tsx` to provide a premium autocomplete dropdown replacing the static search bar placeholder.
- Integrated the search bar to automatically switch to the Chat tab and pre-fill a contextual analysis prompt upon ticker selection.

## [2026-07-22] — Wrote High_Level_Overview.md from full codebase audit
- Documented all backend modules, ORM models, API endpoints, LangGraph pipelines (chat agent + deep research), frontend architecture, and data flows in `docs/High_Level_Overview.md`.
- Covers infrastructure (Docker Compose, env vars), all 14 agent tools, the 7-node research pipeline, evidence/citation system, briefing service, and frontend component tree.
- Added maintenance rules for both `High_Level_Overview.md` and `CHANGES.md` to `.gemini/instructions.md`.

## [2026-07-22] — Setup documentation tracking
- Added High_Level_Overview.md and CHANGES.md to `dev/docs/`
- Why: To maintain structured architectural context and a rolling changelog.
- Updated project instructions with rules for maintaining these files.
