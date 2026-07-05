# Financial AI Agent — 14-Day Solo-Dev Sprint Plan (Reactive Mode Only)

**Stack:** React · FastAPI · PostgreSQL · Chroma DB · LangGraph · yfinance
**Scope:** Reactive chat mode only. Proactive/background research mode is explicitly deferred.

---

## Guiding Principle: Walking Skeleton → Depth, Not Depth-First

The #1 failure mode for a solo dev on a project like this is building the agent, the DB, and the UI as three deep, separate tracks and only integrating them at the end. Integration bugs (streaming breaks, schema mismatches, tool-call formatting errors) are the most expensive bugs to find late and the cheapest to find early.

So the sequencing rule is:

1. **Day 1: Build a "walking skeleton"** — the thinnest possible end-to-end slice (UI → FastAPI → LangGraph → LLM → streamed response back). Nothing smart happens yet. This proves your streaming/transport layer works *before* you build anything on top of it.
2. **Data layer next** — the agent needs portfolio context to reason about, so Postgres + CSV ingestion comes before agent intelligence.
3. **Tools built and tested standalone** (via FastAPI's `/docs` Swagger UI or pytest) **before** they're wired into LangGraph. This isolates bugs: if something breaks after wiring, you know it's the *graph logic*, not the *tool logic*, because the tool was already proven correct alone.
4. **Agent orchestration** once real tools exist to orchestrate.
5. **Enrichment (news/RAG)** layered in after core orchestration is stable, since it's the most failure-prone piece (embedding quality, retrieval relevance).
6. **Output polish (artifacts/charts) last**, since it depends on everything upstream being reliable.

---

## Sprint Overview

| Sprint | Days | Focus |
|---|---|---|
| 0 | Day 1 | Walking Skeleton (full stack, hardcoded logic) |
| 1 | Days 2–3 | Data Foundation (Postgres schema + CSV ingestion) |
| 2 | Days 4–6 | Tool Belt I — Market/Historical Data + Ticker Resolution |
| 3 | Days 7–9 | Agent Orchestration (LangGraph state machine + streaming) |
| 4 | Days 10–11 | Tool Belt II — News Aggregation + Semantic Retrieval (Chroma) |
| 5 | Days 12–13 | Preferences, Quant Analysis & Rich Markdown/Artifact Output |
| — | Day 14 | Hardening, Buffer, Smoke Test |

---

## Sprint 0 (Day 1): Walking Skeleton

**Objective:** Prove the full transport pipeline works before building anything meaningful on top of it.

**Tasks:**
- Scaffold repo: `/frontend` (React), `/backend` (FastAPI), `docker-compose.yml` for Postgres + Chroma.
- FastAPI endpoint `POST /chat` that accepts a message and invokes a **single-node LangGraph graph** — no tools yet, just a raw LLM call.
- Stream the response back via **SSE** (Server-Sent Events) — simpler than WebSockets for one-directional agent→client streaming and sufficient for a chat UI.
- Bare-bones React chat UI: message list + input box, consuming the SSE stream token-by-token.
- Single dev-user stub (no real auth yet — hardcode a `user_id` in a cookie or local var). Real auth is explicitly deferred.

**Definition of Done:** You type a message in the browser, it hits FastAPI, invokes LangGraph, calls the LLM, and tokens stream back and render live in the chat UI. Nothing is smart. Everything is *connected*.

---

## Sprint 1 (Days 2–3): Data Foundation

**Objective:** Get portfolio data into Postgres so the agent has something real to reason about.

**Tasks:**
- Postgres schema (start minimal, migrate later with Alembic):
  - `users`, `portfolios`, `holdings` (ticker, quantity, avg_cost, asset_class), `transactions` (optional if you want history).
- `POST /portfolio/upload` — accepts CSV, parses with pandas, validates columns, normalizes ticker symbols (uppercase, strip exchange suffixes if needed), upserts into `holdings`.
- `GET /portfolio` — returns the current parsed portfolio as JSON.
- React: simple file upload component + a table view rendering the parsed portfolio (this doubles as your validation UI — if it renders correctly, ingestion worked).

**Definition of Done:** Upload a real CSV, see holdings persisted in Postgres, and confirm via `GET /portfolio` and the UI table that the data round-trips correctly. Malformed rows are rejected with a clear error, not a silent failure.

---

## Sprint 2 (Days 4–6): Tool Belt I — Market Data & Asset Resolution

**Objective:** Build and independently verify the tools that don't require the agent to exist yet.

**Provider:** yfinance (unofficial but free; provider is abstracted behind a `MarketDataProvider` Protocol so Kite Connect / Upstox can be swapped in by changing one file).

**Tasks:**
- yfinance provider wrapper with a DB caching layer (`market_snapshots` Postgres table). Quote TTL: 90 s. Historical bars for closed prior-day sessions are treated as immutable (TTL 365 d).
- New `instruments` table for alias overrides and lazy-populated instrument metadata.
- Three tools, each with a strict Pydantic input/output schema:
  - `resolve_asset(query)` → `AssetResolution` — maps free-text company names/aliases to one or more `Asset` candidates with exchange labels and confidence scores. Ambiguous inputs (e.g. `"tata motors"`) must return **both** NSE and BSE candidates, never silently collapse to one.
  - `get_quote(ticker)` → `MarketQuote` — price, day change, day change %, volume, 52-week high/low, staleness flag.
  - `get_historical_data(ticker, range, interval)` → `HistoricalDataResponse` — OHLCV series, provider-adjusted closes.
- Expose each as a plain FastAPI endpoint under `/tools/` and test via Swagger UI / pytest — **before** touching LangGraph.

**Endpoints:**
```
GET /tools/resolve-asset?query=reliance
GET /tools/quote?ticker=INFY.NS
GET /tools/historical-data?ticker=INFY.NS&range=6mo&interval=1d
```

**Explicitly out of scope for Sprint 2:** fundamentals (P/E, EPS, revenue), news, earnings, dividends, corporate actions, analyst estimates.

**Tool architecture note (Raw vs. Semantic layers):** Sprint 2 builds Layer 1 — pure deterministic fetch tools. Layer 2 tools (`compare_assets`, `assess_valuation`) are deterministic *compositions* over Layer 1 outputs with zero LLM math; they land in Sprint 4/5. This layering is now the stated organizing principle for all future tool development.

**Definition of Done:** All three tools, called directly (not through the agent), return correct structured JSON for 10+ inputs including deliberately ambiguous ones (`"tata motors"` → both NSE/BSE candidates, not silently one). Cache hit is verified by confirming `fetched_at` does not change on a repeat call within the TTL window.

---

## Sprint 3 (Days 7–9): Agent Orchestration — LangGraph State Machine

**Objective:** Wire the proven tools into a real multi-step reasoning graph, and get streaming working end-to-end with real tool calls.

**Tasks:**
- Define LangGraph state schema: conversation history, portfolio context, intermediate tool results, final answer.
- Build the graph: `intent_router` node → conditional tool-calling node(s) → `synthesis` node that composes the final answer.
- Bind the Sprint 2 tools to the graph using LangGraph's tool-calling support (pydantic schemas you already wrote pay off here directly).
- Extend the SSE streaming from Sprint 0 to handle **intermediate states** too — e.g., emit a "calling market data tool…" event so the UI can show a loading/thinking indicator, not just silence until the final answer.
- Inject portfolio context (from Sprint 1's `GET /portfolio`) into the graph state at the start of each conversation turn.

**Definition of Done:** Ask "What's the current price of my largest holding?" and the agent correctly identifies the holding from your portfolio, resolves the ticker, calls the market data tool, and returns a grounded answer with the data timestamp cited. Do this for at least 3 distinct query types (price lookup, historical trend, "what do I own").

---

## Sprint 4 (Days 10–11): Tool Belt II — News & Semantic Retrieval (Chroma)

**Objective:** Add the RAG-based tools, the most failure-prone layer, in isolation before trusting the agent to use them well.

**Tasks:**
- News aggregation tool: fetch from Wirefinance's news endpoint, chunk articles sensibly (by paragraph, not fixed token windows — financial news loses meaning when sliced arbitrarily), embed, and store in a Chroma collection keyed by ticker/date.
- `semantic_news_search(query, ticker=None)` tool: retrieve top-k relevant chunks, re-rank by recency (news relevance decays fast — a purely semantic match from 6 months ago is often worse than a recent, loosely related one).
- Wire as a new conditional node in the LangGraph graph — the router should only invoke this when the query is news/sentiment-related, not for every turn.

**Definition of Done:** Ask "Any recent news on [a holding]?" and get a summarized, source-linked answer built from actually-relevant retrieved chunks — spot-check retrieval quality manually for at least 5 queries before trusting it.

---

## Sprint 5 (Days 12–13): Preferences, Quant Analysis & Rich Output

**Objective:** Close the loop on personalization and make responses visually useful, not just textually correct.

**Tasks:**
- `user_preferences` table (risk tolerance, sector preferences/exclusions, any stated trading principles) + a simple settings form in the UI to populate it.
- `match_preferences` tool: filters/flags analysis or recommendations against stored preferences.
- Server-side quant analysis functions (not agent-generated math — compute deterministically, then let the LLM narrate): allocation by sector/asset class, concentration risk, simple volatility metrics.
- Frontend: markdown renderer with embedded chart components (e.g., Recharts) for portfolio breakdowns — this is your "artifact" rendering layer.

**Definition of Done:** Ask "How diversified is my portfolio?" and get a rendered allocation chart plus a narrative that references your stated risk preference (e.g., flags if you're overweight in a sector you said you wanted to avoid).

---

## Day 14: Hardening & Buffer

**Objective:** Stabilize, not expand.

**Tasks:**
- Error handling pass: what happens when Wirefinance API times out mid-tool-call? When a CSV has a ticker that can't be resolved? When Chroma returns zero results?
- Loading/error states in the UI for each of the above.
- End-to-end smoke test of all 5 query types built across the sprints.
- Write down (don't fix) known gaps as a backlog for the optimization pass.

**Definition of Done:** You can run through all core reactive workflows back-to-back without a crash, and you have a written list of what's rough vs. what's solid.

---

## Explicitly Out of Scope for These 14 Days

Keep these off your plate — they're real, but not MVP-blocking:

- Proactive/background research mode
- Real multi-user auth (dev-user stub is fine)
- Advanced retrieval (re-ranking models, hybrid search) beyond basic recency weighting
- CI/CD, deployment, containerized production config
- Comprehensive automated test suite (targeted pytest on tools is enough for now)
- Mobile-responsive UI polish

---

## Why This Order Avoids Bottlenecks

- **DB before agent:** the agent is only as useful as the context it has. Building orchestration against a portfolio that doesn't exist yet means rebuilding prompts/state later.
- **Tools tested standalone before wiring:** when something breaks post-integration, you'll know immediately whether it's tool logic or graph logic — you're never debugging both at once.
- **Streaming proven on Day 1, not Day 9:** SSE/streaming quirks (buffering, premature connection close, token-level vs. message-level streaming) are transport-layer problems, not agent-logic problems. Finding them on Day 1 against a dummy LLM call is trivial; finding them on Day 9 against a complex graph is not.
- **RAG (Chroma/news) after core orchestration is stable:** retrieval quality is the hardest thing to get right and the easiest to spend unbounded time tuning. Isolating it to its own sprint, after the rest of the agent works, stops it from blocking everything else.