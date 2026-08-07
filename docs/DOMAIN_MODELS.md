# Domain Models

**Source of truth:** `docs/MVP_PLAN.md`  
**Status:** Frozen for MVP prototype

## Enums

### Asset Class

`equity | etf | mf | bond | gold | other`

### Recommendation Action

`buy | hold | sell | reduce | add | watch | no_action | insufficient_data`

### Confidence Tier

`low | medium | high`

### Data Quality

`good | limited | stale | critical_failure`

### Research Run Status

`queued | running | waiting_for_user | completed | failed | cancelled`

### Claim Type

`data_supported | inference | assumption`

## Core Models

### UserProfile

- `user_id`
- `risk_tolerance`
- `investment_horizon`
- `currency_base`
- `principles: list[InvestmentPrinciple]`

### InvestmentPrinciple

- `id`
- `title`
- `body`
- `priority`
- `is_active`

### Holding

- `raw_ticker`
- `canonical_ticker`
- `exchange`
- `asset_class`
- `quantity`
- `avg_buy_price`
- `currency`
- `purchase_date`

### WatchlistItem

- `ticker`
- `exchange`
- `notes`

### MarketSnapshot

- `ticker`
- `provider`
- `snapshot_type`
- `payload`
- `fetched_at`
- `fresh_until`

### NewsDocument

- `ticker`
- `source`
- `title`
- `published_at`
- `fetched_at`
- `content_ref`

### EvidenceItem

- `evidence_id`
- `type`
- `ticker`
- `source`
- `title`
- `excerpt`
- `published_at`
- `retrieved_at`

### Claim

- `text`
- `claim_type`
- `evidence_ids: list[str]`

### RecommendationOutput

- `action`
- `confidence_tier`
- `data_quality`
- `summary`
- `bear_case`
- `expected_drawdown`
- `key_risks`
- `portfolio_impact`
- `upside_case`
- `no_action_case`
- `assumptions`
- `principle_conflicts`
- `claims`
- `next_steps`

### ResearchFinding

- `ticker`
- `thesis_summary`
- `bear_case`
- `key_risks`
- `valuation_notes`
- `confidence_tier`
- `data_quality`
- `principle_conflicts`
- `suggested_action`
- `supporting_evidence_ids`

## Invariants

- Numbers used in recommendations come from deterministic backend data.
- Claims must map to evidence IDs that exist in the active evidence pack.
- Recommendations always include downside framing and a no-action comparison.
- Compliance for the MVP is `not_implemented_mvp`, never `passed`.

