# DB Schema

**Source of truth:** `docs/MVP_PLAN.md`  
**Status:** Frozen for MVP prototype

## Storage Boundaries

- PostgreSQL is the source of truth for structured application state.
- ChromaDB stores rebuildable retrieval chunks only.
- Redis stores short-lived provider and market cache entries only.

## Core Tables

### Identity and Profile

- `users`
  - `id`, `email`, `display_name`, `is_demo_user`, `created_at`
- `user_profiles`
  - `id`, `user_id`, `risk_tolerance`, `investment_horizon`, `currency_base`, `updated_at`
- `investment_principles`
  - `id`, `user_id`, `title`, `body`, `priority`, `is_active`, `created_at`

### Portfolio

- `portfolio_imports`
  - `id`, `user_id`, `source_filename`, `status`, `row_count`, `valid_row_count`, `error_count`, `created_at`
- `holdings`
  - `id`, `user_id`, `portfolio_import_id`, `raw_ticker`, `canonical_ticker`, `exchange`, `asset_class`, `quantity`, `avg_buy_price`, `currency`, `purchase_date`, `created_at`
- `watchlist_items`
  - `id`, `user_id`, `ticker`, `exchange`, `notes`, `created_at`

### Market and Content

- `market_snapshots`
  - `id`, `user_id`, `ticker`, `provider`, `snapshot_type`, `payload_json`, `fetched_at`, `fresh_until`
- `news_documents`
  - `id`, `user_id`, `ticker`, `source`, `title`, `published_at`, `fetched_at`, `content_ref`, `metadata_json`
- `artifacts`
  - `id`, `user_id`, `artifact_type`, `title`, `source_run_id`, `storage_ref`, `metadata_json`, `created_at`

### Chat

- `chat_sessions`
  - `id`, `user_id`, `title`, `created_at`, `updated_at`
- `chat_messages`
  - `id`, `session_id`, `user_id`, `role`, `content`, `graph_run_id`, `created_at`

### Research

- `research_runs`
  - `id`, `user_id`, `scope_json`, `status`, `current_step`, `progress`, `error_message`, `final_result_id`, `started_at`, `completed_at`
- `research_run_steps`
  - `id`, `run_id`, `step_name`, `status`, `progress`, `message`, `payload_json`, `started_at`, `completed_at`
- `research_findings`
  - `id`, `run_id`, `ticker`, `thesis_summary`, `bear_case`, `confidence_tier`, `data_quality`, `suggested_action`, `supporting_evidence_json`
- `recommendations`
  - `id`, `user_id`, `source_type`, `source_id`, `action`, `confidence_tier`, `data_quality`, `summary`, `bear_case`, `no_action_case`, `assumptions_json`, `principle_conflicts_json`, `created_at`

### Audit

- `audit_events`
  - `id`, `user_id`, `run_id`, `session_id`, `actor`, `event_type`, `event_timestamp`, `input_hash`, `output_hash`, `source_refs_json`, `metadata_json`

## Required Constraints

- Every user-scoped table includes `user_id`.
- Holdings store both raw and canonical ticker values.
- Audit events are append-only at the application layer.
- Research run status values are limited to `queued`, `running`, `waiting_for_user`, `completed`, `failed`, `cancelled`.

