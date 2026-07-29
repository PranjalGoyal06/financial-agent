### [2026-07-29] — Fixed auto-switching behavior for Node events and logs
- Refactored auto-switching in `ResearchLayout.tsx` to detect node status transitions (e.g. pending to running) instead of continuous enforcement.
- Ensures the OrchestrationGraph only auto-focuses when a node changes state, leaving the user with full manual control over node selection between status updates.
- Why: Fixes an issue where users were unable to manually check the status and logs of completed or skipped nodes while a run was still active.


### [2026-07-29] — Fixed EvidenceItem Validation, Discovered Tickers State & UI Node Styling
- Expanded `EvidenceItem.source` literal options to include `"reconciliation_node"` in [`backend/app/evidence/schemas.py`](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/evidence/schemas.py#L55).
- Added `discovered_tickers` to `ResearchState` in [`backend/app/research/state.py`](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/state.py#L40) and `initial_state` in [`backend/app/research/router.py`](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/router.py#L60).
- Normalized yfinance ticker downloads with `normalize_ticker_symbol` in `portfolio_synthesis_node` in [`backend/app/research/nodes/synthesis.py`](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/nodes/synthesis.py#L380).
- Scoped transparent background for `.graph-node--informational` in [`frontend/src/features/research/research.css`](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/features/research/research.css#L243) to pending status only.
- *Why*: Resolves `ValidationError` crash during portfolio synthesis, enables candidate pass-through from `discover_screen` to `plan_tickers`, fixes missing symbol warnings on Indian equities, and ensures completed reconciliation nodes render proper status backgrounds in the UI.

### [2026-07-29] — Fixed NameError for reset_gemini_circuit_breaker in planner.py
- Added missing import `from app.llm.provider import reset_gemini_circuit_breaker` to [`backend/app/research/nodes/planner.py`](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/nodes/planner.py#L18).
- *Why*: Fixed `NameError: name 'reset_gemini_circuit_breaker' is not defined` crash when `plan_macro_sector` node executes at the start of a research run.

### [2026-07-29] — Dynamic Nifty 500 Screener Universe
- Replaced the hardcoded 31-stock `SCREENER_UNIVERSE` in `discovery.py` with a dynamically loaded Nifty 500 list from `sample_imports/ind_nifty500list.csv`.
- Why: Vastly expands the discoverable universe for the research node without requiring API requests to NSE, providing immediate utility and significantly more candidate surfaces.
- Invalidates the assumption that discovery screening only runs on a highly constrained static MVP list.

### [2026-07-29] — Nemotron Cloud Model Tag, Gemini Rate-Limiting & Research DAG Fixes
- Updated `ollama_cloud_model` to `"nemotron-3-super:cloud"` and default Gemini model to `"gemini-3.5-flash-lite"`, aligning chat UI dropdown and research node model selection.
- Implemented `ThrottledChatGoogleGenerativeAI` with 1-RPM pacing and 1-strike per-run circuit breaker to handle Gemini quota limits cleanly without spamming requests.
- Fixed `AttributeError` in `macro_synthesis_node`, changed `portfolio_synthesis_node` fallback to log `node_warning`, and updated frontend ReactFlow node ID to `'reconcile_with_prior'`.
- *Why*: Resolves 404 model errors, 429 quota log spam, and frontend DAG status stuck in pending.

### [2026-07-29] — Tracked Scheduled 7 AM Research Run End-to-End
- Identified and monitored scheduled deep research run `run_5d057d4cded1` (07:00 IST – 07:37 IST).
- Documented node progression across all 13 execution stages, model fallbacks, rate-limit warnings, and generated artifacts.
- Why: Validated end-to-end autonomous research run execution and documented system findings without modifying product source code.

### [2026-07-29] — Unified Slash Command Graphs into MasterGraph
- Implemented `MasterGraph` containing all specialized subgraphs (`paisa_agent`, `compare_graph`, `create_artifact_graph`, `recommend_graph`) routed by a single top-level state containing a `slash_command` string.
- Removed custom manual routing and condition logic from `backend/app/main.py`, drastically simplifying the `/chat` endpoint stream handler.
- Fixed mock test leaks and route prefixing bugs that were throwing 404s and 500s across `test_chat_endpoint.py`, `test_market_endpoints.py`, and `test_portfolio_endpoints.py`.
- *Why:* Ensures slash command executions are properly processed through the `langgraph` checkpointer, persisting all outputs (`AIMessage`) seamlessly to the chat session database history.

# Changes

### 2026-07-28 — Chat layout fixes and prompt chips removal
- Removed prompt chips from `Home.tsx` to declutter the interface.
- Fixed a structural scrolling issue in `styles.css` by locking `.app-shell` to `100vh` and explicitly enabling `overflow-y: auto` on sidebars, preventing the main container from scrolling out of bounds.
- Increased the docked chat container's bottom padding (`96px`) across `Home.tsx`, `ChatHome.tsx`, and `styles.css` to lift the chat box significantly from the bottom edge.
- Why: Ensures the chat composer is comfortably within bounds on all viewports without being clipped or crowded by other elements.

### [2026-07-29] — Fixed Sparkline Visual Drop Artifact Bug & Missing Math Import
- Filtered out `NaN` and non-positive `Close` values in `YFinanceProvider.get_historical` (`backend/app/market_data/provider.py`) using `df.dropna(subset=["Close"])`.
- Added missing `import math` to top of `backend/app/main.py` and added defensive `NaN` and `> 0` checks in `_fetch_sparkline_real`.
- Added array sanitization in `Sparkline` component (`frontend/src/App.tsx`) to filter non-numeric, `NaN`, non-finite, or `0` values before calculating SVG points.
- Why: Resolves `NameError: name 'math' is not defined` during sparkline fetching and fixes `yfinance` returning a trailing `NaN` bar for active/in-progress trading sessions.

### [2026-07-29] — Added Auto-Migration for `watchlist_id` Column in `research_schedules`
- Added schema migration statement in `init_db()` (`app/db.py`) to execute `ALTER TABLE research_schedules ADD COLUMN IF NOT EXISTS watchlist_id VARCHAR;`.
- Executed migration script against existing database.
- Why: Fixes `sqlalchemy.exc.ProgrammingError: column "watchlist_id" of relation "research_schedules" does not exist` when saving schedules for existing tables.

### [2026-07-28] — Added Active Schedules Manager & Dynamic APScheduler Registration
- Built `ActiveSchedulesModal.tsx` component to list active research schedules, next execution times, target watchlists, and delete controls.
- Added `watchlist_id` binding to `ResearchScheduleModel` in `models.py` and updated `/api/research/schedule` endpoints in `router.py`.
- Updated `scheduler.py` with `register_schedule_job` and `unregister_schedule_job` for dynamic runtime APScheduler synchronization.
- Added `Schedules (N)` button in `ResearchLayout.tsx` header for instant schedule inspection.
- Why: Provides full UI transparency into saved schedules and guarantees instant registration with APScheduler without server restarts.

### 2026-07-28 — Backend Bugfixes (Gemini Thinking, utc_now Type Error, & json_mode for Structured Outputs)
- Conditionally added `thinking_budget=0` and `include_thoughts=False` to `ChatGoogleGenerativeAI` instantiation in `backend/app/llm/provider.py` (only for models supporting reasoning, i.e. containing "pro" or "thinking" in their name).
- Fixed `utc_now` helper in `backend/app/main.py` to return a `datetime` object instead of an ISO string, using `.isoformat()` only for SSE JSON serialization.
- Defaulted structured models to use `json_mode` instead of `function_calling` for the Gemini provider in `backend/app/llm/provider.py`.
- Why: Fixes:
  1. A `thought_signature` missing 400 validation error on Gemini 3.x reasoning models during tool use, while preventing "400 Request contains an invalid argument" errors on standard/lite models (which do not support the legacy `thinking_budget` configuration).
  2. A SQLAlchemy `DataError` on `chat_session.updated_at` due to assigning a string instead of a `datetime` object.
  3. Structured output parsing failures (e.g. `ComparisonCard` validation errors) on Gemini 3.5 Flash by leveraging native API-level JSON Schema constraints.

### [2026-07-27] — Fixed TATAMOTORS.NS Error in discovery.py
- Updated the hardcoded `TATAMOTORS.NS` ticker in `SCREENER_UNIVERSE` inside `discovery.py` to `TMPV.NS`.
- Why: TATAMOTORS is deprecated (delisted) and was causing a `YFPricesMissingError` during the `discover_screen` node's yfinance download step, failing the batch check.
- Invalidates no prior plans.

### [2026-07-27] — Quick Fixes for SSE Routing and Evidence Metadata
- Fixed the Vite proxy bypass bug in the frontend by ensuring the `EventSource` connection in `useResearchRun.ts` points to `/api/research/stream` instead of `/research/stream`.
- Added a `metadata` dictionary field to the `EvidencePack` schema in `schemas.py` to resolve an `AttributeError` crashing the `collect_tickers_round2` pipeline node.

### [2026-07-27] — Fixed SSE Event Mismatches and Silenced yfinance Logs
- Fixed a silent event-loss bug in `logger.py` by maintaining strong references to background `asyncio` database write tasks.
- Restored exception tracebacks in the `research_run_events` table payload, and decoupled UI node failure signaling (`node_error`) from the durable exception logs.
- Resolved a state mismatch where stopped runs collapsed into "failed"; added explicit `run_cancelled` handlers in both the backend and frontend.
- Silenced noisy Pandas deprecation warnings and HTTP 404 prints from `yfinance` in `discovery.py` by forcing `auto_adjust=False` and `ignore_tz=True`.
- Fixed duplicate node descriptions in the frontend inspector panel.
- *Why:* Ensures the frontend graph UI transitions to red/failed or cancelled accurately without getting permanently stuck in "running", and prevents silent data loss of critical orchestration audit logs.

### [2026-07-27] — Stripped Placeholder UI and Added Rename/Delete for Research Runs
- Removed mock `DiscoveryDesk` and `EvidenceDrawer` implementations from the `ResearchLayout.tsx` frontend to eliminate confusion around placeholder vs actual pipeline data.
- Added `title` column to `ResearchRunModel` and performed a direct PostgreSQL schema update.
- Implemented `PATCH /api/research/runs/{run_id}` and `DELETE /api/research/runs/{run_id}` endpoints in `router.py` to allow custom naming and removal of historical runs.
- Enhanced the `RunHistorySidebar` with contextual "More options" dropdown menus mapping to the new edit and delete operations.
- *Why:* Prevents users from mistaking static mock data for active research output, and adds necessary lifecycle management for organizing and pruning past research runs.

### [2026-07-27] — Home Page UI Improvements & Chat Integration
- Redesigned the Home tab to feature a prompt composer, a list of recent chat sessions, and suggested prompt chips, acting as a gateway to start new threads.
- Refactored `BriefingZone` styling to "card-ify" the climate strip, expose the existing news carousel, and add an illustrated empty state for the Action Desk.
- Integrated the new FastAPI `/api/chat` router with the frontend, moving the chat experience from a single flat list into a robust session-based `ChatBrowser` view (at `/chat`) with sidebar navigation.
- Fixed a couple of lingering TypeScript build errors in the Research tab (type mismatches with `selectedRunId` and `NODE_SUMMARIES` indexing).
- *Why:* Unifies the user experience by creating a clear distinction between the "dashboard" (Home) and the deep-dive conversational space (Chat), resolving the news integration gap, and polishing the aesthetic.

### [2026-07-27] — Migrated Frontend to Client-Side Routing and Namespaced Backend APIs
- Refactored FastAPI routers to use a unified `/api/` prefix for backend endpoints (`/api/research`, `/api/artifacts`, etc.) and updated the frontend `vite.config.ts` proxy.
- Implemented `react-router-dom` in the React frontend, transitioning from state-based `activeTab` navigation to true URL-based client-side routing (e.g., `/home`, `/portfolio`, `/research`).
- Kept global state (like chat messages) preserved across navigation by maintaining the state within the `App` shell component that houses the `<Routes>`.
- *Why:* Enables direct deep-linking into specific application views and prevents browser URL collisions with the backend API root when serving both from the same domain locally.

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

### [2026-07-27] — Fixed Research Run UI Bugs
- Updated `ResearchLayout.tsx` to read the active run ID directly from the URL (`/research/:runId`) via `react-router-dom`, ensuring the active research view persists perfectly across hard refreshes.
- Instrumented early-stage LangGraph nodes (`planner.py`, `collection.py`, `synthesis.py`) with `get_run_logger` to emit realtime SSE `node_start` events, resolving a UI lag bug where early nodes appeared permanently "pending".
- Added a `NODE_SUMMARIES` human-readable dictionary to the frontend Node Inspector to display a clear 1-2 sentence description of a node's responsibilities to the end-user.
- *Why:* Directly addresses bugs identified during manual UI testing, significantly improving real-time observability of the research graph execution and preserving layout state on navigation.

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
### 2026-07-27 — Add dedicated chat page with persistent sessions
- Extracted chat logic into `ChatPage.tsx` and simplified `Home.tsx` to serve as a routing shell entry point.
- Created `ChatSessionModel` and `ChatMessageModel` to linearly persist chat history, including tool inputs and outputs as JSON.
- Created `/api/chat/sessions` endpoints and modified the `stream_chat_events` logic to stream and persist data simultaneously.
### 2026-07-29 — Make action cards horizontally scrollable
- Updated `.action-cards` and `.action-card` styles in `frontend/src/styles.css` to use flexbox for a single horizontal scrollable row instead of a wrapping grid.
- Improves UI compactness and ensures action cards don't consume excessive vertical space on smaller screens.

### 2026-07-29 — Keep climate cards on one line
- Changed `.climate-strip` to use a non-wrapping flexbox instead of CSS grid to ensure cards stay on a single line on smaller screens.
- Updated `.climate-metric` with `flex: 1` and `min-width: 0` to shrink gracefully.
- Added text truncation (`text-overflow: ellipsis`) to `.climate-label` and `.climate-val` to prevent internal text from stretching the cards or wrapping.
