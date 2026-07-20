<!-- DEEP_RESEARCH.md — overnight mode design doc, aligned with dev worktree codebase -->

# PAISA — Deep Research (Overnight Mode) Design

## Context

PAISA is an AI-powered investment intelligence platform for Indian equity investors. It has two operating modes: a **reactive agent** (cloud LLM via Groq, responds to user chat queries, implemented as a `create_react_agent` ReAct loop) and a **deep research agent** (local Ollama LLM, processes watchlist tickers via a deterministic LangGraph state-graph, produces structured research artifacts and Markdown reports). This document specifies the deep research / overnight mode component.

**Governing architectural decision:** The research pipeline is a deterministic state-graph, not a free-roaming multi-agent system. No node autonomously chooses its own tools or spawns sub-agents. This document adds node types (macro, sector, ticker, portfolio) but every node is a fixed step in a pre-specified sequence.

**Key convention:** Deep research graph nodes call provider methods and lib functions **directly** — never via `@tool` wrappers. The `@tool` wrappers exist only for the reactive agent's LLM tool-calling surface. Same underlying functions, different call path.

**Governing principles** (from `PRINCIPLES.md`) that directly shape this design: LLM reasons, deterministic tools calculate (#1); every claim must be traceable (#5); uncertainty is a first-class output (#3); loss asymmetry — downside before upside (#4); fiduciary purity (#7); data integrity precedes analysis (#6); compliance is a hard constraint, audit even no-op state (#11); tools are layered, Layer 1 and Layer 2 are never mixed (#12).

## What was deliberately cut, and why

A much larger version of this design was considered (full macro pipeline with GDELT/RSS/liquidity/credit-spread ingestion, financial forensics, quant screening, alternative data, delta-based artifact diffing, a dedicated LLM "research agenda" node, per-node bespoke evidence schemas, multi-tier news ingestion). All of it is cut for shared reasons: each item requires new infrastructure whose build cost exceeds its marginal value.

- **Macro pipeline (GDP, credit spreads, liquidity, RBI data feeds)** — no data source exists yet. Replaced with a single index-quote call as market backdrop.
- **Financial forensics (NI vs OCF, accruals, debt maturity)** — yfinance fundamentals on `.NS`/`.BO` tickers is not reliable enough for forensic-grade claims; doing forensics on shaky data violates Principle #6. Deferred until a real fundamentals provider is integrated.
- **Delta-based artifact updates** — needs diff logic against a prior artifact plus a first-run fallback branch. Prior artifacts are still used as RAG context, just not as a mandatory diff target.
- **Dedicated LLM "Research Agenda" node** — folded into the Planner as templated (non-LLM) output.
- **Static sector taxonomy service** — replaced with a static `{ticker: sector}` dict scoped only to the watchlist.
- **GDELT + RSS bulk ingestion tier** — correct long-term design, explicitly out of scope. Total Tavily calls for one full research run are under 10, nowhere near free-tier quota pressure for a single run.
- **Per-node bespoke evidence structures** — rejected in favor of one reused `EvidencePack` schema.
- **Per-node-type storage tables** — rejected in favor of one `research_artifacts` table shape reused across all output types.

## Data source decision

**Tavily only**, for primary search. It returns cleaned, deduplicated snippets with source URL and published date — maps directly onto `EvidenceItem` with no HTML-cleaning step. Integrated via `search/client.py` with 20-minute caching in the existing `market_snapshots` table (`snapshot_type="search_snapshot"`).

**Known accepted risk**: Tavily is a single external paid dependency with no fallback. If its API has an outage, this component has no backup path. Treated the same way the yfinance no-SLA risk is documented — an explicit, accepted assumption.

**Supplementary, free, non-blocking**: `yf.Ticker(symbol).news` is called opportunistically alongside the existing yfinance calls already made for quote/historical data. It frequently returns empty — when it does, the node proceeds with Tavily results alone. When it returns data, its items are added as additional low-cost `EvidenceItem`s. This is not a second search integration — it's a zero-cost bonus read on an object the pipeline already instantiates.

## Watchlist

The deep research graph runs against the user's **watchlist**. A `WatchlistItem` domain object and `get_watchlist()` service function are created as part of this plan. Initially, `get_watchlist()` reads from the `holdings` table — so the watchlist defaults to all current holdings. UI to create/manage watchlists is a future feature; the service function hides this detail from callers and can be updated when that UI exists.

## Evidence Pack (single schema, reused everywhere)

Canonical location: `backend/app/evidence/schemas.py`.

```python
class EvidenceItem(BaseModel):
    id: str                # short unique id, referenced in LLM citations
    type: Literal["news", "market_data", "prior_artifact", "computed_metric"]
    source: Literal["tavily", "yfinance", "chroma_retrieval", "internal_computation"]
    url: str | None = None       # for news items
    title: str | None = None     # for news items
    published_at: datetime | None = None  # article pub date (≠ fetched_at)
    fetched_at: datetime         # when retrieved or computed
    freshness: Literal["same_day", "this_week", "stale"]
    summary: str                 # prompt-ready text

class EvidencePack(BaseModel):
    pack_id: str
    target: str            # canonical_ticker / sector name / "macro" / "portfolio"
    items: list[EvidenceItem]
    created_at: datetime
```

`freshness` is computed deterministically: `same_day` = today, `this_week` = within 7 days, `stale` = older.

One `EvidencePack` per target (macro / sector / ticker). All `EvidenceItem` types (Tavily results, yfinance news, computed metrics, quote data, prior Chroma artifacts) use the same schema.

## Storage

One `research_artifacts` table reused across all node output types (in `backend/app/models.py`):

```python
class ResearchArtifact(Base):
    __tablename__ = "research_artifacts"

    id: str (UUID)
    run_id: str              # links all artifacts from one run
    artifact_type: str       # "macro" | "sector" | "ticker" | "portfolio"
    target: str | None       # sector name / canonical_ticker / null
    content_markdown: str    # full LLM output in Markdown
    evidence_pack_json: str  # serialized EvidencePack
    recommendation: str | None  # denormalized for fast portfolio reads
    confidence_score: int | None  # 0-100, denormalized for pill display
    created_at: datetime
```

`recommendation` and `confidence_score` are denormalized columns extracted from the structured ticker output at persist time. This keeps the portfolio tab recommendation pill fast — no JSON parsing needed.

Every node writes here. Chroma embedding happens at persist time, chunked by Markdown header, keyed so next run's retrieval node can pull top-k relevant prior artifacts per ticker/sector.

## Chroma Integration

Uses `chromadb.HttpClient` connecting to the ChromaDB container already running in Docker Compose on port 8001. Configuration: `settings.chroma_host` + `settings.chroma_port`. Wrapper in `research/chroma.py`:
- `embed_artifact(artifact_markdown, metadata)` — chunks by Markdown header, upserts to Chroma
- `retrieve_prior_artifacts(target, top_k)` — returns `[]` gracefully if collection is empty (first run condition)

## Graph topology

```
plan → collect_all → synthesize_macro → synthesize_sectors
     → synthesize_tickers → synthesize_portfolio → persist
```

**plan**: No LLM. Reads watchlist via `get_watchlist()`, looks up each ticker's sector via a static `{ticker: sector}` dict (scoped to watchlist only), and emits a `ResearchPlan` with all Tavily query strings pre-formed.

**collect_all**: All deterministic, no LLM reasoning. Uses `asyncio.gather` internally for parallel I/O:
- Macro news: one Tavily query
- Sector news: one Tavily query per sector (gathered)
- Company data per ticker (gathered): call `market_data.provider.get_quote()`, `get_historical()`, `get_fundamentals()` directly; compute `quant.lib.compute_all_metrics()` inline in Python; opportunistic `yf.Ticker.news`
- Company news per ticker (gathered): one Tavily query per ticker
- Prior artifacts per ticker (gathered): `research.chroma.retrieve_prior_artifacts()`

All outputs normalized to `EvidencePack`s. No `@tool` wrappers used — direct provider and lib calls only.

**synthesize_macro** (1 LLM call): Input: macro evidence pack. Output: `MacroSummaryOutput`.

**synthesize_sectors** (1 LLM call per sector): Input: macro artifact + sector evidence pack. Output: `SectorSummaryOutput` per sector.

**synthesize_tickers** (1 LLM call per ticker): Input: macro artifact, relevant sector artifact, company evidence pack (news + computed metrics from quant.lib), RAG-retrieved prior artifacts, user risk profile (loaded once per run). Output — `TickerResearchOutput` Pydantic schema, bear-case ordered before recommendation per Principle #4:

```python
class TickerResearchOutput(BaseModel):
    ticker: str
    financial_snapshot_summary: str  # narrates computed metrics, no invented numbers
    bear_case: str                    # precedes bull_case — enforced by field order
    kill_the_company: str             # forces model to argue against its own thesis
    bull_case: str
    key_risks: list[str]             # tagged: business/financial/regulatory/market
    confidence_tier: ConfidenceTier
    confidence_score: int            # 0-100 — maps to portfolio tab pill display
    confidence_justification: str
    user_fit_note: str               # references injected risk profile
    recommendation: TickerRecommendation  # buy/add/hold/reduce/watch/no_action/insufficient_data
    citations: list[str]             # evidence pack item IDs only
```

`no_action` and `insufficient_data` are valid, non-penalized recommendation outputs (Principle #7).

**synthesize_portfolio** (1 LLM call): Input: all macro/sector/ticker artifacts from this run, watchlist, user profile. Output: `PortfolioSynthesisOutput`.

**persist**: Deterministic. For every LLM output:
1. `evidence.lib.validate_citations()` — verify every citation ID actually exists in that node's evidence pack. Violations are logged and recorded in state errors but don't crash the run.
2. `evidence.lib.check_data_freshness()` — flag stale items.
3. Insert `ResearchArtifact` row — for ticker artifacts, extract `recommendation` and `confidence_score` into denormalized columns.
4. `research.chroma.embed_artifact()` — embed artifact markdown into Chroma.
5. `compliance.lib.run_compliance_check()` — no-op currently but always executes and logs a structured audit event via Python `logging` (logger name: `paisa.compliance.audit`). Silent skipping is not acceptable per Principle #11.
6. Render final Markdown report stitching all artifacts into one document.

## LLM usage

- **Synthesis nodes** use `get_structured_model(OutputSchema, provider="ollama")` from the existing `llm/provider.py`.
- Ollama serializes on a single GPU regardless of upstream fan-out; keep the watchlist small (2 sectors / 3 tickers) during initial testing to keep runtime manageable.

## Principles mapping

| Principle | How this design satisfies it |
|---|---|
| #1 LLM reasons, doesn't calculate | All financial metrics computed in Python before the LLM ever sees them; LLM only narrates. |
| #3 Uncertainty is first-class | `confidence_tier` + `confidence_score` + justification required on every output. |
| #4 Loss asymmetry | `bear_case` and `kill_the_company` structurally precede `recommendation` in the output schema. |
| #5 Traceability | Every LLM output cites `EvidencePack` item IDs; persist stage enforces citation membership check before storage. |
| #6 Data integrity | Every `EvidenceItem` carries `source` and `freshness`; yfinance/Tavily reliability limits are documented assumptions, not silent gaps. |
| #7 Fiduciary purity | `no_action` and `insufficient_data` are explicit, valid outputs, not penalized. |
| #11 Compliance | Persist stage logs a structured audit event even for the current compliance no-op. |
| #12 Layered tools | Deep research calls provider methods and lib functions directly — never @tool wrappers. Layer 1 and Layer 2 are physically separate modules. |

## Open risks

- Tavily is a single point of failure with no fallback — documented assumption.
- Ollama serializes on a single GPU; keep watchlist small during development.
- Company IR pages and NSE/BSE announcement feeds are noted for the future scaling path but explicitly out of scope.
- Citation membership check at persist time is new code — do not treat it as already handled.