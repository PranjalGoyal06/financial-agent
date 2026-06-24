# SCALE MVP — Investment Intelligence Agent

## Updated MVP Architecture Plan

### Confidence Boundary

This plan includes only architectural and product decisions that are high-confidence for the MVP. It deliberately avoids overbuilding, fake governance, premature broker integration, or agent complexity that exists only to look impressive. The goal is a professional, demo-ready investment intelligence system whose architecture, API design, and UI/UX are credible even if the implementation remains MVP-sized.

---

## 1. Product Description

SCALE is a portfolio-aware investment intelligence system for individual investors. It helps the user understand their portfolio, analyse holdings and watchlist companies, inspect risk, reason about market/news context, and receive structured investment recommendations.

The system has two interaction modes:

1. **Reactive Chat Mode**
   The user asks direct questions through a chat interface. The agent responds with portfolio-aware, evidence-backed, risk-first analysis using current market data, stored portfolio context, user profile, investment principles, news, notes, and previous research outputs.

2. **Research Run Mode**
   The user explicitly triggers a longer-running research job, such as “analyse my full watchlist and suggest portfolio reallocations”. This runs as a persisted background research run using a local open-source LLM through Ollama. The output is saved as a structured recommendation record and as a reusable Markdown research artefact.

The system does **not** execute trades. It reasons, advises, explains, records, and surfaces risk. All final decisions remain with the user.

---

## 2. MVP Positioning

The MVP is not a trading bot and not a generic finance chatbot.

It is a **portfolio command centre with an AI reasoning layer**.

The first screen should immediately communicate three things:

1. What the user owns.
2. What the system currently thinks is worth attention.
3. How the user can ask follow-up questions.

The MVP should feel like:

> Portfolio dashboard + intelligence feed + chat interface

not:

> Empty chatbot with hidden portfolio tools

For the MVP, the “proactive” layer is user-triggered only. Scheduled autonomous monitoring is intentionally out of scope. In the UI, this should be called **Research Run**, **Deep Portfolio Review**, or **Watchlist Analysis**, not “proactive agent”, because the MVP does not yet monitor markets autonomously.

---

## 3. Core Principles Reflected in the Architecture

The architecture is governed by the following practical rules:

1. **The LLM reasons; it does not calculate.**
   Numerical calculations, market data lookup, portfolio valuation, allocation, and P&L are deterministic backend operations.

2. **The agent advises; it does not act.**
   No trade execution API exists in the MVP. Human sovereignty is enforced by the absence of an execution path.

3. **Every recommendation must include uncertainty.**
   Confidence tier, assumptions, data quality, and insufficient-data mode are required output fields.

4. **Downside analysis comes before upside analysis.**
   Every recommendation must include bear case, expected drawdown or downside framing, and key risk factors before presenting upside.

5. **Every factual claim must be traceable.**
   The backend builds an evidence pack. The LLM can only cite evidence IDs from that pack. Citations are logged with evidence IDs post-hoc.

6. **Data quality gates reasoning.**
   Stale, missing, or unresolved data is surfaced explicitly. Critical data failure routes to an insufficient-data response instead of invoking the LLM on bad inputs.

7. **User principles are context, not commandments.**
   The system uses the user’s investment principles, but it is allowed to flag conflicts, contradictions, or unsafe assumptions. It must not optimise for satisfying user preferences at all costs.

8. **No action is valid, but not privileged.**
   “No action” is always evaluated. It is recommended only when justified on risk-adjusted grounds, not because the system is biased toward inactivity.

9. **Compliance is not faked.**
   The MVP does not have a full compliance engine. The system must log compliance as `not_implemented_mvp`, not as `passed`.

---

## 4. Tech Stack

### Backend

* **FastAPI** for HTTP APIs, request validation, routing, and serving the agent workflows.
* **LangGraph** for stateful multi-step agent execution.
* **Pydantic** for typed request/response schemas and LLM output validation.
* **SQLAlchemy or SQLModel** for PostgreSQL persistence.
* **Alembic** for database migrations.

LangChain integrations may be used where helpful, especially for model clients, embeddings, vector store wrappers, and document processing. However, the core workflow orchestration should be LangGraph, not plain LangChain chains.

### Frontend

* **React** for the single-page application.
* **Tailwind CSS** for styling.
* Optional but recommended: **TanStack Query** for API fetching/cache state.
* Optional but recommended: **Zustand** or simple React context for lightweight shared UI state.

React is justified because the UI has multiple concurrent stateful zones: portfolio dashboard, intelligence/briefing panel, and chat. These panels should share state; for example, clicking a risk card should pre-populate a chat question.

### Storage

The MVP uses three distinct storage systems:

1. **PostgreSQL** — structured source of truth.
2. **ChromaDB** — semantic retrieval index for unstructured text.
3. In-memory Python dict with timestamp-based TTL (15 min default). No external cache server. (No Redis for MVP)

ChromaDB is not the source of truth. It is a rebuildable retrieval index. Raw documents and artefact metadata should remain in PostgreSQL or the local artefact store.

### Market and News Data

* **yfinance** for MVP market data and ticker validation.
* **yfinance news** for ticker-level news retrieval where available.
* NSE/BSE tickers should use Yahoo Finance suffixes such as `.NS` and `.BO` after validation.

All yfinance access must go through backend provider wrappers. The LLM must never call yfinance directly.

### LLM Clients

The MVP uses two LLM paths:

1. **Reactive Chat LLM**

   * Provider: Groq API
   * Purpose: low-latency interactive responses
   * Suggested model: `llama-3.3-70b` if available under the configured Groq account
   * Fallback: configure model ID through environment variables

2. **Research Run LLM**

   * Provider: Ollama, local
   * Purpose: long-running background research
   * Preferred model: `qwen2.5:14b` if local hardware can run it acceptably
   * Fallback model: `llama3.1:8b` for weaker machines

The model choice must be configurable. Do not hardcode one model into the application logic.

---

## 5. High-Level Architecture

The system should be organised into four planes.

```text
1. Interface Plane
   React dashboard, briefing panel, chat UI, evidence drawers, research run status UI

2. API Plane
   FastAPI routes, request validation, response schemas, authentication stub if needed

3. Intelligence Plane
   LangGraph reactive graph, LangGraph research graph, evidence builder, validators, output parsers

4. Data Plane
   PostgreSQL, ChromaDB, Redis, yfinance adapters, artefact storage, audit log
```

The key design idea:

> Agents are not the whole system. Agents operate inside a governed evidence, data, audit, and UI system.

---

## 6. Data Storage Responsibilities

### PostgreSQL

PostgreSQL is the structured source of truth.

It stores:

* user profile
* risk tolerance
* investment horizon
* investment principles
* portfolio imports
* validated holdings
* watchlist items
* raw document metadata
* artefact metadata
* chat sessions
* chat messages
* research runs
* research run steps
* recommendation records
* recommendation claims
* evidence links
* audit events

Even though the MVP is single-user, tables should still include `user_id` with a default demo user. This avoids painful refactoring later.

### ChromaDB

ChromaDB stores embeddings and retrieval metadata for:

* news chunks
* Markdown notes
* research reports
* prior analyses
* user-authored theses
* agent-authored artefacts

Each embedded chunk should include metadata such as:

```json
{
  "document_id": "...",
  "ticker": "INFY.NS",
  "source": "yfinance_news",
  "document_type": "news | note | research_report | prior_analysis",
  "created_at": "...",
  "fetched_at": "...",
  "published_at": "..."
}
```

ChromaDB should be rebuildable from stored raw documents and artefacts.

### Redis

Redis stores short-lived market/provider data with TTL.

Examples:

```text
quote:INFY.NS
fundamentals:TCS.NS
news_fetch_status:RELIANCE.NS
```

Each cached value should include:

```json
{
  "value": {...},
  "fetched_at": "...",
  "provider": "yfinance",
  "ttl_seconds": 900
}
```

Default quote TTL: **15 minutes**.

The system must never silently use stale Redis data. If stale data is used as fallback, the response must surface that fact.

---

## 7. Portfolio Ingestion

### CSV Schema

The MVP portfolio CSV schema is:

```csv
ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date
```

### Field Definitions

| Field           | Required | Description                                                                      |
| --------------- | -------: | -------------------------------------------------------------------------------- |
| `ticker`        |      Yes | User-provided ticker symbol before canonicalisation.                             |
| `exchange`      |      Yes | Exchange or market identifier. Required to avoid ambiguity.                      |
| `asset_class`   |      Yes | Enum: `equity`, `etf`, `mf`, `bond`, `gold`, `other`.                            |
| `quantity`      |      Yes | Number of units held. Must be positive.                                          |
| `avg_buy_price` |      Yes | Weighted average buy price per unit.                                             |
| `currency`      |      Yes | Currency of cost basis, e.g. `INR`, `USD`.                                       |
| `purchase_date` |      Yes | Purchase date or average acquisition date. Stored even if not fully used in MVP. |

### Why These Fields Exist

* `exchange` is mandatory because symbols are ambiguous across markets.
* `avg_buy_price` is used instead of full tax-lot tracking because FIFO/tax-lot modelling is out of scope for MVP.
* `purchase_date` is retained because future tax-aware and thesis-age analysis need it.
* `currency` is explicit because the product should not hardcode INR, even if Indian equities are the initial focus.
* `asset_class` gates downstream analysis logic.

### Fields Not Accepted in CSV

The CSV should not include:

* current price
* current value
* P&L
* allocation percentage
* day change

These are derived at runtime using current market data. Storing them in the CSV creates staleness problems.

### Import Validation Flow

```text
upload CSV
→ parse rows
→ validate schema
→ validate enum fields
→ canonicalise ticker using exchange
→ resolve ticker through yfinance wrapper
→ reject malformed/unresolved rows
→ store validated import and holdings in PostgreSQL
→ write audit event
```

Invalid rows must never enter the holdings table. The LLM must never see unvalidated portfolio data.

### Canonical Ticker Handling

The system should store both:

```text
raw_ticker       = ticker provided by user
canonical_ticker = resolved provider ticker, e.g. RELIANCE.NS
exchange         = declared exchange
```

The canonical ticker is used for market data calls.

---

## 8. Market and News Ingestion

### Market Data

Market data is fetched through a backend yfinance adapter.

Responsibilities of the adapter:

* canonical ticker validation
* quote retrieval
* fundamentals retrieval where available
* provider error handling
* timeout handling
* Redis cache read/write
* freshness metadata
* audit logging

The reactive graph should request market data from an internal service, not directly from yfinance.

### News Data

News is fetched per ticker through yfinance where available.

News ingestion flow:

```text
manual refresh or startup refresh
→ fetch ticker news
→ normalise metadata
→ store raw document metadata/content reference
→ chunk text
→ embed chunks
→ store embeddings in ChromaDB
→ write audit event
```

The reactive agent retrieves news from ChromaDB rather than fetching fresh news during every chat turn. This keeps chat fast and retrieval auditable.

The UI should provide a manual “Refresh News / Market Data” control.

---

## 9. Evidence Pack Design

The backend, not the LLM, owns evidence construction.

Before the main LLM call, the system builds an evidence pack:

```json
{
  "evidence_pack_id": "ep_123",
  "items": [
    {
      "evidence_id": "news_001",
      "type": "news",
      "ticker": "INFY.NS",
      "source": "yfinance_news",
      "title": "...",
      "published_at": "...",
      "retrieved_at": "...",
      "excerpt": "..."
    },
    {
      "evidence_id": "quote_001",
      "type": "market_quote",
      "ticker": "INFY.NS",
      "provider": "yfinance",
      "fetched_at": "...",
      "fields": {
        "price": 0,
        "currency": "INR"
      }
    }
  ]
}
```

The LLM may cite only `evidence_id` values from the provided pack.

The output validator must reject:

* missing citations for factual claims
* citations to non-existent evidence IDs
* numerical claims not backed by deterministic backend data
* unsupported probabilistic claims

This is the core anti-hallucination mechanism.

For MVP: the evidence pack builder is not a hard gate, but "best-effort linking".

---

## 10. Reactive Agent Graph

The reactive agent is a LangGraph graph invoked for each user chat message.

### State

The graph state should include:

```python
class ReactiveState(TypedDict):
    session_id: str
    user_query: str
    user_profile: dict
    portfolio: dict
    watchlist: list[str]
    principles: list[dict]
    relevant_tickers: list[str]
    market_data: dict
    retrieved_chunks: list[dict]
    evidence_pack: dict
    data_quality: dict
    compressed_context: str
    principle_conflicts: list[dict]
    llm_raw_output: str
    parsed_output: dict
    validation_errors: list[str]
    final_response: dict
    audit_events: list[dict]
```

### Nodes

```text
1. initialise_run
2. load_authoritative_context
3. identify_relevant_tickers
4. fetch_market_data
5. semantic_retrieve
6. build_evidence_pack
7. validate_data_quality
8. compress_context
9. principle_conflict_check
10. llm_reason
11. parse_and_validate_output
12. compliance_boundary_check
13. format_response
14. persist_outputs
```

### Node Responsibilities

#### 1. `initialise_run`

Creates a run ID, attaches the chat session, and starts audit logging.

#### 2. `load_authoritative_context`

Loads from PostgreSQL:

* holdings
* watchlist
* user profile
* risk tolerance
* investment horizon
* investment principles
* previous recommendation summaries where relevant

#### 3. `identify_relevant_tickers`

Identifies tickers relevant to the query.

For MVP, this can be a deterministic keyword/symbol match against holdings and watchlist, with a lightweight LLM fallback only if needed.

#### 4. `fetch_market_data`

Fetches quote/fundamental data through the internal market data service.

Rules:

* Redis cache is checked first.
* Fresh values may be used directly.
* Stale values are flagged.
* Missing critical data can trigger insufficient-data routing.

#### 5. `semantic_retrieve`

Queries ChromaDB for relevant news, notes, research reports, and prior analyses.

Retrieval should be filtered by ticker where possible.

#### 6. `build_evidence_pack`

Converts retrieved market data and unstructured chunks into a strict evidence pack with stable evidence IDs.

#### 7. `validate_data_quality`

Checks:

* quote freshness
* missing tickers
* stale market data
* insufficient news coverage
* unresolved symbols
* provider failure
* weak evidence count

If the verdict is `critical_failure`, the graph skips LLM reasoning and routes to `format_response` with an insufficient-data output.

#### 8. `compress_context`

Compresses retrieved context before the main LLM call.

Acceptable MVP approaches:

* extractive summarisation
* smaller LLM summarisation
* deterministic top-k truncation with clear logging

The compression decision must be auditable. The system should log what was retrieved and what was actually passed to the LLM.

#### 9. `principle_conflict_check`

Checks whether the user query or likely recommendation conflicts with:

* user risk tolerance
* investment horizon
* stated investment principles
* concentration limits
* prior recommendation history

The purpose is not to blindly satisfy the user. The system should explicitly surface conflicts.

Example:

```text
Your stated principle says you prefer concentrated positions, but your current portfolio already has 42% exposure to one stock. This increases single-stock risk.
```

#### 10. `llm_reason`

Calls Groq for the main reasoning step.

The prompt should require:

* downside before upside
* no unsupported claims
* clear distinction between data-supported conclusions, inferences, and assumptions
* no direct calculation by the LLM
* no recommendation without confidence tier
* citation only from provided evidence IDs
* explicit no-action comparison

#### 11. `parse_and_validate_output`

Parses LLM output into a Pydantic schema.

If required fields are missing, invalid, or unsupported, the graph returns an insufficient-data or validation-failed response. It should not silently repair financial recommendations.

#### 12. `compliance_boundary_check`

For MVP:

```text
compliance_status = "not_implemented_mvp"
execution_allowed = false
```

This node exists to preserve the future governance boundary, but it must not log “passed”.

#### 13. `format_response`

Formats the final user-visible structured answer.

The response order should be:

```text
1. Recommendation / conclusion
2. Confidence tier
3. Data quality status
4. Bear case / downside
5. Portfolio impact
6. Upside case
7. Assumptions
8. Principle conflicts, if any
9. Evidence / sources
10. Suggested next questions or actions
```

#### 14. `persist_outputs`

Stores:

* chat message
* graph run metadata
* final response
* evidence links
* audit events
* recommendation record if applicable

---

## 11. Reactive Output Schema

The LLM output should be parsed into a schema similar to:

```python
class Claim(BaseModel):
    text: str
    claim_type: Literal["data_supported", "inference", "assumption"]
    evidence_ids: list[str]

class RecommendationOutput(BaseModel):
    action: Literal[
        "buy", "hold", "sell", "reduce", "add", "watch", "no_action", "insufficient_data"
    ]
    confidence_tier: Literal["low", "medium", "high"]
    data_quality: Literal["good", "limited", "stale", "critical_failure"]
    summary: str
    bear_case: str
    expected_drawdown: str | None
    key_risks: list[str]
    portfolio_impact: str
    upside_case: str | None
    no_action_case: str
    assumptions: list[str]
    principle_conflicts: list[str]
    claims: list[Claim]
    next_steps: list[str]
```

The backend should validate that all `evidence_ids` exist in the evidence pack.

---

## 12. Research Run Mode

The research mode is user-triggered and should be modelled as a persisted job, not a loose background coroutine.

### Why Persisted Runs Matter

Research runs can be long, fail halfway, or be interrupted. A professional MVP should track them explicitly.

A research run has:

```text
run_id
status
scope
started_at
completed_at
current_step
progress
error_message
final_result_id
```

### Status Values

```text
queued
running
waiting_for_user
completed
failed
cancelled
```

### Execution Model

For MVP:

```text
POST /api/v1/research-runs
→ create row in research_runs table
→ local worker picks queued run
→ LangGraph executes research graph
→ checkpoints/progress persisted
→ result stored as recommendation + Markdown artefact
→ UI polls or subscribes to run events
```

The first implementation may use a simple local worker process or in-process worker loop. The API should still treat research as a durable run so that it can later be moved to Celery/RQ/ARQ without changing the frontend contract.

### Research Graph

```text
1. initialise_research_run
2. load_scope
3. load_portfolio_context
4. for_each_ticker
   4.1 fetch_market_data
   4.2 fetch_fundamentals
   4.3 retrieve_news_and_notes
   4.4 build_ticker_evidence_pack
   4.5 analyse_ticker_with_ollama
   4.6 validate_ticker_output
   4.7 persist_ticker_finding
5. synthesize_portfolio_view
6. validate_research_output
7. persist_recommendation
8. create_markdown_artifact
9. embed_artifact_in_chromadb
10. mark_run_completed
```

### Per-Ticker Output

Each ticker analysis should produce:

```text
ticker
thesis_summary
bear_case
key_risks
valuation_notes
confidence_tier
data_quality
principle_conflicts
suggested_action
supporting_evidence_ids
```

### Portfolio-Level Synthesis

The final synthesis should include:

* concentration risk
* sector exposure
* correlation approximation if feasible
* overexposed holdings
* under-supported holdings
* watchlist opportunities
* ranked reallocation suggestions
* no-action case
* assumptions
* confidence tier
* data quality caveats

No recommendation should be presented without a no-action comparison.

---

## 13. Human Approval and Action Boundary

The MVP does not execute trades, so the most important human approval gate is architectural: there is no execution path.

The user may optionally mark a recommendation as:

```text
accepted
rejected
saved_for_later
needs_more_research
```

This is not trade execution. It is user decision tracking.

The system should never present a recommendation as an instruction. It should present it as an analysis-backed suggestion.

Example wording:

```text
Suggested action: Reduce exposure
This is an advisory recommendation only. No trade will be executed by SCALE.
```

Future broker integration, if ever added, must be a separate execution service behind explicit human approval.

---

## 14. API Design

Use resource-oriented endpoints under `/api/v1`.

### Portfolio

```http
POST   /api/v1/portfolio/imports
GET    /api/v1/portfolio
GET    /api/v1/portfolio/summary
GET    /api/v1/portfolio/holdings
GET    /api/v1/portfolio/imports/{import_id}
DELETE /api/v1/portfolio/holdings/{holding_id}
```

### Watchlist

```http
GET    /api/v1/watchlist
POST   /api/v1/watchlist/items
DELETE /api/v1/watchlist/items/{ticker}
```

### Market Data

```http
GET    /api/v1/market/quotes?tickers=INFY.NS,TCS.NS
POST   /api/v1/market/refresh
GET    /api/v1/market/freshness
```

### News

```http
POST   /api/v1/news/refresh
GET    /api/v1/news?tickers=INFY.NS,TCS.NS
```

### Artefacts

```http
GET    /api/v1/artifacts
POST   /api/v1/artifacts
GET    /api/v1/artifacts/{artifact_id}
DELETE /api/v1/artifacts/{artifact_id}
```

### Chat

```http
POST   /api/v1/chat/sessions
GET    /api/v1/chat/sessions
GET    /api/v1/chat/sessions/{session_id}
POST   /api/v1/chat/sessions/{session_id}/messages
GET    /api/v1/chat/sessions/{session_id}/messages
GET    /api/v1/chat/sessions/{session_id}/events
```

### Research Runs

```http
POST   /api/v1/research-runs
GET    /api/v1/research-runs
GET    /api/v1/research-runs/{run_id}
GET    /api/v1/research-runs/{run_id}/events
GET    /api/v1/research-runs/{run_id}/result
POST   /api/v1/research-runs/{run_id}/cancel
```

### Recommendations

```http
GET    /api/v1/recommendations
GET    /api/v1/recommendations/{recommendation_id}
GET    /api/v1/recommendations/{recommendation_id}/evidence
POST   /api/v1/recommendations/{recommendation_id}/decision
```

### Audit

```http
GET    /api/v1/audit/events?run_id=...
GET    /api/v1/audit/runs/{run_id}
```

---

## 15. Frontend UX

The frontend is a single-page React app with three major zones.

```text
Top Bar
- Total portfolio value
- Day change
- Data freshness indicator
- Last research run status
- Manual refresh button

Left Panel: Portfolio Dashboard
- Holdings table
- Allocation percentage
- P&L
- Sector/asset-class exposure
- Concentration risk indicator

Centre Panel: Intelligence / Briefing
- Latest research run summary
- Risk cards
- Watchlist findings
- Collapsible per-ticker cards
- Trigger new research run

Right Panel: Chat
- Message thread
- Suggested prompts
- Query box
- Source/evidence drawer
```

### Important UX Behaviours

* Clicking a holding should open its detail context and offer chat prompts.
* Clicking a risk card should pre-fill a chat question.
* Clicking a source should open the evidence drawer.
* Research run progress should be visible step-by-step.
* Data freshness should be visible before the user asks anything.

### Recommended Chat Response Card

```text
Recommendation: Hold / Reduce / Add / No Action / Insufficient Data
Confidence: Medium
Data Quality: Good, limited, stale, or critical failure

Downside First
- Bear case
- Expected drawdown / risk framing
- Key risks

Portfolio Impact
- Allocation effect
- Concentration effect
- Risk tolerance fit

Upside Case
- Why the idea may still be attractive

No-Action Case
- What happens if the user does nothing

Assumptions
- Explicit assumptions

Evidence
- Collapsed source list with evidence IDs
```

The UI should visually separate:

* facts
* inferences
* assumptions
* recommendations

---

## 16. Core Database Tables

Recommended MVP tables:

```text
users
user_profiles
investment_principles

portfolio_imports
holdings
watchlist_items

market_snapshots
news_documents
artifacts

chat_sessions
chat_messages

research_runs
research_run_steps
research_findings

recommendations

audit_events
```

### Audit Event Shape

```text
audit_event_id
run_id
session_id
actor
event_type
event_timestamp
input_hash
output_hash
source_refs
metadata_json
```

The audit log should be append-only at the application level.

---

## 17. Suggested Repository Organisation

Only a suggestion, not a hard requirement.

```text
financial-agent/
  backend/
    app/
      main.py
      config.py
      api/
        v1/
          portfolio.py
          watchlist.py
          market.py
          news.py
          chat.py
          research_runs.py
          recommendations.py
          audit.py
      agents/
        reactive/
          graph.py
          state.py
          nodes.py
          prompts.py
          schemas.py
        research/
          graph.py
          state.py
          nodes.py
          prompts.py
          schemas.py
      services/
        portfolio_service.py
        market_data_service.py
        news_service.py
        evidence_service.py
        artifact_service.py
        audit_service.py
        recommendation_service.py
      integrations/
        yfinance_client.py
        groq_client.py
        ollama_client.py
        chroma_client.py
        cache.py
      db/
        models.py
        session.py
        repositories/
      workers/
        research_worker.py
      schemas/
        api.py
        domain.py
    alembic/
    tests/
  frontend/
    src/
      app/
      components/
      features/
        portfolio/
        chat/
        research/
        recommendations/
        artifacts/
      lib/
        api.ts
        types.ts
      styles/
  docs/
    problem-statement.md
    csv_schema.md
    principles.md
    [any other doc you think needs to be created]
  docker-compose.yml
  README.md
```

---

## 18. MVP Build Order

### Phase 1 — Foundations

1. FastAPI project setup
2. PostgreSQL schema + migrations
3. Redis setup
4. ChromaDB setup
5. yfinance wrapper
6. portfolio CSV import and validation
7. portfolio dashboard API

### Phase 2 — Reactive Agent

1. chat session/message APIs
2. LangGraph reactive state
3. market data node
4. retrieval node
5. evidence pack builder
6. data quality validator
7. Groq reasoning node
8. Pydantic output validator
9. structured response UI

### Phase 3 — Research Runs

1. research_runs table
2. local worker
3. research graph skeleton
4. sequential ticker loop
5. Ollama integration
6. portfolio synthesis
7. persist research result
8. embed report into ChromaDB
9. research status UI

### Phase 4 — Polish and Demo Readiness

1. evidence drawer
2. audit event viewer
3. data freshness indicators
4. better error states
5. sample CSV
6. demo portfolio
7. README and architecture docs

---

## 19. Explicit MVP Non-Goals

Out of scope:

* trade execution
* broker API integration
* multi-user production authentication
* autonomous scheduled monitoring
* tax-lot/FIFO accounting
* complete compliance rule engine
* real-time streaming market feed
* complex portfolio optimisation engine
* parallel multi-agent research swarm
* paid market data integrations

These are intentionally excluded to keep the MVP grounded.

---

## 20. Final Product Standard for the MVP

The MVP is successful if it can demonstrate the following:

1. A user imports a portfolio CSV.
2. The system validates and canonicalises holdings.
3. The dashboard shows live-derived portfolio metrics.
4. The user asks a portfolio-specific question in chat.
5. The reactive LangGraph pipeline retrieves context, checks data quality, builds evidence, reasons through Groq, validates output, and returns a structured risk-first answer.
6. The user triggers a research run.
7. The research run processes tickers sequentially through Ollama, persists progress, and produces a portfolio-level report.
8. The report becomes a reusable artefact for future chat retrieval.
9. Every recommendation includes confidence, downside, assumptions, evidence, and data quality.
10. No trade is executed. No fake compliance pass is logged.

The central product promise is:

> SCALE gives the investor a portfolio-aware, evidence-backed, risk-first AI research assistant whose recommendations are structured, traceable, and bounded by human decision-making.
