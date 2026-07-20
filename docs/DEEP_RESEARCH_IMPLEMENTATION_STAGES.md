<!-- DEEP_RESEARCH_IMPLEMENTATION_STAGES.md — companion to DEEP_RESEARCH.md -->
<!-- Fully rewritten to align with actual codebase structure in backend/app/ -->

# Deep Research — Implementation Stages

Companion to `DEEP_RESEARCH.md`. That document specifies *what* to build; this one specifies *the order to build it in*, so each piece can be tested in isolation before it's wired into the graph.

**Convention:** All new modules live under `backend/app/<domain>/`. Imports are `from app.<domain>.<module> import ...`. All lib functions are synchronous pure functions called via `asyncio.to_thread()` when needed from async contexts (same pattern as the existing `market_data/provider.py`).

**Test discipline:** Don't skip a stage's test checkpoint to save time — a bug caught at Stage 1 costs minutes; the same bug surfacing at Stage 11 costs hours of graph debugging.

---

## Stage 0 — Environment sanity check

**Build**: Confirm all prerequisites are live.

**What to verify:**
1. Tavily API key is set in `.env` (`TAVILY_API_KEY`) and `from tavily import TavilyClient` works.
2. Ollama is running locally — `ollama list` shows your target model pulled.
3. ChromaDB Docker container is running on port 8001 — `curl http://localhost:8001/api/v1/heartbeat` returns 200.
4. PostgreSQL Docker container is running — `psql` connects successfully.
5. Existing tools import and run: `from app.market_data.tools import get_quote_tool, get_historical_data_tool, resolve_asset_tool` — call `get_quote_tool` on one NSE ticker (e.g. `RELIANCE.NS`).

**Test checkpoint**: All five checks pass. If any fail here, fix before writing a single line of pipeline code — everything downstream assumes all five are live.

---

## Stage 1 — Foundations: schemas, config, DB, dependency

**Build:**
- `pyproject.toml` → add `"tavily-python>=0.5,<1.0"`
- `backend/app/config.py` → add `tavily_api_key`, `chroma_host`, `chroma_port` fields
- `backend/app/evidence/schemas.py` → `EvidenceItem`, `EvidencePack` Pydantic models (exact schema in `DEEP_RESEARCH.md`)
- `backend/app/models.py` → add `WatchlistItem` and `ResearchArtifact` ORM models (exact schemas in `implementation_plan.md`)

**Do NOT build yet**: Any client code, lib functions, or graph code.

**Test checkpoint:**
- `uv sync` passes with new dependency.
- `from app.evidence.schemas import EvidenceItem, EvidencePack` — instantiate both with dummy data, serialize to JSON and back, confirm round-trip.
- Run `Base.metadata.create_all(engine)` (or `init_db()`) — confirm `watchlist_items` and `research_artifacts` tables appear in the database via `psql \dt`.
- `from app.config import settings; settings.tavily_api_key` returns the key value.

This is the shape everything later writes into — get it locked before anything depends on it.

---

## Stage 2 — Tavily search integration

**Build:**
- `backend/app/search/schemas.py` → `SearchResult`, `SearchResponse`
- `backend/app/search/client.py` → `search(query: str, max_results: int = 5) -> list[EvidenceItem]`

The `search()` function:
1. Computes `params_hash = make_params_hash(query, "search_snapshot", max_results=str(max_results))` using the existing function from `market_data/cache.py`
2. Calls `get_cached(session, "search_snapshot", params_hash)` — return cached items if fresh
3. On cache miss: calls Tavily, maps `{title, url, content, published_date, score}` → `EvidenceItem`
4. Computes `freshness` from `published_date` vs today
5. Calls `put_cache()` with `fresh_until = now + timedelta(minutes=20)`
6. Returns `list[EvidenceItem]`

**Do NOT build yet**: `search/tools.py` (@tool wrapper for reactive agent) — that's Stage 12.

**Test checkpoint (standalone, no graph):**
```python
import asyncio
from app.search.client import search

items = asyncio.run(search("India equity market outlook this week"))
print(items)  # should have 5 EvidenceItem objects with clean summaries

items2 = asyncio.run(search("RELIANCE.NS stock news analysis"))
print(items2)

# Second call with same query — should be cache hit (no Tavily request)
items3 = asyncio.run(search("India equity market outlook this week"))
assert items3 == items  # or at least same length — cache hit
```

Verify: `freshness` is computed correctly, `published_at` is populated when Tavily returns a date, `summary` is clean prompt-ready text (not raw HTML). Confirm `market_snapshots` row exists with `snapshot_type="search_snapshot"`.

---

## Stage 3 — Quant + TA + Fundamentals

**Build:**
- `backend/app/quant/lib.py` → all P0 functions (see `TOOLKIT_EXPANSION_PLAN_FINAL.md` for full list). All take `list[HistoricalBar]` from `app.market_data.schemas`.
- `backend/app/ta/lib.py` → `compute_sma`, `compute_ema`, `compute_rsi`
- `backend/app/market_data/schemas.py` → add `FundamentalsSnapshot` model (PE, PB, market_cap, EPS, dividend_yield — all `float | None`)
- `backend/app/market_data/provider.py` → add `YFinanceProvider.get_fundamentals(ticker: str) -> FundamentalsSnapshot`

The `get_fundamentals()` method calls `yf.Ticker(ticker).info` (same call as `get_quote()`) and extracts the fundamentals fields. Reliability caveat in the docstring: yfinance `.NS`/`.BO` fundamentals are directionally useful, not forensic-grade.

**Do NOT build yet**: `quant/tools.py`, `ta/tools.py`, `market_data/tools.py` additions (those are Stage 12).

**Test checkpoint (standalone):**
```python
from app.market_data.provider import YFinanceProvider
from app.quant.lib import compute_all_metrics
from app.ta.lib import compute_rsi

provider = YFinanceProvider()
hist = provider.get_historical("RELIANCE.NS", period="3mo", interval="1d")
fundamentals = provider.get_fundamentals("RELIANCE.NS")

metrics = compute_all_metrics(hist.bars)
print(metrics)  # expect: volatility 0.1-0.6, max_drawdown negative float, 52w values in range
print(fundamentals)  # some fields may be None — that's fine, not a crash

rsi = compute_rsi(hist.bars, window=14)
assert all(0 <= v <= 100 for v in rsi if v is not None)
```

Verify against 2-3 real NSE tickers. Confirm `get_fundamentals()` doesn't crash when yfinance returns `None` for a field (use `.get(key)`, never `[key]`). Confirm `compute_all_metrics()` returns a dict with all expected keys.

---

## Stage 4 — Evidence + Compliance lib functions

**Build:**
- `backend/app/evidence/lib.py` → five functions:
  - `check_data_freshness(pack: EvidencePack) -> dict[str, bool]` — returns `{item_id: is_fresh}` 
  - `validate_citations(citation_ids: list[str], pack: EvidencePack) -> dict[str, bool]` — `{id: is_valid}`
  - `compute_evidence_sufficiency_score(pack: EvidencePack) -> ConfidenceTier` — deterministic tier from item count + freshness spread + source diversity
  - `apply_price_shock(shock_pct: float, position_value: float) -> float` — simple arithmetic
  - `compute_scenario_ev(bull_prob: float, base_prob: float, bear_prob: float, bull_target: float, base_target: float, bear_target: float) -> float` — probability-weighted EV
- `backend/app/compliance/lib.py` → `run_compliance_check(ticker, recommendation, run_id, rules=None) -> dict`

**Do NOT build yet**: `evidence/tools.py` (@tool wrappers — Stage 12).

**Test checkpoint (standalone):**
```python
from app.evidence.schemas import EvidenceItem, EvidencePack
from app.evidence.lib import check_data_freshness, validate_citations, compute_evidence_sufficiency_score
from app.compliance.lib import run_compliance_check
from datetime import datetime, timezone, timedelta

today = datetime.now(timezone.utc)
pack = EvidencePack(
    pack_id="test",
    target="RELIANCE.NS",
    items=[
        EvidenceItem(id="news_001", type="news", source="tavily",
                     fetched_at=today, freshness="same_day", summary="test"),
        EvidenceItem(id="mkt_001", type="market_data", source="yfinance",
                     fetched_at=today - timedelta(days=10), freshness="stale", summary="test"),
    ],
    created_at=today,
)

freshness = check_data_freshness(pack)
assert freshness["mkt_001"] is False  # stale

valid = validate_citations(["news_001", "news_999"], pack)
assert valid["news_001"] is True
assert valid["news_999"] is False  # not in pack

# Verify compliance audit log appears
import logging, io
log_output = io.StringIO()
logging.getLogger("paisa.compliance.audit").addHandler(logging.StreamHandler(log_output))
run_compliance_check("RELIANCE.NS", "hold", "test_run_001")
assert "RELIANCE.NS" in log_output.getvalue()
```

---

## Stage 5 — Chroma integration

**Build:**
- `backend/app/research/chroma.py` → two functions:
  - `retrieve_prior_artifacts(target: str, top_k: int = 3) -> list[EvidenceItem]` — returns `[]` gracefully if collection empty
  - `embed_artifact(artifact_markdown: str, artifact_id: str, target: str, artifact_type: str) -> None` — chunks by Markdown header (`## ` prefix), upserts to Chroma

Use `chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)`. Collection name: `"research_artifacts"`.

**Test checkpoint:**
```python
from app.research.chroma import retrieve_prior_artifacts, embed_artifact

# Must return [] without error (actual first-run condition)
items = retrieve_prior_artifacts("RELIANCE.NS", top_k=3)
assert items == []

# Embed a fake artifact
embed_artifact(
    "## Financial Snapshot\nReliance had strong Q3 results.\n## Risks\nRegulatory headwinds.",
    artifact_id="test_001",
    target="RELIANCE.NS",
    artifact_type="ticker",
)

# Retrieve it back
items = retrieve_prior_artifacts("RELIANCE.NS", top_k=3)
assert len(items) > 0
assert items[0].type == "prior_artifact"
assert items[0].source == "chroma_retrieval"
```

Don't proceed until both cases (empty and non-empty) pass.

---

## Stage 6 — Watchlist service

**Build:**
- `backend/app/watchlist/__init__.py`
- `backend/app/watchlist/service.py` → `get_watchlist(user_id: str, session: AsyncSession) -> list[dict]`

Initially reads from `holdings` table, returns list of `{canonical_ticker, exchange}` dicts — same shape that the deep research planner needs. When UI is added later, this function will read from `watchlist_items` table instead; callers don't change.

**Test checkpoint:** Upload test CSV (sample already in `sample_imports/`). Call `get_watchlist("local-user", session)` — confirm it returns the holdings tickers as watchlist entries. No extra DB queries beyond what's needed.

---

## Stage 7 — Research schemas + output schemas + prompts

**Build:**
- `backend/app/research/schemas.py` → `ResearchPlan`, `MacroSummaryOutput`, `SectorSummaryOutput`, `TickerResearchOutput`, `PortfolioSynthesisOutput`, `TickerRecommendation` enum, `ConfidenceTier` enum (exact schemas in `implementation_plan.md`)
- `backend/app/research/state.py` → `ResearchState` TypedDict
- `backend/app/research/prompts/macro.py`, `sector.py`, `ticker.py`, `portfolio.py` → prompt template strings

**Do NOT wire into the graph yet.**

**Test checkpoint — one direct Ollama call per prompt template:**
```python
from app.llm.provider import get_structured_model
from app.research.schemas import MacroSummaryOutput
from app.evidence.schemas import EvidencePack, EvidenceItem

# Use real output from Stage 2 or hand-construct fake evidence pack
pack = ...  # your real or fake EvidencePack

from app.research.prompts.macro import build_macro_prompt
prompt = build_macro_prompt(pack)

model = get_structured_model(MacroSummaryOutput, provider="ollama")
result = model.invoke(prompt)
assert isinstance(result, MacroSummaryOutput)
assert all(cid in {i.id for i in pack.items} for cid in result.citations)  # no invented IDs
```

Repeat for all four schemas. If the model invents citation IDs, fix the prompt here — Stage 11's citation validation will reject them later and you want to know why now. Pay particular attention to the ticker schema: verify `bear_case` is populated, `kill_the_company` is non-generic, and `recommendation` is a value from the `TickerRecommendation` enum.

---

## Stage 8 — Planner node

**Build:**
- `backend/app/research/nodes/planner.py` → `plan_node(state: ResearchState) -> dict`

Static `{ticker: sector}` dict must be scoped to the tickers in your actual holdings. Update this dict as the watchlist changes — it's a small, explicit mapping for a small watchlist, not a lookup service.

**Test checkpoint:**
```python
from app.research.state import ResearchState
from app.research.nodes.planner import plan_node

state = ResearchState(run_id="test", plan=None, user_risk_profile="moderate", ...)
result = plan_node(state)
assert result["plan"].tickers  # non-empty
assert all(t in result["plan"].sector_queries for t in result["plan"].tickers)
assert all(t in result["plan"].ticker_queries for t in result["plan"].tickers)
# No None values in sector map
assert None not in result["plan"].sectors
```

---

## Stage 9 — Collection node

**Build:**
- `backend/app/research/nodes/collection.py` → `collect_all_node(state: ResearchState) -> dict`

Uses `asyncio.gather` internally. Calls directly (no @tool wrappers):
- `search.client.search(macro_query)` for macro
- `search.client.search(sector_query)` per sector (gathered)
- `market_data.provider.get_quote(ticker)`, `get_historical(ticker, ...)`, `get_fundamentals(ticker)` per ticker (gathered)
- `quant.lib.compute_all_metrics(bars)` inline (synchronous, no gather needed)
- `yf.Ticker(ticker).news` opportunistically; gracefully returns `[]` if empty
- `search.client.search(ticker_query)` per ticker (gathered)
- `research.chroma.retrieve_prior_artifacts(ticker)` per ticker (gathered)

All outputs assembled into `EvidencePack`s stored in state.

**Test checkpoint (no synthesis, no LLM):**
```python
import asyncio
from app.research.state import ResearchState
from app.research.nodes.collection import collect_all_node

state = ...  # state with plan from Stage 8

result = asyncio.run(collect_all_node(state))
# Inspect each evidence pack
print(result["macro_evidence"])  # should have news items
for ticker in plan.tickers:
    pack = result["company_evidence"][ticker]
    assert any(i.type == "computed_metric" for i in pack.items)  # quant metrics present
    assert any(i.source == "tavily" for i in pack.items)  # news present
print(result["prior_artifacts"])  # empty dict on first run
```

This is the last checkpoint before any LLM cost enters the loop. Be thorough here.

---

## Stage 10 — Graph wiring + synthesis nodes

**Build:**
- `backend/app/research/nodes/synthesis.py` → four node functions
- `backend/app/research/graph.py` → `build_research_graph() -> CompiledGraph`

Graph wiring:
```python
workflow = StateGraph(ResearchState)
workflow.add_node("plan", plan_node)
workflow.add_node("collect_all", collect_all_node)
workflow.add_node("synthesize_macro", synthesize_macro_node)
workflow.add_node("synthesize_sectors", synthesize_sectors_node)
workflow.add_node("synthesize_tickers", synthesize_tickers_node)
workflow.add_node("synthesize_portfolio", synthesize_portfolio_node)
workflow.add_node("persist", persist_node)

workflow.set_entry_point("plan")
workflow.add_edge("plan", "collect_all")
workflow.add_edge("collect_all", "synthesize_macro")
workflow.add_edge("synthesize_macro", "synthesize_sectors")
workflow.add_edge("synthesize_sectors", "synthesize_tickers")
workflow.add_edge("synthesize_tickers", "synthesize_portfolio")
workflow.add_edge("synthesize_portfolio", "persist")
workflow.add_edge("persist", END)
```

**Test checkpoint — add one synthesis node at a time:**

First, add only macro synthesis and run the graph to that node. Confirm macro artifact produced and matches Stage 7's standalone output. Then add sectors — confirm each sector artifact references macro context. Then add tickers — verify for each:
- `bear_case` is present and precedes `recommendation`
- `kill_the_company` is non-boilerplate
- `recommendation` is a valid enum value
- `citations` all resolve to real evidence pack IDs
- `confidence_score` is in 0–100

Then add portfolio synthesis — confirm it references specifics from multiple ticker artifacts.

---

## Stage 11 — Persist node

**Build:**
- `backend/app/research/nodes/persist.py` → `persist_node(state: ResearchState) -> dict`
- `backend/app/portfolio/lib.py` → `get_ticker_recommendation(ticker, session) -> dict | None`

Persist node sequence per LLM output (see `DEEP_RESEARCH.md` for full spec):
1. `validate_citations()` — log violations, record in `state["errors"]`, continue
2. `check_data_freshness()` — log stale items
3. Insert `ResearchArtifact` row; for ticker type, extract `recommendation` + `confidence_score` to denormalized columns
4. `embed_artifact()` into Chroma
5. `run_compliance_check()` — no-op + structured audit log
6. Render final Markdown

**Test checkpoint — full end-to-end run on 2 sectors / 3 tickers:**
```bash
# After running the full graph:
psql -c "SELECT artifact_type, target, recommendation, confidence_score FROM research_artifacts;"
# Expect: 1 macro row, 2 sector rows, 3 ticker rows (all with recommendation), 1 portfolio row

# Chroma embeddings
python -c "from app.research.chroma import retrieve_prior_artifacts; print(retrieve_prior_artifacts('RELIANCE.NS'))"
# Should now return items (non-empty — from the run you just did)

# Compliance audit log
grep "paisa.compliance.audit" app.log | head -5

# Recommendation read path
python -c "from app.portfolio.lib import get_ticker_recommendation; print(get_ticker_recommendation('RELIANCE.NS', session))"
# Should return {recommendation, confidence_score, run_id, generated_at}
```

Verify the final Markdown report is readable top-to-bottom.

---

## Stage 12 — API endpoints + reactive agent tool expansion

**Build:**
- `backend/app/research/router.py` → `/research/run`, `/research/runs/{run_id}`, `/research/recommendations`, `/research/recommendations/{ticker}`
- `backend/app/search/tools.py` → `web_search_tool` @tool wrapper
- `backend/app/quant/tools.py` → @tool wrappers for P0 functions
- `backend/app/ta/tools.py` → @tool wrappers for SMA, EMA, RSI
- `backend/app/portfolio/tools.py` → `get_ticker_recommendation_tool` @tool wrapper
- `backend/app/market_data/tools.py` → add `get_fundamentals_tool` @tool wrapper
- `backend/app/graph.py` → import expanded tool list as `AGENT_TOOLS`

**Test checkpoint:**
- `POST /research/run` triggers a run, returns `run_id`
- `GET /research/runs/{run_id}` returns the Markdown report once complete
- `GET /research/recommendations` returns all ticker recommendations (drives portfolio tab pills)
- Reactive agent still compiles: `build_agent(portfolio_context="")` succeeds with new tool list

---

## Stage 13 — Smoke test + second run validation

**Test checkpoint (validation only, no new code):**

1. Time the full research run start-to-finish. If collection is slower than expected, confirm `asyncio.gather` is actually running in parallel (not accidentally being awaited sequentially).
2. Run the graph a **second time**. Verify:
   - Chroma retrieval returns first run's artifacts in `prior_artifacts` (the RAG loop is working)
   - `market_snapshots` cache hits for quotes and historical data with fresh TTLs (no duplicate yfinance calls)
   - Search cache hits for queries identical to the first run (no duplicate Tavily calls)
3. Call `GET /research/recommendations` and verify the pills data matches the second run's outputs (not stale from first run).

---

## Sequencing notes

- **Stages 0–7 involve no graph wiring** — everything is tested as standalone functions and direct calls. Graph-level debugging is slower to iterate on than a direct function call; push as many bugs out of the graph as possible.
- **Stages 8–11 add one node type at a time**, always re-running from the start of the graph rather than testing a node in isolation with fake upstream input — this catches integration bugs (wrong field names between node output and next node's expected input) as early as possible.
- **Stage 11's citation membership check is new code** — it was previously identified as unresolved wiring debt. Don't skip it; don't treat it as already handled anywhere in the codebase.
- **If a stage's test checkpoint fails**, fix it before moving to the next stage. A broken Stage 3 test caught early costs 10 minutes; the same bug surfacing in Stage 11 costs hours of re-debugging through 8 layers of graph state.
