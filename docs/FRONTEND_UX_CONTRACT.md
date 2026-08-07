# Frontend UX Contract

**Source of truth:** `docs/MVP_PLAN.md`  
**Status:** Frozen for MVP prototype

## Layout

Single-page React app with three persistent zones:

| Zone | Purpose |
| --- | --- |
| Top bar | Portfolio value, day change, freshness, latest research status, refresh action |
| Left panel | Holdings, allocation, exposure, concentration risk |
| Centre panel | Briefing, risk cards, watchlist findings, research run status |
| Right panel | Chat thread, suggested prompts, query box, evidence drawer |

## Required Behaviours

- Clicking a holding opens its detail context and pre-fills relevant prompts.
- Clicking a risk card pre-fills a chat question.
- Clicking a source opens the evidence drawer.
- Data freshness must be visible before the user asks a question.
- Research progress must render step-by-step.
- The UI must separate facts, inferences, assumptions, and recommendations.

## Response Card Contract

Every chat answer should support this structure:

- Recommendation / conclusion
- Confidence tier
- Data quality status
- Bear case
- Portfolio impact
- Upside case
- No-action case
- Assumptions
- Evidence / sources

## Demo Priorities

The first screen should immediately show:

1. What the user owns.
2. What deserves attention.
3. How to ask follow-up questions.

The app should feel like a portfolio dashboard plus intelligence feed plus chat, not a blank chatbot.

