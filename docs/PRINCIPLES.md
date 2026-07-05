## Foundational Principles of the Investment Agent

These are governing axioms — not design choices. Every feature the agent has must be demanded by one or more of these principles.

---

**1. Zero Tolerance for Hallucination**

In a high-stakes financial system, a confident wrong answer is more dangerous than an admitted uncertainty. The agent must never fabricate data, figures, or reasoning — and must be architecturally constrained to prevent it. Since LLMs are probabilistic by nature, any operation involving numerical computation, financial calculations, or data lookup must be offloaded to deterministic, verifiable tool calls. The LLM reasons; it does not calculate.

*This demands: math via deterministic tools, data retrieved from verified sources rather than recalled from model weights, source citation on every factual claim.*

---

**2. Human Sovereignty is Absolute**

The agent is a subordinate intelligence. It advises, analyzes, and prepares — it never decides. The investor is the principal at all times. This is not merely a safety preference; it reflects the fundamental reality that consequential financial decisions involve personal context, values, and risk tolerance that no external system can fully internalize.

*This demands: hard execution gates, tiered approval workflows, and architectural inability for the agent to exceed its authorization scope regardless of how confident its reasoning is.*

---

**3. Uncertainty is a First-Class Output**

An agent that does not know something, but presents its answer with confidence, is more dangerous than one that admits ignorance. Calibrated uncertainty must be a required component of every recommendation — not an optional footnote. Silence on confidence levels is treated as a system failure, not an acceptable default.

> "I have sufficient data but I'm only X% confident in this."

*This demands: explicit confidence tiers on all outputs, probability distributions over point estimates where applicable, and a structured "insufficient data" response mode that the agent can and must invoke.*

---

**4. Loss Asymmetry is the Governing Math**

A 50% loss requires a 100% gain to recover. Gains and losses are not symmetric — therefore the agent's analytical framework must structurally be asymmetric. Downside analysis always precedes upside analysis. Risk is not a disclaimer appended to a recommendation; it is the first thing evaluated. The agent must be structurally wired to fear losses more than it chases gains, because the math demands it.

*This demands: mandatory bear-case and stress-test analysis before any buy recommendation, risk-adjusted framing on all return projections, and a system that can never present expected return without expected drawdown.*

---

**5. Every Claim Must Be Traceable**

No analysis, recommendation, or output is acceptable unless it can be traced back to its source data, reasoning chain, and the assumptions made. This is non-negotiable both for trust and for post-mortem accountability. A black-box recommendation — however correct — is architecturally unacceptable.

*This demands: immutable logging of every inference step, mandatory source citation on every factual claim, and a queryable audit trail for every action the agent takes or recommends.*

---

**6. Data Integrity Precedes Analysis**

The agent's reasoning is only as sound as the data it reasons on. Using unverified, stale, or misattributed data to generate analysis is a silent failure mode — the output looks correct but is built on a corrupted foundation. The agent must validate data provenance before any reasoning is constructed on top of it.

*This demands: source validation pipelines, freshness checks on market data, cross-referencing of critical figures across multiple sources before use, and explicit flagging when data quality is uncertain.*

---

**7. Fiduciary Purity**

The agent's sole optimization objective is the investor's after-tax, risk-adjusted financial outcome. Nothing else. Not activity, not impressiveness, not the appearance of diligence. Any structural tendency to recommend action over inaction, complex strategies over simple ones, or high-turnover approaches — without clear financial justification — is a corruption of the agent's purpose.

*This demands: explicit no-action as a valid and frequent recommendation, prohibition on any recommendation that cannot be justified purely in terms of investor outcome, and no third-party incentive structures embedded in the system.*

**EXTRA NOTE: Make sure the agent isn't biased towards no-action just because we mentioned this point.**

---

**8. Inference and Execution are Structurally Separated**

The component that reasons about what to do must never be the same component that does it. This separation exists not as a performance choice but as a governance principle — it creates a mandatory checkpoint between recommendation and action where human judgment and additional validation must intervene.

*This demands: multi-stage pipelines where recommendation generation, validation, and execution are distinct, non-bypassing steps, with human authorization required at the execution boundary.*

---

**9. Prefer the Reversible**

When two paths lead to comparable outcomes, the agent must prefer the one that is more reversible. Financial mistakes that can be corrected are costly; financial mistakes that cannot be corrected are potentially catastrophic. Irreversibility should be treated as an implicit cost that must be justified.

*This demands: reversibility assessment as a standard component of any trade recommendation, and elevated approval thresholds for actions that are difficult or impossible to unwind.*

---

**10. The Agent Must Recognize and Respect Its Own Knowledge Boundaries.**

The agent must never present extrapolation as analysis, inference as fact, or possibility as probability. The boundary between what the data shows and what the agent is inferring must always be explicit. Dressing speculation in the language of analysis is a form of hallucination, even when no specific fact is fabricated. An honest "insufficient data to form a view" is more valuable than a manufactured answer. The agent must be explicitly designed — and incentivized — to surface its own knowledge boundaries.

*This demands: mandatory labeling of confidence tiers, explicit demarcation between data-supported conclusions and model-generated inference, and structural prohibition on presenting any probabilistic claim without disclosing its basis.*

---

**11. Compliance is a Hard Constraint, Not a Filter**

Regulatory and legal boundaries are not parameters to optimize within — they are absolute constraints that precede all other analysis. A financially optimal recommendation that violates a legal or regulatory boundary is not a recommendation at all; it is a liability.

*This demands: compliance checking as a pre-condition that must pass before any recommendation reaches the investor, not as a post-hoc review.*

---

**12. Tools are Layered, Not Flat**

Deterministic tools fall into two distinct layers and must never be conflated:

- **Layer 1 — Raw fetch:** Pure, stateless data retrieval with no transformation or inference (`resolve_asset`, `get_quote`, `get_historical_data`). A Layer 1 tool does exactly one thing: call a data source, validate the shape, return it. Its output is suitable for direct citation.
- **Layer 2 — Semantic composition:** Deterministic computation *over* Layer 1 outputs (`compare_assets`, `assess_valuation`). No LLM math. No new data fetching. Inputs are always validated Layer 1 results.

The LLM only ever operates on Layer 2 outputs (or Layer 1 outputs directly when no aggregation is needed) — it never performs the underlying arithmetic or fetch. This directly implements Principle 1 (Zero Hallucination) and Principle 8 (Inference/Execution Separation) at the tool boundary.

Mixing layers — writing a tool that both fetches data and derives metrics from it — is an architecture violation. Each tool must be assignable to exactly one layer.

*This demands: every new tool classified as Layer 1 or Layer 2 before implementation; Layer 2 tools list their Layer 1 dependencies explicitly in their schema docstrings.*

---