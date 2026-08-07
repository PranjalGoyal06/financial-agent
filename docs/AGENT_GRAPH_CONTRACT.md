# Agent Graph Contract

**Source of truth:** `docs/MVP_PLAN.md`  
**Status:** Frozen for MVP prototype

## Reactive Graph

The chat assistant uses a LangGraph pipeline with deterministic data loading, retrieval, validation, and structured response formatting.

### State

Required state keys:

- `session_id`
- `user_query`
- `user_profile`
- `portfolio`
- `watchlist`
- `principles`
- `relevant_tickers`
- `market_data`
- `retrieved_chunks`
- `evidence_pack`
- `data_quality`
- `compressed_context`
- `principle_conflicts`
- `llm_raw_output`
- `parsed_output`
- `validation_errors`
- `final_response`
- `audit_events`

### Nodes

1. `initialise_run`
2. `load_authoritative_context`
3. `identify_relevant_tickers`
4. `fetch_market_data`
5. `semantic_retrieve`
6. `build_evidence_pack`
7. `validate_data_quality`
8. `compress_context`
9. `principle_conflict_check`
10. `llm_reason`
11. `parse_and_validate_output`
12. `compliance_boundary_check`
13. `format_response`
14. `persist_outputs`

### Required Behaviour

- Skip LLM reasoning when data quality is `critical_failure`.
- Build evidence before reasoning.
- Allow the LLM to cite only evidence IDs from the current pack.
- Persist outputs and audit events for every run.
- Surface uncertainty, downside, and no-action framing in the final response.

## Research Graph

The research run is a persisted job that processes tickers sequentially.

### Steps

1. `initialise_research_run`
2. `load_scope`
3. `load_portfolio_context`
4. `for_each_ticker`
   - `fetch_market_data`
   - `fetch_fundamentals`
   - `retrieve_news_and_notes`
   - `build_ticker_evidence_pack`
   - `analyse_ticker_with_ollama`
   - `validate_ticker_output`
   - `persist_ticker_finding`
5. `synthesize_portfolio_view`
6. `validate_research_output`
7. `persist_recommendation`
8. `create_markdown_artifact`
9. `embed_artifact_in_chromadb`
10. `mark_run_completed`

### Research Run Rules

- Status is persisted in PostgreSQL.
- Progress must be visible step-by-step.
- Ticker analysis must include bear case, confidence, data quality, and supporting evidence.
- Final output must include a no-action case.
- Research results are saved as both structured data and a reusable Markdown artefact.

