# SCALE Finance Agent MVP — Updated Frontend Design Specification

## 0. Purpose of This Specification

This document defines the frontend design direction for the SCALE Finance Agent MVP.

The goal of the MVP frontend is not merely to expose backend functionality. The goal is to **showcase the product vision through a credible, professional, portfolio-first interface**, even where some backend wiring is incomplete or represented by honest demo states.

The interface should allow a judge, user, or developer to understand the product without reading the backend code.

The MVP should communicate:

1. The user owns a real portfolio.
2. The system understands that portfolio.
3. The system surfaces risks, opportunities, evidence, and uncertainty.
4. The user can ask follow-up questions naturally.
5. Deep research can be triggered and saved as reusable artefacts.
6. No trade is executed by the system.
7. AI outputs are advisory, traceable, and bounded by human decision-making.

The frontend should feel like:

> Groww / Zerodha Console / INDmoney for portfolio familiarity
> Bloomberg-lite / professional analytics dashboard for seriousness
> ChatGPT / Claude / Gemini for conversational interaction
> Notion / GitHub-style drawers for evidence, audit, and research artefacts

The MVP must not feel like:

> An empty chatbot with finance-themed prompts
> A fake autonomous trading terminal
> A crypto-style neon dashboard
> A black-box AI oracle
> A broker execution platform

---

# 1. Product Positioning

## 1.1 One-line product identity

SCALE is a portfolio-aware investment intelligence dashboard with an AI reasoning layer.

## 1.2 User-facing promise

SCALE helps investors understand their portfolio, inspect risks, analyse holdings, ask portfolio-aware questions, and generate structured research reports.

## 1.3 MVP promise

The MVP demonstrates:

* Portfolio import and display.
* Derived portfolio metrics.
* Risk and exposure visibility.
* Conversational AI assistant.
* Query-aware financial response cards.
* Evidence and reasoning traceability.
* User-triggered Deep Research runs.
* Saved research artefacts.
* Recommendation history.
* Honest data freshness and confidence indicators.
* No trade execution.

## 1.4 What the MVP is not

The MVP is not:

* A trading bot.
* A broker app.
* A real-time market terminal.
* A fully autonomous monitoring agent.
* A compliance-certified investment advisor.
* A portfolio optimiser with execution capabilities.
* A production-grade multi-user wealth platform.

The UI should therefore avoid language that implies unsupported capabilities.

Use:

* “Latest Research Briefing”
* “Generated from last portfolio review”
* “Run Deep Portfolio Review”
* “Refresh market data”
* “Advisory recommendation”
* “No trade will be executed”

Avoid:

* “Live AI alerts”
* “Autonomous monitoring”
* “Guaranteed recommendation”
* “Execute trade”
* “Compliance passed”
* “Always-on market watcher”

---

# 2. Core UX Philosophy

## 2.1 The dashboard hierarchy

The dashboard should prioritise information in this order:

1. Portfolio reality.
2. Risk and data freshness.
3. AI-generated intelligence.
4. Conversational follow-up.
5. Evidence and audit trail.

This means the homepage should not be chat-first. Chat is important, but it should be embedded inside the portfolio command centre rather than replacing it.

## 2.2 The three-zone dashboard

The dashboard must follow a three-zone structure:

```text
Portfolio dashboard + Intelligence briefing + Chat rail
```

The three zones should work together:

* Clicking a holding opens holding details and suggested chat prompts.
* Clicking a risk card pre-fills the chat input.
* Clicking an evidence chip opens the evidence drawer.
* Clicking “View Report” opens a research artefact.
* Clicking “Ask AI” expands or routes to the full chat page.

## 2.3 Conversational-first chat

The chat UI should feel conversational by default.

Most normal queries should produce normal assistant messages.

Special financial queries should produce a normal assistant bubble followed by one or more structured cards.

Examples:

* “What is beta?” → plain educational chat bubble.
* “News on Reliance?” → news digest card.
* “Should I add more INFY?” → recommendation card.
* “Compare TCS and INFY” → comparison card.
* “Do technical analysis on HDFC Bank” → technical analysis card.
* “Analyse my portfolio risk” → portfolio snapshot card.
* “Run deep research on my watchlist” → research run launcher/status card.

This keeps the assistant natural while allowing serious financial outputs to be structured and auditable.

---

# 3. Design System

## 3.1 Theme

SCALE should be **dark-mode-first**, not dark-mode-only.

Dark mode gives the MVP a premium analytical feel and works well for demo environments. However, the design system should not assume that finance tools must always be dark. A light theme can be added later.

Default MVP theme: dark.

## 3.2 Colour palette

Use a restrained, professional finance palette.

```css
--background: #0D0F1A;
--surface: #13162A;
--card: #1B1F35;
--card-muted: #171B2E;
--border: #2A2F4A;

--accent-primary: #5B7FFF;
--accent-primary-hover: #6E8DFF;

--accent-ai-start: #6366F1;
--accent-ai-end: #818CF8;

--positive: #34D399;
--negative: #F87171;
--warning: #FBBF24;
--info: #60A5FA;

--text-primary: #E4E8FF;
--text-secondary: #A8B0D0;
--text-muted: #6B7399;
--text-disabled: #4B526D;

--success-bg: rgba(52, 211, 153, 0.12);
--danger-bg: rgba(248, 113, 113, 0.12);
--warning-bg: rgba(251, 191, 36, 0.12);
--info-bg: rgba(96, 165, 250, 0.12);
--ai-bg: rgba(99, 102, 241, 0.12);
```

## 3.3 Semantic colours

Use green only for positive financial values or success states.

Use red only for negative financial values, failed statuses, destructive actions, or high-risk warnings.

Use amber for caution, limited confidence, stale data, moderate risk, or pending states.

Use grey for unavailable, insufficient data, disabled controls, or unknown states.

Do not overuse green/red for decorative UI. They should carry meaning.

## 3.4 Typography

Primary UI font:

```text
Inter
```

Fallbacks:

```css
font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

Financial numbers must use tabular numerals:

```css
font-variant-numeric: tabular-nums;
```

Recommended type scale:

```text
Display / Portfolio value: 32px–40px, 700
Page title: 24px–28px, 650
Section title: 18px–20px, 600
Card title: 14px–16px, 600
Body: 14px–15px, 400
Secondary text: 13px–14px, 400
Table text: 13px–14px, 400
Labels / tickers / headers: 11px–12px, uppercase, letter-spacing 0.06em–0.08em
Badges: 11px–12px, 500
```

## 3.5 Spacing

Use an 8px base grid.

```text
4px  = micro gaps
8px  = compact spacing
12px = badge/button internal gap
16px = card gaps
20px = card padding
24px = section spacing
32px = page-level spacing
```

## 3.6 Border radius

```text
Cards: 8px
Inputs: 6px
Badges: 6px
Small buttons: 6px
Large panels: 10px
Table row hover: 4px
Avatars: fully round
```

Avoid excessive pill-shaped UI except for avatars and compact status chips.

## 3.7 Borders and shadows

The MVP should mostly use borders, not heavy shadows.

```css
border: 1px solid var(--border);
```

Use very subtle shadows only for overlays, modals, dropdowns, and drawers.

## 3.8 Icons

Use one consistent icon family, preferably:

* Lucide React
* Heroicons
* Phosphor Icons

Icons should be thin, professional, and not cartoonish.

## 3.9 Motion

Use subtle transitions:

```css
transition: 150ms ease;
```

Recommended animations:

* Sidebar collapse/expand.
* Chat rail expand.
* Drawer slide-in.
* Skeleton shimmer.
* Button hover.
* Progress timeline updates.
* Toast entry/exit.

Avoid excessive animations, bouncing charts, or crypto-style glowing effects.

---

# 4. Global Application Shell

## 4.1 Layout overview

The app should use a persistent global shell:

```text
┌──────────────────────────────────────────────────────────────┐
│ Fixed Top Navbar                                             │
├───────────────┬──────────────────────────────────────────────┤
│ Left Sidebar  │ Current Page Content                         │
│               │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

On the dashboard, the page content itself contains the three-zone layout:

```text
Portfolio dashboard | Intelligence briefing | Chat rail
```

## 4.2 Top navbar

Height: 56px
Position: fixed top
Border bottom: 1px solid border colour
Shadow: none

Navbar contents:

### Left

* SCALE logo mark.
* “SCALE” wordmark.
* Optional environment badge:

  * `MVP`
  * `Demo`
  * `Local`

### Centre

The centre area should usually stay empty on the dashboard.

On pages where search is important, the centre may contain a global command/search bar:

```text
Search holdings, reports, evidence, or ask SCALE...
```

This can become a command palette later.

### Right

Right-side items, in order:

1. Data freshness indicator.
2. Model status indicator.
3. Notification bell.
4. Theme toggle.
5. User avatar / settings dropdown.

## 4.3 Data freshness indicator

Always visible.

Example states:

```text
Market data: Fresh · 12 min ago
Market data: Stale · 2h ago
Market data: Failed · Retry
Demo data
```

Visual style:

* Fresh: green chip.
* Stale: amber chip.
* Failed: red chip.
* Demo: grey/blue chip.

Clicking it opens a popover:

```text
Data Freshness

Quotes:
- Last refreshed: 10:42 AM
- Provider: yfinance
- TTL: 15 min
- Status: Fresh

News:
- Last refreshed: Yesterday, 9:12 PM
- Status: Limited

Portfolio:
- Last import: 15 Jun 2026
- Source: CSV
```

## 4.4 Model status indicator

Always visible, but subtle.

Two small dots:

```text
Groq ●    Ollama ●
```

States:

* Green: healthy.
* Red: offline.
* Amber: degraded.
* Grey: not configured.

Hover tooltip:

```text
Groq API: Online
Used for reactive chat.
```

```text
Ollama: Offline
Deep Research is disabled until the local inference server is available.
```

Do not make “Powered by local LLM” the main dashboard headline. Keep model visibility as infrastructure metadata.

## 4.5 Notification bell

The bell should represent system notifications, not fake autonomous market alerts.

Allowed MVP notifications:

* Portfolio imported.
* CSV validation failed.
* Market refresh completed.
* Market refresh failed.
* Research run completed.
* Research run failed.
* New research report available.
* Chat response validation failed.
* Ollama unavailable.
* Groq unavailable.

Avoid notifications that imply unsupported continuous monitoring.

Bad:

```text
Live AI alert: Sell ICICI now
```

Good:

```text
Research run completed: Financials exposure review
```

## 4.6 Left sidebar

Width:

```text
Expanded: 220px
Collapsed: 56px
```

Behaviour:

* Collapsible.
* Active route highlighted.
* Icons visible in collapsed state.
* Labels hidden in collapsed state.
* Tooltip on collapsed icons.
* Persistent primary CTA near bottom.

Navigation items:

```text
Dashboard
Portfolio
Chat
Deep Research
Watchlist
Research Library
Recommendations
```

Optional lower-priority links:

```text
Settings
Audit Trail
```

For MVP, Audit Trail can live inside drawers and recommendation details rather than as a primary sidebar item.

## 4.7 Sidebar CTA

Persistent CTA:

```text
▶ Start Deep Research
```

Behaviour:

* If Ollama is available: opens Deep Research launcher.
* If Ollama is offline: disabled with tooltip.
* If portfolio is empty: opens portfolio import page.
* If a research run is active: changes to “View Research Run”.

---

# 5. Dashboard Page

Route:

```text
/
```

or:

```text
/dashboard
```

## 5.1 Dashboard purpose

The dashboard is the most important page of the MVP.

It should immediately answer:

1. What is my portfolio worth?
2. What changed today?
3. What am I exposed to?
4. What does SCALE think needs attention?
5. What can I ask next?

## 5.2 Dashboard layout

Desktop layout:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Hero Stats Row                                                              │
├───────────────────────────────────────┬─────────────────────┬───────────────┤
│ Portfolio Zone                        │ Intelligence Zone   │ Chat Rail     │
│ - Performance chart                   │ - Research briefing │ - Mini chat    │
│ - Top holdings table                  │ - Risk cards        │ - Prompts      │
│ - Allocation / exposure summary       │ - Watchlist alerts  │ - Expand link  │
└───────────────────────────────────────┴─────────────────────┴───────────────┘
```

Suggested proportions:

```text
Portfolio Zone: 50%–55%
Intelligence Zone: 25%–30%
Chat Rail: 20%–25%
```

On narrower screens:

* Chat rail collapses first.
* Intelligence zone stacks below portfolio zone.
* Sidebar collapses automatically.
* Mobile support is not the primary MVP target, but the layout should not break.

## 5.3 Hero stats row

Four primary cards:

```text
Total Portfolio Value
All-Time P&L
Today's P&L
Portfolio Risk Score
```

Example:

```text
Total Portfolio Value
₹14,82,340
+₹8,230 today · +0.56%

All-Time P&L
+₹2,14,560
+16.9%

Today's P&L
+₹8,230
+0.56%

Portfolio Risk Score
Moderate
6.2 / 10
```

Card details:

* Total Portfolio Value is the visual anchor.
* P&L cards use green/red depending on sign.
* Risk Score uses a small arc gauge or segmented indicator.
* Include subtle sparklines in the first three cards if available.
* If data is mocked, show a small `Demo` badge.

## 5.4 Portfolio performance card

Large chart card.

Contents:

* Portfolio value line chart.
* Time filters:

  * `1W`
  * `1M`
  * `3M`
  * `6M`
  * `1Y`
  * `All`
* Hover tooltip:

  * Date
  * Portfolio value
  * Day change
  * Percentage change
* Optional benchmark overlay later.

Empty state:

```text
No portfolio history yet.
Import a portfolio CSV to begin tracking your portfolio over time.
```

MVP placeholder state:

```text
Portfolio history preview
Historical chart uses sample data until portfolio snapshots are available.
```

## 5.5 Compact holdings table

Show top 5–6 holdings by weight.

Columns:

```text
Ticker
Current Price
Qty
Invested
Current Value
P&L
Weight %
AI Status
```

Example AI statuses:

```text
Healthy
Watch
High concentration
Stale data
Needs analysis
Insufficient data
```

Row actions:

* Click row: open holding detail drawer.
* “Analyse” icon: pre-fill chat with holding-specific prompt.
* “View all” link: route to Portfolio page.

Visual details:

* Sticky header not needed for compact table.
* Numbers right-aligned.
* Ticker and company left-aligned.
* P&L coloured green/red.
* Weight shown with small inline bar.

## 5.6 Exposure summary

Small cards or charts below/near portfolio table:

* Asset-class allocation.
* Sector exposure.
* Top concentration.
* Cash/unallocated.
* Number of holdings.
* Watchlist count.

Preferred visualisations:

* Donut for asset class.
* Horizontal bars for sector exposure.
* Single concentration warning card if any holding exceeds threshold.

## 5.7 Intelligence briefing zone

This is the signature AI zone on the dashboard.

Title:

```text
Latest Intelligence Briefing
```

Subtitle examples:

```text
Generated from last portfolio review · 2h ago
```

or:

```text
No briefing yet · Run Deep Portfolio Review
```

Avoid:

```text
Live AI alerts
```

because the MVP does not include continuous autonomous monitoring.

### Briefing card structure

```text
✦ Latest Intelligence Briefing              2h ago   ↻

Generated from: Deep Portfolio Review
Data quality: Good
Confidence: Medium

1. High concentration in RELIANCE.NS
   22% of portfolio. Consider reviewing single-stock exposure.

2. Financials exposure near threshold
   38% of portfolio. Your configured threshold is 40%.

3. ETF basket stable
   No action required based on available data.

[View Full Research Report] [Ask Follow-up]
```

Use AI accent styling:

* Indigo border glow, but subtle.
* AI badge.
* Gradient accent line at top.
* Not too flashy.

## 5.8 Risk cards

Below or inside the intelligence zone.

Risk card types:

1. Concentration Risk.
2. Sector Exposure Risk.
3. Stale Data Warning.
4. News Impact.
5. Drawdown Watch.
6. Portfolio Drift.
7. Watchlist Opportunity.
8. Insufficient Evidence.

Each card should include:

```text
Severity
Title
Short explanation
Affected tickers
Suggested question/action
```

Example:

```text
Amber · Concentration Risk

RELIANCE.NS is 22% of your portfolio.
This increases single-stock risk.

Suggested:
“Stress-test my Reliance exposure.”
```

Click behaviour:

* Opens details drawer, or
* Pre-fills chat rail with suggested question.

## 5.9 Chat rail on dashboard

The chat rail is a docked assistant panel on the right side of the dashboard.

States:

### Collapsed

A slim vertical tab:

```text
Ask SCALE
```

or icon button.

### Docked

Width: 300–360px.

Contents:

* Header: `Ask SCALE`
* Small session indicator.
* Suggested prompt chips.
* Recent mini-message thread.
* Input box.
* Expand button.

### Expanded

Routes to full Chat page.

The chat rail should be useful but not dominate the dashboard.

Suggested prompt chips:

```text
What's my biggest risk?
Why is my portfolio down today?
Should I rebalance?
Analyse RELIANCE.NS
Run downside analysis
```

## 5.10 Dashboard empty state

If no portfolio exists:

```text
Welcome to SCALE

Import your portfolio CSV to unlock:
- Portfolio dashboard
- AI risk briefing
- Holding-level analysis
- Deep Research reports
- Evidence-backed chat

[Upload Portfolio CSV] [Use Demo Portfolio]
```

A demo portfolio option is useful for judging/demo flow.

---

# 6. Portfolio Page

Route:

```text
/portfolio
```

## 6.1 Purpose

The Portfolio page is the full holdings dashboard.

It should feel familiar to users of brokerage or portfolio-tracking apps.

## 6.2 Toolbar

Left:

* Search input:

  ```text
  Filter by ticker or company...
  ```

* Filter chips:

  ```text
  All
  Equity
  ETF
  Mutual Fund
  Debt
  Gold
  Other
  ```

* Optional sector filter.

Right:

* Upload New CSV.
* Export CSV.
* Refresh Prices.
* Columns/settings icon.

## 6.3 Portfolio summary strip

At top:

```text
Current Value
Invested Amount
Unrealised P&L
Today's P&L
Number of Holdings
Last Updated
```

## 6.4 Holdings table

Full table columns:

```text
Ticker
Name
Exchange
Sector
Asset Class
Quantity
Average Buy Price
Current Price
Invested Amount
Current Value
Unrealised P&L
P&L %
Day Change
Weight %
AI Status
Actions
```

Column behaviour:

* Sortable columns.
* Sticky header.
* Right-align numerical columns.
* Use tabular numerals.
* Pinned summary row at bottom.
* Optional horizontal scroll for smaller screens.
* Weight column shows text + inline bar.
* AI status column uses compact status badge.

Actions:

```text
Analyse
Add to Watchlist
Open Details
```

Row click opens holding detail drawer.

## 6.5 Holding detail drawer

The drawer opens from the right.

Sections:

```text
Header
- Company name
- Ticker
- Exchange
- Current price
- Day change
- Data freshness

Your Position
- Quantity
- Average buy price
- Invested amount
- Current value
- Unrealised P&L
- Portfolio weight

AI View
- Current stance
- Confidence
- Data quality
- Last analysed

Risk First
- Bear case
- Key risks
- Concentration impact

Thesis / Notes
- User notes
- Prior research summary
- Last recommendation

Evidence
- Market quote
- News sources
- Research artefacts

Ask SCALE
- Should I add more?
- What is the bear case?
- Compare with sector peers
- What would change the recommendation?
```

## 6.6 Allocation charts

Below the table:

* Donut: by asset class.
* Donut: by sector.
* Bar chart: top holdings by weight.
* Optional: risk contribution approximation.

## 6.7 Portfolio page empty state

```text
No holdings yet.

Upload a CSV with your holdings to generate a portfolio dashboard and AI analysis.

[Upload CSV] [Download Sample CSV] [Use Demo Portfolio]
```

---

# 7. Portfolio Import Page

Route:

```text
/portfolio/import
```

or modal from Portfolio page.

## 7.1 Purpose

The import flow should visibly demonstrate data integrity.

The user should see that bad data is rejected before entering the portfolio.

## 7.2 Import steps

Stepper:

```text
1. Upload CSV
2. Validate Schema
3. Resolve Tickers
4. Preview Holdings
5. Confirm Import
```

## 7.3 Accepted CSV schema

MVP CSV columns:

```csv
ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date
```

Show this clearly in the UI.

Provide:

* Download sample CSV.
* View schema requirements.
* Drag-and-drop upload.

## 7.4 Validation results

After upload, show:

```text
Valid rows: 12
Warnings: 2
Rejected rows: 1
```

Validation table columns:

```text
Row
Ticker
Issue Type
Message
Suggested Fix
Status
```

Examples:

```text
TATA
Ambiguous ticker
Choose NSE or BSE.
Needs review
```

```text
INFY
Valid
Resolved as INFY.NS.
Ready
```

Invalid rows must not be imported.

## 7.5 Preview holdings

Before final import, show derived preview:

```text
Ticker
Exchange
Canonical Ticker
Asset Class
Quantity
Average Buy Price
Currency
Purchase Date
```

Do not show current price, current value, P&L, or allocation as CSV-imported values. Those should be derived from market data.

## 7.6 Import success state

```text
Portfolio imported successfully.

12 holdings imported.
2 rows skipped.
Market data refresh started.

[Go to Dashboard] [View Portfolio]
```

---

# 8. Chat System

The chat system has two representations:

1. Docked chat rail on the dashboard.
2. Full Chat page for serious sessions and history.

## 8.1 Full Chat Page

Route:

```text
/chat
```

## 8.2 Layout

Desktop layout:

```text
┌────────────────────┬─────────────────────────────────────────────┐
│ Chat Sessions      │ Active Chat Thread                          │
│                    │                                             │
│ Previous chats     │ Messages                                    │
│ New chat           │ Cards                                       │
│ Filters            │ Sticky input                                │
└────────────────────┴─────────────────────────────────────────────┘
```

Left chat session sidebar:

* New Chat button.
* Search chats.
* Previous sessions grouped by date:

  * Today
  * Yesterday
  * Previous 7 days
  * Older
* Session title generated from first meaningful query.
* Session metadata:

  * portfolio-aware
  * recommendation produced
  * research triggered
  * evidence available

Main chat area:

* Max width around 760–860px for readability.
* Message thread.
* Sticky input.
* Suggested prompt chips on empty state.
* Cards rendered inline below assistant messages.

## 8.3 Chat empty state

```text
Ask SCALE about your portfolio

Suggested:
[What's my biggest risk?]
[Should I rebalance?]
[Compare TCS vs INFY]
[News on RELIANCE.NS]
[Run downside analysis]
[Explain my sector exposure]
```

## 8.4 Chat input

Input features:

* Multi-line input.
* Send button.
* Keyboard submit:

  * Enter to send.
  * Shift+Enter for newline.
* Attachment/artefact reference button later.
* Query mode hint, not forced mode selection.

Placeholder:

```text
Ask about your portfolio, holdings, risks, news, or research...
```

## 8.5 Query-aware response rendering

The frontend should render based on backend-provided `response_type`.

Recommended response types:

```ts
type ResponseType =
  | "plain_chat"
  | "recommendation"
  | "news_digest"
  | "comparison"
  | "portfolio_snapshot"
  | "technical_analysis"
  | "fundamental_analysis"
  | "quant_analysis"
  | "research_run_status"
  | "insufficient_data"
  | "error";
```

The assistant response should generally have:

1. A conversational summary bubble.
2. Optional structured card(s).
3. Evidence / reasoning / assumptions controls where relevant.

Example:

```text
Assistant bubble:
“Given your current exposure and the available evidence, I would not add aggressively right now.”

Structured card:
RecommendationCard
```

This keeps chat natural without sacrificing financial structure.

---

# 9. Chat Response Cards

## 9.1 Plain chat bubble

Used for:

* Definitions.
* Educational explanations.
* General finance questions.
* Clarifications.
* Non-portfolio questions.

Example:

```text
Beta measures how sensitive a stock is to market movements. A beta above 1 means the stock usually moves more than the market, while a beta below 1 means it usually moves less.
```

No heavy card required unless evidence-backed financial claims are made.

## 9.2 Recommendation card

Used for:

* “Should I buy/sell/add/reduce?”
* “Is this a good time to enter?”
* “Should I rebalance?”
* “What should I do with this holding?”

Required sections:

```text
Recommendation
Confidence
Data Quality
Downside First
Portfolio Impact
Upside Case
No-Action Case
Assumptions
Evidence
Reasoning Trace
Decision Tracking
```

Example layout:

```text
RECOMMENDATION                      Advisory only

Suggested action: Hold / Watch
Confidence: Medium
Data quality: Limited

DOWNSIDE FIRST
- Key downside scenario
- Drawdown or risk framing
- Main risks

PORTFOLIO IMPACT
- Current exposure
- Concentration effect
- Risk tolerance fit

UPSIDE CASE
- Why the idea may still be attractive
- What could improve the thesis

NO-ACTION CASE
- What happens if the user does nothing
- Why waiting may or may not be sensible

ASSUMPTIONS
- Market data fetched at...
- News coverage limited to...
- Valuation data unavailable...

EVIDENCE
[quote_001] [news_004] [portfolio_002]

ACTIONS
[Save] [Needs More Research] [Ask Follow-up]
```

Do not use trade-execution buttons.

Bad:

```text
Buy Now
Sell Now
Execute
```

Good:

```text
Save analysis
Ask follow-up
Run deeper research
Mark as accepted
Mark as rejected
```

## 9.3 Confidence display

Use confidence tiers first.

Allowed tiers:

```text
High
Medium
Low
Insufficient
```

Visual mapping:

```text
High: green
Medium: amber
Low: red
Insufficient: grey
```

Avoid presenting fake precision as the primary UI.

Bad:

```text
Confidence: 62%
```

Better:

```text
Confidence: Medium
Why not high: news coverage is limited and valuation data is stale.
```

If a numerical model score exists, it can be shown as secondary metadata:

```text
Internal estimate: 62%
```

But only if the backend actually produces it.

## 9.4 Data quality badge

Every recommendation card must show data quality.

Allowed states:

```text
Good
Limited
Stale
Critical Failure
Demo
```

Examples:

```text
Data Quality: Good
Data Quality: Stale — prices last refreshed 3h ago
Data Quality: Limited — no recent news found
Data Quality: Critical Failure — unable to fetch market quote
```

If data quality is critical failure, the card should not show a confident recommendation. It should render as insufficient data.

## 9.5 News digest card

Used for:

* “News on Infosys”
* “What happened to ICICI today?”
* “Summarise recent news affecting my portfolio”

Structure:

```text
NEWS DIGEST

Ticker / Scope
Data freshness
Sources retrieved

Headline 1
- Source
- Published time
- Short summary
- Possible portfolio relevance

Headline 2
...

Portfolio relevance
- Affected holdings
- Risk level
- What to watch

Evidence
[source chips]
```

Do not overstate market impact unless evidence supports it.

Use phrases like:

```text
Potential relevance
May affect
Worth monitoring
Insufficient evidence to quantify impact
```

## 9.6 Comparison card

Used for:

* “Compare TCS vs INFY”
* “Which ETF is better?”
* “Compare my two largest holdings”

Structure:

```text
COMPARISON

Metric               TCS              INFY
Price change          ...              ...
Portfolio weight      ...              ...
P&L                   ...              ...
Valuation             ...              ...
Recent news           ...              ...
Risk                  ...              ...
Data quality          ...              ...

Summary
- Where A looks stronger
- Where B looks stronger
- What data is missing

Recommendation / Conclusion
- Optional
- Must include confidence if advisory
```

## 9.7 Portfolio snapshot card

Used for:

* “How is my portfolio doing?”
* “What is my biggest risk?”
* “Summarise my portfolio”
* “Am I diversified?”

Structure:

```text
PORTFOLIO SNAPSHOT

Total value
Today's P&L
All-time P&L
Top holdings
Sector exposure
Asset allocation
Largest risk
Data freshness

Risk observations
- Concentration
- Sector exposure
- Stale data
- Under-diversification

Suggested next questions
```

## 9.8 Technical analysis card

Used for:

* “Do technical analysis on RELIANCE”
* “Show trend for HDFC Bank”
* “Is this stock technically weak?”

Structure:

```text
TECHNICAL ANALYSIS

Ticker
Timeframe
Data freshness

Trend
Momentum
Support / resistance
Volatility
Volume signal
Risk level

Caveats
- Technical analysis is short-term and probabilistic.
- Indicators are derived mechanically.
- Not sufficient alone for investment decisions.

Evidence / calculated indicators
```

MVP note:

Technical indicators may be placeholders initially, but the UI should exist. Mark placeholder/demo values clearly.

## 9.9 Fundamental analysis card

Used for:

* “Analyse fundamentals of TCS”
* “Is this company financially strong?”
* “Give me a fundamental view”

Structure:

```text
FUNDAMENTAL ANALYSIS

Ticker
Data quality
Latest available financial data

Business summary
Revenue / growth notes
Margins
Debt / leverage
Valuation
Risks
Bear case
Bull case
What data is missing

Conclusion
Confidence
Evidence
```

## 9.10 Quant analysis card

Used for:

* “Quant analysis of my portfolio”
* “Show volatility and correlation”
* “Risk-adjusted view”
* “Calculate portfolio beta”

Structure:

```text
QUANT ANALYSIS

Scope
Data window
Data freshness

Metrics
- Volatility
- Beta
- Max drawdown
- Correlation approximation
- Concentration score
- Sharpe-like proxy if feasible

Interpretation
Limitations
Evidence / calculations
```

Important:

The UI may exist before all metrics are implemented. Unavailable metrics should show:

```text
Not available in MVP
```

not fake values.

## 9.11 Insufficient data card

Used when the system cannot safely answer.

Structure:

```text
INSUFFICIENT DATA

I cannot form a reliable view because:

Missing data
- ...
Stale data
- ...
Unresolved ticker
- ...
Provider failure
- ...

What you can do
[Refresh Market Data]
[Upload Portfolio CSV]
[Run Deep Research]
[Ask a narrower question]
```

This is not an error state. It is a valid financial output.

## 9.12 Research run status card

Used when the user triggers or asks about research.

Structure:

```text
DEEP RESEARCH RUN

Status: Running
Scope: Full portfolio
Current step: Analysing INFY.NS
Progress: 7 / 15 holdings

Timeline
✓ Load portfolio
✓ Fetch market data
✓ Retrieve news
→ Analyse INFY.NS
○ Analyse RELIANCE.NS
○ Synthesise portfolio view

[View Full Run] [Cancel]
```

---

# 10. Evidence, Reasoning, and Assumptions

Every serious AI output should expose three controls:

```text
Evidence
Reasoning Trace
Assumptions
```

These can appear as tabs, accordions, or drawer buttons.

## 10.1 Evidence drawer

The evidence drawer is more important than a generic “sources” list.

It should show exactly what the agent used.

Drawer sections:

```text
Evidence Summary
Evidence Items
Claims Using This Evidence
Raw Data / Excerpt
Metadata
```

Evidence item examples:

```text
quote_001
Type: Market quote
Ticker: INFY.NS
Provider: yfinance
Fetched at: 10:42 AM
Freshness: Fresh
Used in claims:
- “INFY is down today”
- “Current portfolio weight is 8.2%”
```

```text
news_004
Type: News
Ticker: ICICIBANK.NS
Source: yfinance news
Published at: ...
Retrieved at: ...
Excerpt: ...
Used in claims:
- “Recent regulatory news exists”
```

```text
portfolio_002
Type: Portfolio holding
Ticker: RELIANCE.NS
Source: User CSV import
Imported at: ...
Used in claims:
- “Reliance is 22% of portfolio”
```

## 10.2 Reasoning trace drawer

Shows graph steps, not hidden chain-of-thought.

Example:

```text
Reasoning Trace

✓ Initialise run
✓ Load portfolio context
✓ Identify relevant tickers
✓ Fetch market data
✓ Semantic retrieval
✓ Build evidence pack
✓ Validate data quality
✓ LLM reasoning
✓ Parse structured output
✓ Compliance boundary check
✓ Persist response
```

Each step should include:

```text
Status
Timestamp
Duration
Input/output summary
Warnings
```

Do not expose private hidden chain-of-thought. Show structured trace of system operations.

## 10.3 Assumptions drawer

Shows assumptions explicitly.

Example:

```text
Assumptions

- Current price data is treated as fresh because it was fetched 8 minutes ago.
- Sector exposure is calculated from available sector labels only.
- No tax impact is modelled in the MVP.
- News coverage may be incomplete.
- Compliance engine is not implemented in MVP.
```

## 10.4 Claims classification

Where practical, classify claims as:

```text
Data-supported
Inference
Assumption
```

Visual treatment:

* Data-supported: source chip required.
* Inference: source chip + inference label.
* Assumption: assumption label.
* Unsupported: should not be rendered as a factual claim.

---

# 11. Deep Research Page

Route:

```text
/deep-research
```

## 11.1 Purpose

Deep Research is one of the most novel MVP pages.

It shows the user-triggered, longer-running research mode.

This is not autonomous scheduled monitoring. It is explicitly started by the user.

## 11.2 Page header

```text
Deep Research

Run portfolio-level or ticker-level research using a local open-source model.
Research outputs are saved as reusable reports and can be cited in future chat responses.
```

Show Ollama status near the header:

```text
Ollama: Online
```

or:

```text
Ollama: Offline — Deep Research unavailable
```

## 11.3 Research launcher

Launcher card:

```text
✦ Deep Research Engine

Analyse your holdings, watchlist, news, prior notes, and portfolio exposure.
The result is saved as a Markdown research report.

Choose scope:
[Full Portfolio]
[Watchlist]
[Specific Tickers]
[Single Holding]

Research type:
[Deep Portfolio Review]
[Watchlist Analysis]
[Concentration Risk Review]
[Downside Stress Test]
[News Impact Review]
[Fundamental Review]

[Start Research]
```

## 11.4 Scope selector

Specific ticker selector:

* Searchable multi-select.
* Preloaded with holdings and watchlist.
* Ticker chips.
* Validation for unknown symbols.

## 11.5 Active research run

Default view: friendly progress timeline.

```text
Deep Portfolio Review

Status: Running
Scope: Full portfolio
Started: 10:31 AM
Current step: Analysing TATAMOTORS.NS
Progress: 7 / 15 holdings

Progress
✓ Created research run
✓ Loaded portfolio
✓ Fetched market data
✓ Retrieved news and notes
✓ Analysed INFY.NS
✓ Analysed TCS.NS
→ Analysing TATAMOTORS.NS
○ Synthesising portfolio view
○ Creating Markdown report
○ Saving artefact
```

Controls:

```text
[View Advanced Logs]
[Cancel Run]
```

## 11.6 Advanced logs

Hidden by default.

Used for technical visibility.

```text
[10:31:02] initialise_research_run success
[10:31:04] load_portfolio_context success: 15 holdings
[10:31:11] fetch_market_data INFY.NS success
[10:31:22] retrieve_news INFY.NS 8 chunks
[10:32:01] analyse_ticker INFY.NS completed
```

This should feel like a serious execution trace, not a flashy fake terminal.

## 11.7 Past research runs

Card grid or table.

Each card:

```text
Deep Portfolio Review
15 holdings · Completed
Generated: 18 Jun 2026
Confidence: 4 high · 8 medium · 3 low
Data quality: Good

Summary:
Financials exposure is elevated; no urgent action recommended.

[View Report] [Ask About This] [Open Evidence]
```

## 11.8 Markdown report viewer

Full-screen report view.

Layout:

```text
┌───────────────┬─────────────────────────────────────────────┐
│ Table of      │ Markdown report                             │
│ contents      │                                             │
└───────────────┴─────────────────────────────────────────────┘
```

Report sections:

```text
Executive Summary
Portfolio Risk Overview
Holding-Level Findings
Watchlist Findings
Concentration Risks
Downside Scenarios
Suggested Actions
No-Action Case
Assumptions
Evidence
Data Quality Caveats
```

Actions:

```text
Ask SCALE about this report
Save
Export Markdown
Copy summary
```

---

# 12. Research Library

Route:

```text
/research-library
```

Preferred name:

```text
Research Library
```

Alternative:

```text
Knowledge Base
```

“Research Library” is more investor-friendly.

## 12.1 Purpose

The Research Library shows what SCALE knows and can retrieve from.

It makes retrieval visible.

## 12.2 Content types

The library should contain:

* User-uploaded notes.
* Markdown research reports.
* Agent-generated artefacts.
* Prior analyses.
* Imported thesis documents.
* News summaries if stored.
* Watchlist notes.

## 12.3 Upload section

Accepted MVP file types:

```text
.md
.txt
```

Later:

```text
.pdf
.csv
.docx
.html
```

Upload card:

```text
Upload research notes

Add Markdown or text files that SCALE can use as context in future analysis.

[Upload File]
```

## 12.4 Artefact grid

Each artefact card:

```text
Title
Type badge: User Note / AI Generated / Research Report
Created date
Linked tickers
Preview snippet
Data source
Embedded status

[Open] [Ask About This] [Delete]
```

## 12.5 Artefact detail page

Sections:

```text
Metadata
Content preview
Linked tickers
Generated by run
Evidence links
Chunks / retrieval status
Ask SCALE about this artefact
```

---

# 13. Watchlist Page

Route:

```text
/watchlist
```

## 13.1 Purpose

The Watchlist page is a research queue.

It tracks assets the user may want to analyse but does not own.

## 13.2 Add ticker row

Top row:

```text
Add ticker...
Exchange...
Reason...
[Add]
```

## 13.3 Watchlist table

Columns:

```text
Ticker
Name
Current Price
Day Change
52W Range
Reason Added
Last AI Rating
Data Quality
Last Analysed
Alert Status
Actions
```

Actions:

```text
Quick Analyse
Compare
Run Deep Research
Remove
```

## 13.4 In-cell 52W range bar

Visual:

```text
Low ─────●──── High
```

## 13.5 Watchlist empty state

```text
No watchlist items yet.

Add stocks, ETFs, or funds you want SCALE to track for future analysis.

[Add Ticker] [Import Sample Watchlist]
```

---

# 14. Recommendations Page

Route:

```text
/recommendations
```

## 14.1 Purpose

Recommendations should not disappear into chat history.

This page turns advisory outputs into an auditable decision history.

## 14.2 Recommendation list

Table or cards.

Columns:

```text
Date
Scope
Ticker
Suggested Action
Confidence
Data Quality
User Decision
Source
Status
```

Example rows:

```text
18 Jun 2026
Portfolio
-
Reduce concentration
Medium
Good
Saved for later
Deep Research
```

```text
17 Jun 2026
INFY.NS
Hold
High
Good
Accepted analysis
Chat
```

## 14.3 Recommendation detail page

Sections:

```text
Summary
Suggested action
Confidence
Data quality
Downside first
Portfolio impact
Upside case
No-action case
Assumptions
Evidence
Reasoning trace
User decision
Audit metadata
```

Decision buttons:

```text
Accept Analysis
Reject
Save for Later
Needs More Research
```

These are not trade execution actions.

Show advisory boundary:

```text
SCALE does not execute trades. This is an advisory recommendation only.
```

---

# 15. Settings Page

Route:

```text
/settings
```

MVP settings can be simple but useful.

Sections:

## 15.1 User profile

Fields:

```text
Name
Base currency
Investment horizon
Risk tolerance
Preferred markets
```

## 15.2 Risk thresholds

Fields:

```text
Maximum single-stock exposure
Maximum sector exposure
Minimum cash buffer
High-risk asset limit
```

Example:

```text
Single holding threshold: 20%
Sector threshold: 35%
```

These thresholds can power risk cards.

## 15.3 Model configuration status

Read-only or partially configurable:

```text
Reactive chat provider: Groq
Deep Research provider: Ollama
Groq status
Ollama status
```

## 15.4 Data settings

```text
Market data provider
Quote TTL
Manual refresh
Last refresh time
```

## 15.5 Demo mode

Toggle or badge:

```text
Use demo portfolio
Reset demo data
```

---

# 16. Common UI Components

## 16.1 Buttons

Button types:

```text
Primary
Secondary
Ghost
Danger
Disabled
Loading
Icon-only
```

Examples:

```text
Run Deep Research
Import CSV
Refresh Market Data
Cancel Run
Save Analysis
Ask Follow-up
```

Loading button:

```text
Refreshing...
```

Disabled button with tooltip:

```text
Start Deep Research
Tooltip: Ollama is offline.
```

## 16.2 Badges

Badge types:

```text
Fresh
Stale
Good
Limited
Critical
Demo
High Confidence
Medium Confidence
Low Confidence
Insufficient
AI Generated
Advisory Only
No Execution
```

## 16.3 Cards

Card types:

```text
MetricCard
PortfolioChartCard
HoldingSummaryCard
RiskCard
BriefingCard
RecommendationCard
NewsDigestCard
ComparisonCard
ResearchRunCard
ArtefactCard
EvidenceCard
EmptyStateCard
```

## 16.4 Tables

Required features:

* Sticky header.
* Sortable columns.
* Search/filter.
* Row hover.
* Row actions.
* Empty state.
* Loading skeleton rows.
* Error row.
* Pinned summary row where relevant.
* Right-aligned numeric columns.
* Tabular numerals.

## 16.5 Drawers

Drawer types:

```text
HoldingDetailDrawer
EvidenceDrawer
ReasoningTraceDrawer
AssumptionsDrawer
ResearchRunDrawer
```

Drawer behaviour:

* Slide from right.
* Esc closes drawer.
* Click outside closes drawer unless unsaved work exists.
* Can be stacked carefully, but avoid more than two layers.

## 16.6 Modals

Use modals for:

* Confirm delete.
* Confirm cancel research run.
* Clear portfolio data.
* Reset demo portfolio.
* Upload CSV preview confirmation.

Do not use modals for simple detail viewing; use drawers.

## 16.7 Toasts

Top-right toasts.

Types:

```text
Success
Error
Info
Warning
```

Examples:

```text
Portfolio uploaded successfully.
Deep Research run started.
Market data refresh failed.
Ollama is offline.
Recommendation saved.
```

Auto-dismiss: 4 seconds, except critical errors.

## 16.8 Loading states

Use skeletons, not generic spinners, wherever possible.

Skeletons for:

* Metric cards.
* Chart cards.
* Table rows.
* Chat cards.
* Research artefact cards.
* Evidence drawer.

## 16.9 Empty states

Every page needs a designed empty state.

Examples:

Portfolio:

```text
No holdings yet. Upload a CSV to begin.
```

Chat:

```text
Ask SCALE your first portfolio question.
```

Deep Research:

```text
No research runs yet. Start a Deep Portfolio Review.
```

Research Library:

```text
No artefacts yet. Upload notes or run Deep Research.
```

Watchlist:

```text
No watchlist items yet. Add a ticker to track.
```

## 16.10 Error states

Errors must be specific.

Bad:

```text
Something went wrong.
```

Good:

```text
Couldn't fetch RELIANCE.NS price. yfinance returned an empty response.
```

```text
Groq API is unreachable. Reactive chat is temporarily unavailable.
```

```text
Ollama is offline. Deep Research cannot start until the local inference server is running.
```

## 16.11 Tooltips

Use tooltips for jargon:

```text
Portfolio Beta
Drawdown
Confidence
Data Quality
Evidence Pack
Ollama
Groq
Sector Exposure
Unrealised P&L
```

Tooltip style:

* Short.
* Plain language.
* No paragraphs.

Example:

```text
Drawdown: The fall from a previous high to a later low.
```

## 16.12 Keyboard shortcuts

MVP shortcuts:

```text
/        Focus chat input
R        Refresh intelligence briefing
Esc      Close modal/drawer
Cmd/Ctrl + K  Open command palette
?        Show keyboard shortcuts
```

## 16.13 Dynamic tab title

Examples:

```text
SCALE Finance
↑ ₹8,230 | SCALE
Research Running | SCALE
Ollama Offline | SCALE
```

---

# 17. Data Freshness and Honesty Rules

The UI must be honest about what data is fresh, stale, demo, missing, or placeholder.

## 17.1 Demo data

If demo data is used, show a `Demo` badge.

Example:

```text
Demo Portfolio
Sample market data
```

## 17.2 Placeholder features

If the UI exists but backend is incomplete, mark clearly:

```text
Preview feature
Backend not connected
Coming soon
Not available in MVP
```

Do not silently display fake values as if real.

## 17.3 Stale data

If data is stale, show:

```text
Stale · Last refreshed 2h ago
```

If stale data is used in an answer, the chat card must show:

```text
Data Quality: Stale
```

## 17.4 Provider failure

If provider failure occurs:

```text
Market data unavailable
Provider returned empty response
Retry
```

If critical data is missing, render insufficient data rather than a forced recommendation.

---

# 18. No-Execution Boundary

SCALE must never visually imply that it can place trades in the MVP.

Do not use:

```text
Buy Now
Sell Now
Execute
Place Order
Trade
Confirm Trade
```

Use:

```text
Suggested action
Save analysis
Accept analysis
Reject analysis
Needs more research
Ask follow-up
Mark decision
```

Global advisory note, shown subtly in recommendation pages/cards:

```text
SCALE provides research and advisory analysis only. No trades are executed by this system.
```

---

# 19. Suggested Frontend Routes

Recommended route structure:

```text
/dashboard
/portfolio
/portfolio/import
/portfolio/:ticker
/chat
/chat/:sessionId
/deep-research
/deep-research/:runId
/research-library
/research-library/:artifactId
/watchlist
/recommendations
/recommendations/:recommendationId
/settings
```

Dashboard may also be `/`.

---

# 20. Suggested Component Organisation

Recommended React structure:

```text
frontend/
  src/
    app/
      App.tsx
      router.tsx
      providers.tsx

    layouts/
      AppShell.tsx
      DashboardLayout.tsx
      ChatLayout.tsx

    components/
      ui/
        Button.tsx
        Badge.tsx
        Card.tsx
        Table.tsx
        Drawer.tsx
        Modal.tsx
        Tooltip.tsx
        Toast.tsx
        Skeleton.tsx
        Tabs.tsx
        Progress.tsx
        EmptyState.tsx
        ErrorState.tsx

      charts/
        PortfolioLineChart.tsx
        AllocationDonut.tsx
        SectorExposureBars.tsx
        WeightBar.tsx
        RiskGauge.tsx
        Sparkline.tsx

      shell/
        TopNavbar.tsx
        Sidebar.tsx
        ModelStatusIndicator.tsx
        DataFreshnessIndicator.tsx
        NotificationBell.tsx
        ThemeToggle.tsx

    features/
      dashboard/
        DashboardPage.tsx
        HeroStatsRow.tsx
        IntelligenceBriefing.tsx
        RiskCards.tsx
        DashboardChatRail.tsx

      portfolio/
        PortfolioPage.tsx
        HoldingsTable.tsx
        HoldingDetailDrawer.tsx
        PortfolioImportPage.tsx
        ImportValidationTable.tsx

      chat/
        ChatPage.tsx
        ChatSessionSidebar.tsx
        ChatThread.tsx
        ChatInput.tsx
        AssistantMessage.tsx
        ResponseRenderer.tsx
        cards/
          RecommendationCard.tsx
          NewsDigestCard.tsx
          ComparisonCard.tsx
          PortfolioSnapshotCard.tsx
          TechnicalAnalysisCard.tsx
          FundamentalAnalysisCard.tsx
          QuantAnalysisCard.tsx
          InsufficientDataCard.tsx
          ResearchRunStatusCard.tsx

      evidence/
        EvidenceDrawer.tsx
        ReasoningTraceDrawer.tsx
        AssumptionsDrawer.tsx
        EvidenceChip.tsx

      research/
        DeepResearchPage.tsx
        ResearchLauncher.tsx
        ResearchRunTimeline.tsx
        AdvancedRunLogs.tsx
        ResearchRunCard.tsx
        MarkdownReportViewer.tsx

      library/
        ResearchLibraryPage.tsx
        ArtifactCard.tsx
        ArtifactDetailPage.tsx
        UploadArtifactCard.tsx

      watchlist/
        WatchlistPage.tsx
        WatchlistTable.tsx
        AddTickerRow.tsx

      recommendations/
        RecommendationsPage.tsx
        RecommendationDetailPage.tsx
        DecisionButtons.tsx

      settings/
        SettingsPage.tsx

    lib/
      api.ts
      types.ts
      formatters.ts
      constants.ts
      mockData.ts

    styles/
      globals.css
      tokens.css
```

---

# 21. TypeScript Data Contracts for Frontend

These are frontend-facing shapes, not necessarily backend database schemas.

## 21.1 Portfolio summary

```ts
type PortfolioSummary = {
  totalValue: number;
  investedAmount: number;
  allTimePnl: number;
  allTimePnlPct: number;
  todayPnl: number;
  todayPnlPct: number;
  currency: "INR" | "USD" | string;
  riskScore: {
    label: "Low" | "Moderate" | "High" | "Unknown";
    value: number | null;
    max: number;
  };
  dataFreshness: DataFreshness;
};
```

## 21.2 Data freshness

```ts
type DataFreshness = {
  status: "fresh" | "stale" | "failed" | "demo" | "unknown";
  lastUpdatedAt: string | null;
  provider?: string;
  message?: string;
};
```

## 21.3 Holding

```ts
type Holding = {
  id: string;
  ticker: string;
  canonicalTicker: string;
  exchange: string;
  name: string;
  sector?: string;
  assetClass: "equity" | "etf" | "mf" | "bond" | "gold" | "other";
  quantity: number;
  avgBuyPrice: number;
  currentPrice: number | null;
  investedAmount: number;
  currentValue: number | null;
  unrealisedPnl: number | null;
  unrealisedPnlPct: number | null;
  dayChange: number | null;
  dayChangePct: number | null;
  weightPct: number | null;
  aiStatus:
    | "healthy"
    | "watch"
    | "high_concentration"
    | "stale_data"
    | "needs_analysis"
    | "insufficient_data";
  dataFreshness: DataFreshness;
};
```

## 21.4 Chat response

```ts
type ChatResponse = {
  id: string;
  sessionId: string;
  role: "assistant";
  message: string;
  responseType:
    | "plain_chat"
    | "recommendation"
    | "news_digest"
    | "comparison"
    | "portfolio_snapshot"
    | "technical_analysis"
    | "fundamental_analysis"
    | "quant_analysis"
    | "research_run_status"
    | "insufficient_data"
    | "error";
  cards?: ResponseCard[];
  evidenceIds?: string[];
  reasoningTraceId?: string;
  createdAt: string;
};
```

## 21.5 Recommendation card data

```ts
type RecommendationCardData = {
  action:
    | "buy"
    | "hold"
    | "sell"
    | "reduce"
    | "add"
    | "watch"
    | "no_action"
    | "insufficient_data"
    | "investigate";
  confidence: {
    tier: "high" | "medium" | "low" | "insufficient";
    explanation?: string;
    internalScore?: number;
  };
  dataQuality: "good" | "limited" | "stale" | "critical_failure" | "demo";
  summary: string;
  downsideFirst: {
    bearCase: string;
    expectedDrawdown?: string;
    keyRisks: string[];
  };
  portfolioImpact: string;
  upsideCase?: string;
  noActionCase: string;
  assumptions: string[];
  evidenceIds: string[];
  reasoningTraceId?: string;
  advisoryOnly: true;
};
```

---

# 22. MVP Implementation Priority

## Phase 1 — Visual foundation

Build first:

1. App shell.
2. Dark design tokens.
3. Sidebar.
4. Top navbar.
5. Dashboard layout.
6. Hero stats.
7. Portfolio chart placeholder.
8. Compact holdings table.
9. Intelligence briefing card.
10. Docked chat rail.
11. Common cards, badges, buttons, skeletons.

Use demo data.

## Phase 2 — Portfolio functionality

Build:

1. Portfolio page.
2. Holdings table.
3. Holding detail drawer.
4. CSV import page.
5. Validation UI.
6. Data freshness indicators.
7. Empty/error states.

## Phase 3 — Chat experience

Build:

1. Full Chat page.
2. Chat sessions sidebar.
3. Conversational messages.
4. Response renderer.
5. Recommendation card.
6. News digest card.
7. Comparison card.
8. Portfolio snapshot card.
9. Insufficient data card.
10. Evidence drawer.
11. Reasoning trace drawer.
12. Assumptions drawer.

## Phase 4 — Deep Research and artefacts

Build:

1. Deep Research page.
2. Research launcher.
3. Research run timeline.
4. Advanced logs panel.
5. Past research artefact cards.
6. Markdown report viewer.
7. Research Library page.
8. Artefact detail page.

## Phase 5 — Recommendations and polish

Build:

1. Recommendations page.
2. Recommendation detail page.
3. Decision buttons.
4. More robust loading/error states.
5. Toasts.
6. Keyboard shortcuts.
7. Settings page.
8. Final demo polish.

---

# 23. MVP Demo Script Supported by UI

The frontend should support this demo flow:

1. User lands on dashboard.
2. Dashboard shows demo/real portfolio summary.
3. User sees portfolio value, P&L, risk score, top holdings.
4. User sees latest intelligence briefing.
5. User clicks a risk card.
6. Chat rail pre-fills a question.
7. User asks: “What is my biggest portfolio risk?”
8. Assistant responds conversationally and shows Portfolio Snapshot card.
9. User asks: “Should I add more INFY?”
10. Assistant shows Recommendation card with:

    * confidence
    * data quality
    * downside first
    * portfolio impact
    * no-action case
    * evidence
11. User opens Evidence drawer.
12. User opens Reasoning Trace drawer.
13. User starts Deep Portfolio Review.
14. Deep Research page shows progress timeline.
15. User opens generated Markdown report.
16. Report appears in Research Library.
17. Recommendation appears in Recommendations page.
18. User marks recommendation as “Saved for later”.
19. No trade is executed.

This flow should be possible even if some data is mocked, as long as mock/demo status is visible.

---

# 24. Long-Term Design Ideas

These should not be hard requirements for the MVP, but the UI should not block them.

## 24.1 Autonomous monitoring

Long-term, SCALE may support scheduled monitoring.

Possible future UI:

```text
Monitoring Rules
- Notify me if sector exposure crosses 40%
- Notify me if a holding drops more than 5%
- Notify me if new negative news appears
```

For MVP, do not imply this is already active.

## 24.2 Broker integration

Future broker integration should be a separate execution layer.

Future UI may include:

```text
Prepare trade ticket
Send to broker
Requires explicit approval
```

MVP should not include trade execution UI.

## 24.3 Compliance engine

Future UI may show:

```text
Compliance check passed
Suitability check
Tax impact
Regulatory constraints
```

MVP should show:

```text
Compliance engine not implemented in MVP
Execution allowed: false
```

## 24.4 Mobile app

The MVP is desktop-dashboard-first.

Mobile can later support:

* Portfolio summary.
* Alerts.
* Chat.
* Research report reading.

Complex tables and research workflows should remain desktop-first.

## 24.5 Advanced portfolio analytics

Future analytics:

* Correlation matrix.
* Factor exposure.
* Efficient frontier.
* Tax-aware rebalancing.
* Scenario simulation.
* Stress-testing by macro events.
* Portfolio beta.
* Value at Risk.
* Drawdown simulation.

MVP may show UI slots for some of these, but must mark unimplemented metrics honestly.

## 24.6 Collaboration

Future:

* Share report.
* Export PDF.
* Advisor review mode.
* Comments on recommendations.
* Decision journal.

Not MVP.

## 24.7 Command palette

Future command palette:

```text
Cmd/Ctrl + K
```

Actions:

* Search ticker.
* Ask chat.
* Open report.
* Start research.
* Refresh data.
* Upload portfolio.

Could be a polish feature if time permits.

---

# 25. Final Design Standard

The SCALE MVP frontend is successful if a viewer can understand the product from the interface alone.

It should communicate:

```text
This is a serious portfolio dashboard.
This system knows what the user owns.
This system surfaces risk before upside.
This system uses AI, but does not blindly trust AI.
This system shows confidence and data quality.
This system cites evidence.
This system records recommendations.
This system supports deeper research.
This system does not execute trades.
```

The final product should feel like:

> A professional investment dashboard with an embedded, evidence-backed AI research assistant.

Not:

> A chatbot wearing a finance costume.
