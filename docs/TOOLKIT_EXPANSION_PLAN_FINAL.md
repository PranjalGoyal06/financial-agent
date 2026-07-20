<!-- TOOLKIT_EXPANSION_PLAN_FINAL.md — supersedes TOOLKIT_EXPANSION_PLAN.md and AGENT_TOOL_SURFACE_EXPANSION.md -->
<!-- Last revised: architecture aligned with domain-module codebase structure -->

# SCALE — Toolkit Expansion Plan (Final)

## Status

This document replaces both `TOOLKIT_EXPANSION_PLAN.md` and `AGENT_TOOL_SURFACE_EXPANSION.md`. It tiers every tool against the implementation roadmap and resolves every open design question.

## Ground rules

- **Pure functions first, thin `@tool` wrappers second.** Every deterministic capability is a plain Python function with no LLM involvement, independently unit-testable. A `@tool` wrapper is added on top only for functions the reactive agent needs to invoke via LLM tool-calling.
- **Deep research calls lib functions and provider methods directly.** The deep research graph never goes through LangChain tool-calling — its nodes import and call pure functions inline.
- **No Protocol/registry abstraction unless a tool has genuinely swappable implementations.** `MarketDataProvider` earns a Protocol because yfinance today and Kite Connect later are both real. Quant math, TA, compliance rules, and search have exactly one implementation each right now — keep them as plain modules.
- **Fetched data (quotes, historical bars, search results) is cached in `market_snapshots`.** New `snapshot_type` values are added per category (e.g. `"search_snapshot"`). Computed metrics are **never cached** — they are deterministic pure functions; recompute on demand from already-cached input data.
- **A Sharpe ratio, an RSI, a compliance check, or a search query doesn't change meaning depending on which consumer is asking for it.** Both consumers (deep research graph, reactive chat) must hit the same underlying implementation — never build parallel "research mode" and "chat mode" versions of the same calculation.

## New rule: mandatory gates are never LLM-callable

Some tools are not optional analysis the LLM might choose to run — they are gates that must always fire (compliance checks, data-freshness checks, citation validation, evidence-sufficiency scoring). Wrapping a mandatory gate as a `@tool` hands the LLM discretion over whether to run it at all, which defeats the point of it being mandatory. **Every tool in Categories 8 and 9 below is a forced graph step, called directly by graph nodes exactly like a quant lib function — none of them get a `tools.py` wrapper or LLM tool-calling access.**

## Tiering principle

P0 = required for deep research graph to run end-to-end. P1 = build after P0 is verified, in dependency order. P2 = documented, not built.

---

## Module layout (final)

All new modules live under `backend/app/` as domain directories, consistent with the existing `market_data/` pattern.

```
backend/app/
  market_data/            # existing Layer 1 — raw fetch
    provider.py           # add get_fundamentals() here
    schemas.py            # add FundamentalsSnapshot here
    tools.py              # add get_fundamentals_tool here
  search/                 # NEW Layer 1 — Tavily fetch
    client.py             # search() function, cache via market_snapshots
    schemas.py            # SearchResult, SearchResponse
    tools.py              # web_search_tool @tool wrapper
  quant/                  # NEW Layer 2 — pure computation
    lib.py                # all quant math functions
    tools.py              # @tool wrappers for reactive agent
  ta/                     # NEW Layer 2 — technical analysis
    lib.py
    tools.py
  portfolio/              # NEW Layer 2 — portfolio analytics
    lib.py                # compute_portfolio_value, get_ticker_recommendation, etc.
    tools.py
  compliance/             # forced graph steps only — no tools.py
    lib.py
  evidence/               # forced graph steps + select tools
    schemas.py            # EvidenceItem, EvidencePack (canonical location)
    lib.py
    tools.py              # apply_price_shock_tool, compute_scenario_ev_tool only
  watchlist/              # Watchlist model + service
    service.py
  research/               # Deep research graph
    graph.py              # build_research_graph()
    state.py              # ResearchState
    schemas.py            # ResearchPlan, all output schemas
    chroma.py             # Chroma HTTP client wrapper
    nodes/                # planner.py, collection.py, synthesis.py, persist.py
    prompts/              # macro.py, sector.py, ticker.py, portfolio.py
```

**Layer 1 (raw fetch)** tools always live in `market_data/` or `search/`.
**Layer 2 (computation)** tools live in `quant/`, `ta/`, `portfolio/`, `evidence/`.
Mixing layers in one module is an architecture violation (Principle #12).

---

## 1. Quant Math (`quant/lib.py` + `quant/tools.py`)

Input price series type: `list[HistoricalBar]` from `market_data/schemas.py`.

| Function | Tier | Output |
|---|---|---|
| `compute_returns(bars, method)` | P0 | float(s) — method: simple/log/cagr |
| `compute_volatility(bars, window)` | P0 | float (annualized) |
| `compute_max_drawdown(bars)` | P0 | (float, date, date) — magnitude + dates |
| `compute_52w_distance(bars)` | P0 | dict with pct_from_high + pct_from_low |
| `compute_sharpe_ratio(bars, risk_free_rate)` | P0 | float |
| `compute_correlation_matrix(bars_dict)` | P0 | nested dict |
| `compute_all_metrics(bars)` | P0 | dict of all above — used by deep research collection node |
| `compute_beta(bars, index_bars)` | P1 | float, vs. Nifty |
| `compute_sortino_ratio(bars)` | P1 | float |
| `compute_concentration_hhi(weights)` | P1 | float |
| `compute_position_sizing(risk_params, portfolio_value)` | P1 | float |
| `compute_historical_var(bars, confidence)` | P2 | stub only |
| `compute_parametric_var(bars, confidence)` | P2 | stub only |

## 2. Extended Data Retrieval (in `market_data/` — Layer 1)

| Tool | Tier | Source | Notes |
|---|---|---|---|
| `get_fundamentals_tool` | P0 | yfinance `.info` | PE, PB, market cap, EPS, dividend yield. Reliability caveat in docstring — yfinance .NS/.BO fundamentals are directionally useful, not forensic-grade |
| `get_peer_comparison_tool` | P1 | fundamentals × sector map | — |
| `get_ownership_data_tool` | P1 | yfinance `major_holders` | Same reliability caveat |
| `get_corporate_actions_tool` | P1 | yfinance `actions` | Narration only — not wired into FIFO cost-basis math |
| `get_earnings_calendar_tool` | P1 | yfinance `calendar` | Catalyst flag |
| `get_options_chain_tool` | P2 | yfinance `option_chain` | Stub only |

## 3. Technical Analysis (`ta/lib.py` + `ta/tools.py`)

| Function | Tier | Output |
|---|---|---|
| `compute_sma(bars, window)` | P0 | list[float\|None] |
| `compute_ema(bars, window)` | P0 | list[float\|None] |
| `compute_rsi(bars, window)` | P0 | list[float\|None] |
| `compute_macd(bars)` | P1 | MACD, signal, histogram |
| `compute_bollinger_bands(bars, window, std_dev)` | P1 | upper/mid/lower |
| `detect_trend_vs_ma(bars, ma_series)` | P1 | label (above/below/crossing) |
| `compute_volume_profile(bars)` | P2 | stub only |
| `detect_support_resistance(bars)` | P2 | stub only |

## 4. Search / News (`search/client.py` + `search/tools.py`)

| Tool | Tier | Source | Output | Notes |
|---|---|---|---|---|
| `web_search_tool` | **P0** | Tavily API | list[EvidenceItem] | One flexible tool — caller constructs the query string for company-scoped or macro/sector queries |

**Integration decisions:**
- Direct API integration via `search/client.py`, configured via `settings.tavily_api_key` — **not** a Remote MCP connection.
- Results mapped directly to `EvidenceItem` schema (canonical in `evidence/schemas.py`).
- Cache via `market_snapshots` table, `snapshot_type="search_snapshot"`, TTL 20 minutes, keyed by `sha256(query + max_results)`.
- **Cache-read path is built and verified before running live Tavily tests** — free tier has a real ceiling.

## 5. Portfolio Analytics (`portfolio/lib.py` + `portfolio/tools.py`)

| Tool | Tier | Input | Notes |
|---|---|---|---|
| `compute_portfolio_value(holdings, quotes)` | P0 | holdings + live quotes | — |
| `compute_allocation_breakdown(holdings, quotes)` | P0 | holdings + quotes | % weight per holding |
| `get_ticker_recommendation(ticker, session)` | **P0** | ticker, DB session | Reads `recommendation` + `confidence_score` columns from latest `research_artifacts` row — fast, no JSON parsing. Returns None if no artifact exists yet |
| `compute_sector_exposure(holdings, sector_map)` | P1 | — | — |
| `compute_portfolio_volatility(weights, corr_matrix, vols)` | P1 | — | — |
| `compute_portfolio_beta(weighted_betas)` | P1 | — | — |
| `compute_portfolio_drawdown(hist_portfolio_values)` | P1 | — | — |
| `diff_portfolio_snapshot` | P2 | — | Stub only |
| `detect_unusual_movement` | P2 | — | Stub only |

**On recommendation generation:** Generating the recommendation (buy/sell/hold + reasoning) is done by the deep research ticker node (LLM via structured output). What's listed here is the **read path** — a deterministic DB query that retrieves the last stored recommendation for display in the portfolio tab.

## 6. Rebalancing & Execution Prep (`portfolio/lib.py`)

| Function | Tier | Notes |
|---|---|---|
| `compute_target_weight(risk_profile)` | P1 | Heuristic, not optimization — labeled as such |
| `compute_rebalance_deltas(current, target)` | P1 | Depends on compute_target_weight — must be built after |

**`prepare_order_ticket` is not a tool.** It is a plain backend endpoint behind a human-approval UI button — never LLM-callable. Build whenever the approval UI is built.

## 7. Cost & Tax (`cost_tax/lib.py`)

| Function | Tier |
|---|---|
| `estimate_transaction_cost(trade_value, broker_schedule)` | P1 |
| `estimate_capital_gains_tax(holding_period, gain_loss)` | P1 |

## 8. Compliance (`compliance/lib.py`) — forced graph step, no tools.py

| Function | Tier | Notes |
|---|---|---|
| `run_compliance_check(ticker, recommendation, run_id, rules)` | P0 | Currently a no-op (zero rules configured). Always logs a structured audit event via Python `logging` regardless of outcome — silent no-op is unacceptable per Principle #11 |

## 9. Evidence & Confidence Scoring (`evidence/lib.py`) — mostly forced graph steps

| Function | Tier | Notes |
|---|---|---|
| `compute_evidence_sufficiency_score(pack)` | P0 | Returns `ConfidenceTier`. LLM must justify any deviation |
| `check_data_freshness(pack)` | P0 | Flags stale items per EvidenceItem.freshness |
| `validate_citations(citation_ids, pack)` | P0 | Pass/fail per citation ID — membership check only |
| `compute_scenario_ev(bull_prob, base_prob, bear_prob, targets)` | **P0** | Probability-weighted EV. Documented exception to "LLM never does math" — LLM proposes probabilities, this tool guarantees the arithmetic is deterministic |
| `apply_price_shock(shock_pct, position_value)` | **P0** | Computes resulting value change — foundation of stress-test subgraph |
| `cross_reference_figures` | P2 | Stub — only useful once 2+ independent data sources exist |

---

## Consumer map

- **Deep research graph nodes** call lib functions and provider methods directly across every category. No `@tool` wrappers, no LLM tool-calling.
- **Reactive agent tool-calling (`@tool` wrappers)** exists for: `market_data/tools.py`, `search/tools.py`, `quant/tools.py`, `ta/tools.py`, `portfolio/tools.py`, `evidence/tools.py` (price shock + scenario EV only). These expand the `AGENT_TOOLS` list in `graph.py`.
- **Never LLM-callable, forced steps only:** everything in `compliance/lib.py` and `evidence/lib.py` except `apply_price_shock` and `compute_scenario_ev`.
- **Not part of the agent tool surface at all:** `prepare_order_ticket`.

---

## Explicitly out of scope

Applying corporate-action data (bonus issues, splits) as a correction to FIFO cost-basis reconstruction. `get_corporate_actions_tool` stays P1 for narration only.

---

## Build order

See `DEEP_RESEARCH_IMPLEMENTATION_STAGES.md` for the stage-by-stage build plan with test checkpoints.

---

## Principles alignment

- Every function in this toolkit is the deterministic half of Principle #1 — the LLM narrates, never computes.
- The one sanctioned exception is scenario-probability assignment feeding `compute_scenario_ev`, documented in that function's docstring.
- Layer 1 (raw fetch) and Layer 2 (computation) are physically separated into different modules — not just conceptually distinguished (Principle #12).
- All demoted and P2 tools are real, findable answers to "what's next" — nothing is silently dropped.
