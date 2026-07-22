# High Level Overview — SCALE Finance Agent (`dev/`)

> **PAISA** — Portfolio Advisor and Investment Strategist Agent.
> A portfolio-aware investment intelligence system with a React chat UI, a
> FastAPI backend, a LangGraph ReAct agent, and a multi-stage deep research
> pipeline.

This document covers the `dev/` workspace. The `main/` workspace is a separate
reference worktree and is not modified during normal development.

---

## 1. Repository Layout

```
dev/
├── backend/
│   ├── app/                    # FastAPI application package
│   │   ├── main.py             # App entry point, endpoints, SSE streaming
│   │   ├── graph.py            # LangGraph ReAct chat agent
│   │   ├── config.py           # Pydantic Settings (env vars)
│   │   ├── db.py               # Async SQLAlchemy engine, session factory
│   │   ├── models.py           # ORM models (User, Portfolio, Holdings, …)
│   │   ├── schemas.py          # API request/response Pydantic models
│   │   ├── portfolio_parser.py # Tradebook CSV parser (Zerodha / Groww / generic)
│   │   ├── portfolio_service.py# Portfolio CRUD + FIFO lot-matching
│   │   ├── agents/reactive/    # (reserved — agent logic lives in graph.py)
│   │   ├── llm/                # LLM provider factory (Groq / Ollama)
│   │   ├── market_data/        # Quotes, history, resolver, cache, REST router
│   │   ├── search/             # Tavily web search client, cache, local stock search router
│   │   ├── portfolio/          # Portfolio query helpers + agent tools
│   │   ├── quant/              # Quantitative metrics (returns, vol, Sharpe, …)
│   │   ├── ta/                 # Technical analysis (SMA, EMA, RSI)
│   │   ├── evidence/           # Evidence schemas, citation validation, compliance
│   │   ├── research/           # Deep research pipeline (graph, nodes, prompts, store)
│   │   ├── briefing/           # Morning briefing service + router
│   │   └── watchlist/          # Watchlist service (union of holdings + watched)
│   └── tests/                  # pytest suite
├── frontend/
│   ├── src/
│   │   ├── main.tsx            # React entry point
│   │   ├── App.tsx             # App shell, chat, sidebar, portfolio drawer
│   │   ├── components/         # Reusable UI components (e.g., StockSearch.tsx)
│   │   ├── PortfolioZone.tsx   # Portfolio dashboard tab
│   │   ├── BriefingZone.tsx    # Morning briefing tab
│   │   ├── features/research/  # Research orchestration graph viewer
│   │   ├── styles.css          # Core app styles
│   │   └── figma-styles.css    # Figma-exported design tokens
│   ├── vite.config.ts          # Dev server + API proxy
│   └── package.json
├── docs/                       # Project documentation
├── experiments/                # One-off experiment scripts
├── sample_imports/             # Sample CSV tradebooks for testing
├── docker-compose.yml          # Postgres + ChromaDB containers
├── pyproject.toml              # Python project metadata + dependencies
└── .env                        # Local environment variables
```

---

## 2. Infrastructure & Configuration

### 2.1 Docker Compose Services

| Service      | Image                    | Port        | Purpose                       |
| ------------ | ------------------------ | ----------- | ----------------------------- |
| **postgres** | `postgres:16-alpine`     | `5432:5432` | Primary data store            |
| **chroma**   | `chromadb/chroma:0.5.23` | `8001:8000` | Vector store for research RAG |

### 2.2 Environment Variables ([config.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/config.py))

| Variable          | Default                                           | Purpose                             |
| ----------------- | ------------------------------------------------- | ----------------------------------- |
| `DATABASE_URL`    | `postgresql+asyncpg://…@127.0.0.1:5432/scale_finance` | Async Postgres connection       |
| `LLM_PROVIDER`    | `groq`                                            | `groq` or `ollama`                  |
| `GROQ_API_KEY`    | —                                                 | Groq Cloud API key                  |
| `GROQ_MODEL`      | —                                                 | Groq model override                 |
| `OLLAMA_BASE_URL` | `http://localhost:11434`                           | Local Ollama endpoint               |
| `OLLAMA_MODEL`    | `qwen3.5:latest`                                  | Ollama model name                   |
| `TAVILY_API_KEY`  | —                                                 | Tavily web search API key           |
| `CHROMA_HOST`     | `localhost`                                        | ChromaDB host                       |
| `CHROMA_PORT`     | `8001`                                             | ChromaDB port                       |
| `cors_origins`    | `localhost:5173`, `127.0.0.1:5173`                 | Allowed CORS origins                |

---

## 3. Backend Architecture

### 3.1 FastAPI Application ([main.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/main.py))

**Lifespan:** On startup calls `init_db()` to create all tables.

**API Endpoints:**

| Method   | Path                          | Purpose                                               |
| -------- | ----------------------------- | ----------------------------------------------------- |
| `GET`    | `/health`                     | Health check + runtime info                           |
| `POST`   | `/chat`                       | SSE-streamed chat with the ReAct agent                |
| `GET`    | `/portfolio`                  | Raw portfolio holdings for a user                     |
| `GET`    | `/portfolio/quotes`           | Live quotes + sparklines for held tickers             |
| `GET`    | `/portfolio/valued`           | Full valued portfolio with P&L + research recs        |
| `POST`   | `/portfolio/upload`           | Tradebook CSV upload → FIFO lot-matching → save       |
| `GET`    | `/tools/resolve-asset`        | Free-text → NSE/BSE ticker resolution *(market_data)* |
| `GET`    | `/tools/quote`                | Cached stock price snapshot *(market_data)*            |
| `GET`    | `/tools/historical-data`      | Cached OHLCV bars *(market_data)*                      |
| `GET`    | `/api/search/stocks`          | Local CSV-based stock autocomplete search              |
| `POST`   | `/research/trigger`           | Kick off async deep research run                      |
| `GET`    | `/research/status/{run_id}`   | Poll research run status                              |
| `GET`    | `/research/recommendations`   | Latest ticker recommendations from research           |
| `GET`    | `/research/artifact/{run_id}/{type}` | Fetch a stored research report             |
| `GET`    | `/briefing/`                  | Generate morning briefing                             |

**SSE Chat Protocol** (`POST /chat`):
The chat endpoint returns a `text/event-stream` with these event types:
- `run_start` — agent invocation begun
- `token` — incremental LLM token
- `tool_call` — tool invocation with name + args
- `tool_result` — tool output (status + data)
- `error` — error during processing
- `final` — stream complete

Helper `_build_portfolio_context(session)` formats the user's holdings into a
markdown table injected into the agent's system prompt at runtime.

### 3.2 Database Layer

**Engine & Sessions** ([db.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/db.py)):
- Async SQLAlchemy engine with `NullPool` and `pool_pre_ping`.
- `AsyncSessionLocal` factory; `get_session()` FastAPI dependency.

**ORM Models** ([models.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/models.py)):

| Model                  | Table                | Key Columns                                                                 |
| ---------------------- | -------------------- | --------------------------------------------------------------------------- |
| **UserModel**          | `users`              | `id` (str PK), `created_at`                                                |
| **PortfolioModel**     | `portfolios`         | `user_id` FK, `name`, `realized_pnl`, timestamps                           |
| **PortfolioImportModel** | `portfolio_imports` | `portfolio_id` FK, `source_filename`, `status`, `imported_count`, `rejected_count` |
| **HoldingModel**       | `holdings`           | `portfolio_id`/`import_id` FKs, `raw_ticker`, `canonical_ticker`, `exchange`, `asset_class`, `quantity`, `avg_cost`, `currency`, `purchase_date` |
| **MarketSnapshotModel** | `market_snapshots`  | `ticker`, `snapshot_type`, `params_hash` (unique), `payload_json`, `provider`, `fresh_until` |
| **InstrumentModel**    | `instruments`        | `ticker` PK, `name`, `exchange`, `sector`, `industry`, `asset_class`, `aliases` (JSON) |
| **WatchlistItem**      | `watchlist_items`    | `user_id` FK, `canonical_ticker`, `exchange`                               |
| **ResearchArtifact**   | `research_artifacts` | `run_id`, `artifact_type` (macro/sector/ticker/portfolio), `target`, `content_markdown`, `evidence_pack_json`, `recommendation`, `confidence_score` |

---

## 4. LangGraph Chat Agent ([graph.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/graph.py))

The chat agent is built with `create_react_agent` from LangGraph. It uses a
**`SequentialToolNode`** subclass of `ToolNode` that executes tool calls one at
a time to avoid race conditions during SSE streaming.

### System Prompt

Injected at runtime with `{portfolio_context}` — the user's current holdings
formatted as a markdown table. The agent persona is **PAISA** (Portfolio Advisor
and Investment Strategist Agent).

### Agent Tools (14 tools)

| Category        | Tool                              | Source Module       |
| --------------- | --------------------------------- | ------------------- |
| **Market Data** | `resolve_asset_tool`              | `market_data/tools` |
|                 | `get_quote_tool`                  | `market_data/tools` |
|                 | `get_historical_data_tool`        | `market_data/tools` |
|                 | `get_fundamentals_tool`           | `market_data/tools` |
| **Search**      | `web_search_tool`                 | `search/tools`      |
| **Quant**       | `compute_returns_tool`            | `quant/tools`       |
|                 | `compute_volatility_tool`         | `quant/tools`       |
|                 | `compute_max_drawdown_tool`       | `quant/tools`       |
|                 | `compute_sharpe_ratio_tool`       | `quant/tools`       |
|                 | `compute_52w_distance_tool`       | `quant/tools`       |
| **Tech Analysis**| `compute_sma_tool`               | `ta/tools`          |
|                 | `compute_ema_tool`                | `ta/tools`          |
|                 | `compute_rsi_tool`                | `ta/tools`          |
| **Research**    | `get_ticker_recommendation_tool`  | `portfolio/tools`   |

### Execution Flow

```
User message → LLM Agent Node
                  ├── (has tool_calls) → SequentialToolNode → back to LLM
                  └── (no tool_calls)  → END (final response)
```

The LLM decides autonomously which tools to invoke and may loop through
multiple tool-call rounds before producing a final response.

---

## 5. Deep Research Pipeline ([research/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/))

A multi-stage LangGraph `StateGraph` that produces structured investment
research reports with evidence-backed citations.

### 5.1 State Schema ([state.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/state.py))

**`ResearchState(TypedDict)`** tracks:
- **Targets:** `tickers`, `sectors`, `ticker_to_sector` mapping
- **Evidence packs:** `macro_evidence`, `sector_evidence` (dict), `ticker_evidence` (dict), `portfolio_evidence`
- **Synthesis outputs:** `macro_synthesis`, `sector_synthesis` (dict), `ticker_synthesis` (dict), `portfolio_synthesis`
- **Metadata:** `run_id`, `user_id`, `errors`

Concurrent state updates use `Annotated[dict, merge_dict]` and
`Annotated[list, append_list]` reducers.

### 5.2 Pipeline Graph ([graph.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/graph.py))

```
START → planner → collection → macro_synthesis → sector_synthesis
      → ticker_synthesis → portfolio_synthesis → persist → END
```

Seven nodes, executed sequentially. Intra-node parallelism (fan-out across
tickers and sectors) is handled with `asyncio.gather` inside each node.

### 5.3 Node Details ([nodes/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/nodes/))

| Node                     | File              | What It Does                                                                                  |
| ------------------------ | ----------------- | --------------------------------------------------------------------------------------------- |
| **planner**              | `planner.py`      | Resolves user's watchlist (holdings ∪ watchlist) → tickers + sectors. Caches instrument metadata in the `instruments` table, falls back to yfinance. |
| **collection**           | `collection.py`   | Parallel evidence gathering via `asyncio.gather`: Tavily macro/sector/ticker news, Chroma prior research retrieval, yfinance quotes + fundamentals, quant metrics (CAGR, Sharpe, max drawdown), TA indicators (RSI-14, SMA-50), portfolio return correlation matrix. |
| **macro_synthesis**      | `synthesis.py`    | LLM structured output → `MacroSynthesis` (outlook, key drivers, analysis markdown). Citation validation against evidence pack. |
| **sector_synthesis**     | `synthesis.py`    | Parallel LLM calls per sector → `SectorSynthesis` (outlook, drivers, analysis). Citation validation. |
| **ticker_synthesis**     | `synthesis.py`    | Parallel LLM calls per ticker → `TickerSynthesis` (recommendation enum, confidence 0–100, target price, rationale, risk factors, bear case, "kill the company" risk). Receives sector context. |
| **portfolio_synthesis**  | `synthesis.py`    | CIO-persona LLM → `PortfolioSynthesis` (allocation adjustments, top picks, risk aggregates). Receives all upstream context + correlation matrix. |
| **persist**              | `persist.py`      | Writes all artifacts to PostgreSQL (`research_artifacts`) and indexes markdown in ChromaDB (`research_artifacts` collection). |

### 5.4 Prompt Templates ([prompts/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/prompts/))

| File           | Persona                    | Key Requirements                                      |
| -------------- | -------------------------- | ----------------------------------------------------- |
| `macro.py`     | Macroeconomist             | `[id]` citations for every market driver claim         |
| `sector.py`    | Sector analyst             | Indian industry trends, tailwinds/headwinds, policy    |
| `ticker.py`    | Buy-side equity analyst    | Numeric bear case, strict confidence scores, kill-the-company risk |
| `portfolio.py` | Chief Investment Officer   | Allocation adjustments, correlation risk, top picks    |

`__init__.py` exports `format_evidence_pack(pack)` which serializes evidence
items with stable citation IDs (e.g. `[news_a1b2c3d4]`, `[mkt_f1e2d3c4]`).

### 5.5 Research Store ([store.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/store.py))

- **`save_research_artifact(…)`** — Dual-writes to PostgreSQL + ChromaDB.
- **`search_prior_artifacts(query, …)`** — Semantic vector search in Chroma;
  returns `EvidenceItem` objects (`type="prior_artifact"`) for consumption in
  future research runs.

### 5.6 Research Router ([router.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/research/router.py))

`POST /research/trigger` spawns an async background task. Run status is tracked
in-memory (`RUN_STATUS` dict) with DB fallback after server restarts.

---

## 6. Supporting Backend Modules

### 6.1 Market Data ([market_data/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/market_data/))

**Data flow:** Free-text query → **resolver** (yfinance search + heuristic
scoring, India-only filter) → **provider** (`YFinanceProvider` via
`asyncio.to_thread`) → **cache** (PostgreSQL `market_snapshots` with SHA-256
param hash, 90s quote TTL, 24h historical TTL for closed sessions) → response.

Key files:
- [resolver.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/market_data/resolver.py) — `resolve_asset()`, heuristic confidence scoring
- [provider.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/market_data/provider.py) — `YFinanceProvider` implementing `MarketDataProvider` protocol
- [cache.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/market_data/cache.py) — `get_cached()` / `put_cache()` with PostgreSQL upsert
- [schemas.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/market_data/schemas.py) — `MarketQuote`, `HistoricalBar`, `Asset`, `FundamentalsSnapshot`
- [router.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/market_data/router.py) — REST endpoints under `/tools/`

### 6.2 Search ([search/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/search/))

- [client.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/search/client.py) — Tavily API integration with DB-backed cache (20-min TTL, `snapshot_type="search_snapshot"`). Produces `EvidenceItem` objects with stable IDs (`news_<8-hex-sha256(url)>`).
- [tools.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/search/tools.py) — `web_search_tool` for the agent.
- [stocks_router.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/search/stocks_router.py) — `GET /api/search/stocks` serving in-memory stock autocomplete from `data/stocks.json` for the frontend search bar.

### 6.3 Portfolio ([portfolio/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/portfolio/))

- [lib.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/portfolio/lib.py) — `get_ticker_recommendation()` queries latest `ResearchArtifact` for a ticker.
- [tools.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/portfolio/tools.py) — `get_ticker_recommendation_tool` for the agent.

### 6.4 Portfolio Service ([portfolio_service.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/portfolio_service.py))

Handles CSV ingestion with **FIFO lot-matching**: buy trades enqueue lots, sell
trades dequeue from front, accumulating `realized_pnl`. Remaining positions
produce weighted `avg_cost`. Operates atomically within a single DB transaction.

### 6.5 Portfolio Parser ([portfolio_parser.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/portfolio_parser.py))

Parses tradebook CSVs with header auto-detection. Normalizes tickers (strips
`.NS`/`.BO` suffixes, applies corporate renames via `TICKER_RENAMES`). Returns
`ParseResult` with `holdings: list[ParsedHolding]` and `errors: list[CsvFieldError]`.

### 6.6 Quant ([quant/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/quant/))

Pure-Python quantitative finance (no pandas dependency):
- [lib.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/quant/lib.py) — `compute_returns`, `compute_volatility`, `compute_max_drawdown`, `compute_sharpe_ratio` (risk-free = 6.5% India 10Y), `compute_52w_distance`, `compute_correlation_matrix`, `compute_all_metrics`.
- [tools.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/quant/tools.py) — 5 `@tool` wrappers.

### 6.7 Technical Analysis ([ta/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/ta/))

- [lib.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/ta/lib.py) — `compute_sma`, `compute_ema`, `compute_rsi` (Wilder's smoothing). Returns `list[float | None]` aligned with input bars.
- [tools.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/ta/tools.py) — 3 `@tool` wrappers.

### 6.8 Evidence ([evidence/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/evidence/))

- [schemas.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/evidence/schemas.py) — `EvidenceItem` (id, type, source, url, title, freshness, summary), `EvidencePack` (target, items, `item_ids` property).
- [lib.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/evidence/lib.py) — `validate_citations(text, pack)` extracts `[id]` tags via regex and checks against pack IDs. `compute_evidence_sufficiency_score()` scores completeness (0–100). `apply_price_shock()` and `compute_scenario_ev()` for scenario analysis. Compliance audit logging to `paisa.compliance.audit`.

### 6.9 Briefing ([briefing/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/briefing/))

- [service.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/briefing/service.py) — `get_briefing_data()`: market status (NSE hours), climate strip (Nifty 50, India VIX, holdings breadth, net P&L), action desk (high-confidence or shifted research recs, up to 5 cards), news carousel (deduplicated top 5).
- [router.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/briefing/router.py) — `GET /briefing/`.
- [schemas.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/briefing/schemas.py) — `BriefingResponse`, `ClimateData`, `ActionCard`, `NewsItem`, etc.

### 6.10 Watchlist ([watchlist/](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/watchlist/))

- [service.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/watchlist/service.py) — `get_watchlist()` returns the sorted union of held tickers + custom watchlist items. `add_to_watchlist()` / `remove_from_watchlist()` for CRUD. No REST router yet — service-only.

### 6.11 LLM Provider ([llm/provider.py](file:///Users/pranjal/Projects/financial-agent/dev/backend/app/llm/provider.py))

- `get_chat_model(temperature, streaming, provider, model)` — Returns `ChatGroq` or `ChatOllama` based on config.
- `get_structured_model(schema, …)` — Wraps chat model with `.with_structured_output(schema)` for research synthesis nodes.

---

## 7. Frontend Architecture

### 7.1 Stack

- **Framework:** React 18 + TypeScript
- **Build:** Vite 6 (`@vitejs/plugin-react`)
- **Styling:** Vanilla CSS with Figma-exported design tokens
- **Key Libraries:** `@xyflow/react` (graph viz), `lucide-react` (icons), `marked` (markdown rendering), `clsx` + `tailwind-merge` (class utilities)

### 7.2 Vite API Proxy ([vite.config.ts](file:///Users/pranjal/Projects/financial-agent/dev/frontend/vite.config.ts))

All API paths (`/chat`, `/health`, `/portfolio`, `/tools`, `/research`,
`/briefing`) are proxied to `http://127.0.0.1:8000`.

### 7.3 App Shell Layout ([App.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/App.tsx))

```
┌─────────────────────────────────────────────────────────┐
│                     Top Header Bar                      │
│  (search bar, portfolio button, user profile)           │
├──────────┬──────────────────────────┬───────────────────┤
│  Left    │    Main Workspace        │  Right Drawer     │
│  Sidebar │                          │  (Portfolio Quick  │
│  (272px) │  Tabs: Chat | Portfolio  │   View, 340px,    │
│          │        | Research        │   collapsible)     │
│  • Logo  │                          │                    │
│  • Nav   │                          │  Live quotes +     │
│  • CSV   │                          │  sparklines for    │
│    Upload│                          │  held tickers      │
│  • Status│                          │                    │
└──────────┴──────────────────────────┴───────────────────┘
```

**Left Sidebar:** Logo ("PAISA"), nav links (Home/Chat, Portfolio, Research,
Artifacts, Settings), tradebook CSV upload box with validation status, backend
connectivity indicator.

**Main Workspace Tabs:**
- **Chat** — Message stream with `ToolCallCard` components (expandable tool
  invocations), markdown rendering, composer textarea.
- **Portfolio** — `PortfolioZone`: summary cards (market value, unrealized P&L,
  realized P&L), holdings table with AI stance pills and confidence bars.
- **Research** — `ResearchLayout`: orchestration graph viewer (React Flow DAG),
  run history sidebar, node details panel, evidence drawer.

**Right Drawer:** Collapsible quick-view of holdings with live prices, P&L %,
and SVG sparkline charts.

### 7.4 Key Components

| Component                   | File                                                      | Purpose                                              |
| --------------------------- | --------------------------------------------------------- | ---------------------------------------------------- |
| **App**                     | [App.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/App.tsx) | Root shell, chat streaming, state management |
| **PortfolioZone**           | [PortfolioZone.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/PortfolioZone.tsx) | Full portfolio dashboard with valued holdings |
| **StockSearch**             | [StockSearch.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/components/StockSearch.tsx) | Premium stock search autocomplete with chat redirection |
| **BriefingZone**            | [BriefingZone.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/BriefingZone.tsx) | Morning briefing: climate strip, action desk, news |
| **ResearchLayout**          | [ResearchLayout.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/features/research/ResearchLayout.tsx) | Research run viewer with DAG graph |
| **OrchestrationGraph**      | [OrchestrationGraph.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/features/research/components/OrchestrationGraph.tsx) | React Flow DAG of research pipeline execution |
| **RunHistorySidebar**       | [RunHistorySidebar.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/features/research/components/RunHistorySidebar.tsx) | Past research run list |
| **NodeDetailsPanel**        | [NodeDetailsPanel.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/features/research/components/NodeDetailsPanel.tsx) | Execution logs for a selected graph node |
| **EvidenceDrawer**          | [EvidenceDrawer.tsx](file:///Users/pranjal/Projects/financial-agent/dev/frontend/src/features/research/components/EvidenceDrawer.tsx) | Included/discarded evidence viewer |

### 7.5 Frontend ↔ Backend Communication

| Frontend Action          | Protocol    | Endpoint                         |
| ------------------------ | ----------- | -------------------------------- |
| Send chat message        | SSE stream  | `POST /chat`                     |
| Upload tradebook CSV     | REST        | `POST /portfolio/upload`         |
| View raw portfolio       | REST        | `GET /portfolio`                 |
| View valued portfolio    | REST        | `GET /portfolio/valued`          |
| Refresh live quotes      | REST        | `GET /portfolio/quotes`          |
| Trigger deep research    | REST        | `POST /research/trigger`         |
| Poll research status     | REST        | `GET /research/status/{run_id}`  |
| Search stocks            | REST        | `GET /api/search/stocks`         |
| View research artifact   | REST        | `GET /research/artifact/…`       |
| Get recommendations      | REST        | `GET /research/recommendations`  |
| Load morning briefing    | REST        | `GET /briefing/`                 |
| Resolve ticker           | REST        | `GET /tools/resolve-asset`       |
| Get stock quote          | REST        | `GET /tools/quote`               |

---

## 8. Data Flow Summary

### 8.1 Chat Flow

```
User types message
  → Frontend POST /chat (SSE)
  → main.py builds portfolio context from DB
  → graph.py create_react_agent invoked with portfolio-injected system prompt
  → LLM decides: respond directly or call tools
  → SequentialToolNode executes tools one at a time
  → Tool results fed back to LLM for next round
  → Final response streamed as SSE tokens to frontend
```

### 8.2 Portfolio Upload Flow

```
User uploads CSV
  → POST /portfolio/upload
  → portfolio_parser.py: header detection → broker-specific parsing → ticker normalization
  → portfolio_service.py: FIFO lot-matching (buy lots queued, sell lots dequeued)
  → Realized P&L calculated, net positions with weighted avg_cost determined
  → Atomic DB transaction: delete old holdings, insert new import + holdings
  → Response: saved holdings summary
```

### 8.3 Deep Research Flow

```
POST /research/trigger → async background task
  → planner: resolve watchlist → tickers + sectors (instruments cache + yfinance fallback)
  → collection: parallel evidence gathering
      - Tavily: macro news, sector news, ticker news
      - ChromaDB: prior research artifacts
      - yfinance: quotes + fundamentals
      - quant: CAGR, Sharpe, max drawdown
      - TA: RSI-14, SMA-50
      - Portfolio: return correlation matrix
  → macro_synthesis: LLM → MacroSynthesis (outlook + drivers + citations)
  → sector_synthesis: parallel LLM per sector → SectorSynthesis
  → ticker_synthesis: parallel LLM per ticker → TickerSynthesis
      (recommendation, confidence, target price, bear case, kill-the-company risk)
  → portfolio_synthesis: CIO LLM → PortfolioSynthesis (allocations, risk aggregates)
  → persist: dual-write to PostgreSQL + ChromaDB
```

### 8.4 Briefing Flow

```
GET /briefing/
  → Market status check (NSE hours)
  → Concurrent fetch: Nifty 50, India VIX, holdings breadth, net P&L
  → Latest research artifacts → action cards (high confidence or shifted recs)
  → Top 5 deduplicated news items from evidence packs
  → BriefingResponse assembled and returned
```

---

## 9. Testing

Tests live in [backend/tests/](file:///Users/pranjal/Projects/financial-agent/dev/backend/tests/) and run via `pytest` with `asyncio_mode = "auto"`.

| Test File                     | Coverage Area                        |
| ----------------------------- | ------------------------------------ |
| `test_chat_endpoint.py`       | SSE chat streaming, event parsing    |
| `test_agent_graph.py`         | LangGraph agent compilation, routing |
| `test_portfolio_endpoints.py` | Portfolio CRUD API endpoints          |
| `test_portfolio_parser.py`    | CSV parsing, ticker normalization    |
| `test_briefing.py`            | Briefing service                     |
| `test_deep_research.py`       | Research pipeline                    |

---

## 10. Key Dependencies

### Backend (Python 3.11+)

| Package                 | Purpose                             |
| ----------------------- | ----------------------------------- |
| `fastapi[standard]`     | Web framework + Uvicorn             |
| `langgraph`             | Agent graph orchestration           |
| `langchain` / `langchain-core` | Tool and model abstractions  |
| `langchain-groq`        | Groq Cloud LLM provider            |
| `langchain-ollama`      | Local Ollama LLM provider           |
| `langchain-chroma`      | ChromaDB vector store integration   |
| `sqlalchemy[asyncio]`   | Async ORM                           |
| `asyncpg`               | PostgreSQL async driver             |
| `alembic`               | Database migrations                 |
| `yfinance`              | Market data from Yahoo Finance      |
| `tavily-python`         | Web search API                      |
| `httpx`                 | Async HTTP client                   |
| `tenacity`              | Retry logic                         |
| `chromadb`              | Vector database                     |
| `pydantic` / `pydantic-settings` | Data validation + config    |

### Frontend (Node.js)

| Package               | Purpose                           |
| ---------------------- | --------------------------------- |
| `react` / `react-dom`  | UI framework                      |
| `vite`                 | Build tool + dev server           |
| `@xyflow/react`        | React Flow graph visualization    |
| `lucide-react`         | Icon library                      |
| `marked`               | Markdown → HTML rendering         |
| `clsx` / `tailwind-merge` | CSS class utilities            |
| `typescript`           | Type safety                       |
