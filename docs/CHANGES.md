# Changes

### [2026-07-27] — Hotfixes for Research Run Logging & Missing YFinance Tickers
- Fixed a PostgreSQL `ForeignKeyViolationError` in `backend/app/research/router.py` by deferring the first `log_event` emission until after the `ResearchRunModel` is successfully committed to the database.
- Fixed 404 errors for Indian stocks (like `LEMONTREE` and `TATAPOWER`) by explicitly wrapping raw ticker queries with `normalize_ticker_symbol` in `backend/app/research/nodes/planner.py` and updating `_to_yf_symbol` in `main.py` to use the unified normalizer.

### [2026-07-27] — Fixed Index Data Retrieval & Added Briefing Cache
- Fixed a bug in `backend/app/market_data/provider.py` where `normalize_ticker_symbol` erroneously appended `.NS` to market indices (like `^INDIAVIX` and `^NSEI`), causing 404s.
- Implemented an in-memory 10-minute TTL cache in `backend/app/briefing/router.py` to prevent redundant computations and external API calls every time the home page is visited.
- Wrapped local `ChatOllama` invocations in an `asyncio.Semaphore(2)` in `backend/app/llm/provider.py` to prevent severe OS freezing caused by unbounded concurrent local compute.
- Implemented an `_ACTIVE_TASKS` registry in `router.py` along with a `POST /research/cancel/{run_id}` endpoint to gracefully abort background LangGraph processes via `asyncio.CancelledError`.
- Added a "Stop Run" UI button in `ResearchLayout.tsx` for cancelling active jobs in real-time.
- *Why:* Unbounded async fanout for local inference was causing Mac lockups. The new cancellation flow restores control to the user if a job gets stuck or takes too long.
- Updated `backend/app/graph.py` to use `prompt` instead of `state_modifier` in `create_react_agent`.
- Removed `include_thoughts=True` from `ChatGoogleGenerativeAI` in `backend/app/llm/provider.py` to resolve the `thought_signature` 400 validation error when using Gemini 3.1 Pro (High) with LangChain tools.
- *Why:* Fixes a `TypeError` due to an incompatible API change in the installed LangGraph version, and fixes a tool calling issue with Gemini. No structural change.

### [2026-07-27] — Fixed Default Watchlist Bug
- Fixed a missing database commit when dynamically generating the default "My Portfolio" watchlist, ensuring it persists across API requests.

### [2026-07-27] — Revamped Watchlist UI & Added Rename/Delete API
- Added `PATCH /api/watchlists/{id}` and `DELETE /api/watchlists/{id}` to `watchlist/router.py` to allow editing and removing custom watchlists.
- Completely rewrote the Watchlists view in `PortfolioZone.tsx` into a new `WatchlistsView.tsx` component, introducing broker-grade aesthetics and inline actions.
- Replaced manual ticker entry with a dynamic autocomplete search box powered by the `InstrumentModel` (`/api/search/stocks`).
- *Why:* Elevates the UI from a basic list to a premium, data-dense interface and provides full CRUD capabilities for watchlists.

### [2026-07-27] — Refactored Search Autocomplete to use Postgres
- Updated `backend/app/search/stocks_router.py` to query the `InstrumentModel` instead of loading `stocks.json` into memory.
- Deprecated and deleted `stocks.json`, centralizing all stock metadata natively inside the database.
### [2026-07-27] — Implemented LangGraph Context Management & Memory Trimming
- Added `langgraph-checkpoint-postgres` checkpointer (`app/checkpointer.py`) wrapped in FastAPI's request lifecycle to persist conversation history.
- Integrated `trim_messages` in `app/graph.py` to maintain a token limit (max 8000 tokens) using `count_tokens_approximately` while preserving the full log in Postgres.
- Updated `ChatRequest` schema and `App.tsx` state to thread chat sessions via a `thread_id` UUID generated per run and emitted over SSE.
- *Why:* Fixes the stateless backend bug, allowing follow-up chat queries (like `/create-artifact document this comparison`) to parse intent correctly based on previous conversation turns, without exploding the context window.
### [2026-07-27] — Surfaced Watchlists and Instrument Metadata to PAISA Agent & Frontend
- Added `list_watchlists_tool`, `get_watchlist_items_tool`, and `get_instrument_metadata_tool` to the LangGraph `AGENT_TOOLS` so PAISA can autonomously interact with customized watchlists and local metadata.
- Implemented full REST CRUD endpoints for Watchlists in `app/watchlist/router.py`.
- Built an interactive Watchlist Management UI inside `PortfolioZone.tsx` to create and populate custom stock lists.
- Integrated `@` mentions into the `App.tsx` chat composer to quickly inject watchlist slugs directly into conversations.
### [2026-07-27] — Completed Watchlist UI & Synthesis Integration
- Added `GET /watchlists` endpoint to expose all user watchlists to the frontend.
- Updated `ResearchLayout.tsx` to include a dynamic watchlist selector for triggering and scheduling new research runs.
- Enhanced Ticker Synthesis LLM prompts (`nodes/synthesis.py`) to inject exact `market_cap_bucket`, `industry`, and `summary` from the new `InstrumentModel`, dramatically improving the context baseline for thesis drafting.

### [2026-07-27] — Augmented InstrumentModel and Seeded YFinance Data
- Upgraded the `InstrumentModel` schema to capture more static stock metadata (e.g., market cap buckets, country, industry, full_time_employees, website).
- Added a `raw_yfinance_info` JSONB column to archive the original payload for future-proofing and auditing.
- Wrote `seed_instruments.py` to iteratively populate the database with computed/normalized deterministic fields from yfinance while respecting rate limits.
- Updated `planner.py` to lazy load these new schema fields accurately.
### [2026-07-27] — Refactored Watchlist Architecture
- Introduced `WatchlistModel` to support named custom watchlists, chat mentions (`@` command), and selective execution in research runs.
- Updated `get_watchlist` in `watchlist/service.py` to dynamically serve the user's holdings for the default "portfolio" watchlist, preventing data duplication.
- Added `watchlist_id` to `ResearchRunModel` and `/research/trigger` endpoint to allow targeting specific watchlists for deep research.

### [2026-07-26] — Implemented 3-Tier Model Architecture Across Research Orchestration
- Configured Tier 1 (`gemma4:e4b` local), Tier 2 (`nemotron` via Ollama Cloud), and Tier 3 (`Gemini-3.6-Flash`) across all 14 graph nodes.
- Mapped low-complexity search/triage query generation to Tier 1, mid-level reasoning (spillover extraction, candidate grading, red-teaming, draft synthesis, drift reports) to Tier 2 `nemotron`, and high-stakes financial decisions (CIO Judgment & Portfolio Stance) to Tier 3 `Gemini-3.6-Flash`.
- Prevents local CPU thermal throttling while preserving Gemini API quota strictly for critical recommendation decision points.

### [2026-07-26] — Completed Research Hub UI & Backend Integration
- Wired frontend Research Hub to backend execution pipeline featuring real-time Server-Sent Events (SSE) streaming with a "backlog-replay" synchronization mechanism.
- Converted Event Logger to dual-write architecture pushing JSONB log streams to PostgreSQL while concurrently feeding live connected clients.
- Refactored `ResearchLayout.tsx` utilizing React Flow groups and CustomGroupNode, allowing intricate nesting (collapsible `ticker_synthesis` sub-steps) and dynamically rendering node states (`running`, `failed`, `completed`) from active SSE logs.
- Added `apscheduler` on backend startup exposing task scheduling CRUD, surfaced in the UI via the "Schedule" button on the Research header.
- Resolved layout overflows preventing the unified sidebar (Run History/Discovery Desk) from correctly collapsing alongside the Orchestration Graph, and confined the Evidence Drawer properly beneath the header.
- *Why:* Enables operators to seamlessly trigger, monitor, and retroactively review large asynchronous agentic pipelines while maintaining high-fidelity UI states independent of backend scale limits.

### [2026-07-25] — Configured Gemma 4 e4b as Default Local Ollama Model
- Added `gemma4:e4b` ("Gemma 4 e4b (Local)") alongside `qwen3.5:latest` ("Qwen 3.5 (Local)") to UI model configuration options in `models.ts`, `App.tsx`, and `SettingsZone.tsx`.
- Updated default local model setting in `config.py` and `.env` to `gemma4:e4b`.
- Updated research synthesis node fallback provider to dynamically use local Ollama config.
- Built `ResearchRunLogger` (`backend/app/research/logger.py`) to record structured JSON Lines (`.jsonl`) events to `logs/research/{run_id}.jsonl`.
- Instrumented key graph nodes (`discovery`, `triage`, `reconciliation`, `persist`, `workflow`) to capture LLM call traces, API traffic metrics, sufficiency gating scores, and exception tracebacks.
- Added `GET /research/logs/{run_id}` REST endpoint allowing developer log inspection with filtering by `node` or `event_type`.
### [2026-07-25] — Completed Deep Research Orchestration Refactor
- Completely refactored the LangGraph pipeline from 7 nodes to 14 nodes, enabling dynamic discovery of off-watchlist stocks, multi-round evidence gathering, sufficiency gating, and robust synthesis.
- Implemented a 5-step `ticker_synthesis` pipeline including Draft, Critique, Revision, and Frontier Judgment (with fallback).
- Added `discovery.py` to identify candidates via a Nifty 500 local screener and LLM spillover extraction, and `reconciliation.py` to generate drift reports against prior Chroma artifacts.
- Upgraded the `collection.py` node to use LLMs for targeted query generation rather than static f-strings.
- Resolves the structural limitations of the single-pass architecture and massively improves the depth, accuracy, and utility of the research output.
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
