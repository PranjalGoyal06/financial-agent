# Changes

## [2026-07-22] — Converted EQUITY_L.csv to stocks.json
- Converted raw `EQUITY_L.csv` into a structured JSON file at `backend/app/search/data/stocks.json` containing 2,387 stocks with fields `symbol`, `name`, `isin`, `series`, and `exchange: "NSE"`.
- Updated `backend/app/search/stocks_router.py` to load `stocks.json` instead of parsing CSV at runtime.

## [2026-07-22] — Implemented global stock search and chat integration
- Created `backend/app/search/stocks_router.py` providing `GET /api/search/stocks` which serves an in-memory cached list of equities from a local CSV.
- Created `frontend/src/components/StockSearch.tsx` to provide a premium autocomplete dropdown replacing the static search bar placeholder.
- Integrated the search bar to automatically switch to the Chat tab and pre-fill a contextual analysis prompt upon ticker selection.

## [2026-07-22] — Wrote High_Level_Overview.md from full codebase audit
- Documented all backend modules, ORM models, API endpoints, LangGraph pipelines (chat agent + deep research), frontend architecture, and data flows in `docs/High_Level_Overview.md`.
- Covers infrastructure (Docker Compose, env vars), all 14 agent tools, the 7-node research pipeline, evidence/citation system, briefing service, and frontend component tree.
- Added maintenance rules for both `High_Level_Overview.md` and `CHANGES.md` to `.gemini/instructions.md`.

## [2026-07-22] — Setup documentation tracking
- Added High_Level_Overview.md and CHANGES.md to `dev/docs/`
- Why: To maintain structured architectural context and a rolling changelog.
- Updated project instructions with rules for maintaining these files.
