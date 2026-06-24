# API Contract

**Source of truth:** `docs/MVP_PLAN.md`  
**Status:** Frozen for MVP prototype

## Principles

- Resource-oriented REST under `/api/v1`.
- Deterministic operations live behind the API; the LLM never calls providers directly.
- Responses must expose data quality, freshness, and run state where relevant.
- No trade execution endpoints.

## Core Endpoints

### Portfolio

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/portfolio/imports` | Upload and validate a portfolio CSV |
| GET | `/api/v1/portfolio` | Fetch portfolio overview |
| GET | `/api/v1/portfolio/summary` | Fetch portfolio metrics summary |
| GET | `/api/v1/portfolio/holdings` | List validated holdings |
| GET | `/api/v1/portfolio/imports/{import_id}` | Inspect an import |
| DELETE | `/api/v1/portfolio/holdings/{holding_id}` | Remove a holding |

### Watchlist

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/watchlist` | List watchlist items |
| POST | `/api/v1/watchlist/items` | Add a watchlist item |
| DELETE | `/api/v1/watchlist/items/{ticker}` | Remove a watchlist item |

### Market Data

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/market/quotes?tickers=...` | Fetch quotes for one or more tickers |
| POST | `/api/v1/market/refresh` | Refresh market data |
| GET | `/api/v1/market/freshness` | Report freshness and staleness |

### News

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/news/refresh` | Refresh ticker news |
| GET | `/api/v1/news?tickers=...` | Fetch stored news items |

### Artefacts

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/artifacts` | List artefacts |
| POST | `/api/v1/artifacts` | Create an artefact record |
| GET | `/api/v1/artifacts/{artifact_id}` | Fetch artefact details |
| DELETE | `/api/v1/artifacts/{artifact_id}` | Delete artefact record |

### Chat

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/chat/sessions` | Create a chat session |
| GET | `/api/v1/chat/sessions` | List chat sessions |
| GET | `/api/v1/chat/sessions/{session_id}` | Fetch session metadata |
| POST | `/api/v1/chat/sessions/{session_id}/messages` | Send a message and run the reactive graph |
| GET | `/api/v1/chat/sessions/{session_id}/messages` | List messages |
| GET | `/api/v1/chat/sessions/{session_id}/events` | Stream or poll session events |

### Research Runs

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/research-runs` | Create a persisted research run |
| GET | `/api/v1/research-runs` | List research runs |
| GET | `/api/v1/research-runs/{run_id}` | Fetch run status |
| GET | `/api/v1/research-runs/{run_id}/events` | Fetch progress events |
| GET | `/api/v1/research-runs/{run_id}/result` | Fetch final result |
| POST | `/api/v1/research-runs/{run_id}/cancel` | Cancel a queued or running job |

### Recommendations

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/recommendations` | List recommendations |
| GET | `/api/v1/recommendations/{recommendation_id}` | Fetch one recommendation |
| GET | `/api/v1/recommendations/{recommendation_id}/evidence` | Fetch linked evidence |
| POST | `/api/v1/recommendations/{recommendation_id}/decision` | Record user decision state |

### Audit

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/audit/events?run_id=...` | List audit events for a run |
| GET | `/api/v1/audit/runs/{run_id}` | Fetch run-level audit summary |

## Contract Notes

- CSV import must reject malformed rows before persistence.
- Market responses must include freshness metadata and staleness flags where applicable.
- Chat responses must be structured, risk-first, and include evidence references when available.
- Research runs are durable jobs, not ephemeral background tasks.

