# Test Matrix

**Source of truth:** `docs/MVP_PLAN.md`  
**Status:** Frozen for MVP prototype

## Contract Coverage

| Area | What to verify |
| --- | --- |
| CSV import | Required columns, enum validation, row rejection, canonical ticker resolution |
| Portfolio persistence | Valid rows only, raw and canonical tickers stored, audit event written |
| Market data | Freshness metadata, stale fallback flagging, provider error handling |
| News ingestion | Manual refresh flow, chunking, rebuildable storage |
| Evidence pack | Stable evidence IDs, claims only cite pack IDs |
| Reactive graph | Node ordering, critical-failure short circuit, output validation |
| Research runs | Durable job states, sequential ticker loop, progress persistence |
| UX | Holding click-through, source drawer, risk-card prompt prefill, visible freshness |
| Audit | Append-only application behaviour, run/session linkage |

## Minimum Demo Tests

1. Import a valid portfolio CSV and confirm holdings are stored.
2. Reject a CSV row with missing `exchange` or invalid `asset_class`.
3. Open the dashboard and confirm metrics are derived from live data.
4. Ask a portfolio question and confirm the answer includes downside, confidence, and evidence.
5. Trigger a research run and confirm progress updates before completion.
6. Open a recommendation artefact and confirm it is reusable in chat.
7. Confirm no trade execution path exists.

