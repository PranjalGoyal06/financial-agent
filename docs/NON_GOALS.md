# Non-Goals

**Source of truth:** `docs/MVP_PLAN.md`  
**Status:** Frozen for MVP prototype

These are explicitly out of scope for the MVP:

- Trade execution
- Broker API integration
- Multi-user production authentication
- Autonomous scheduled monitoring
- Tax-lot / FIFO accounting
- Full compliance rule engine
- Real-time streaming market feed
- Complex portfolio optimisation
- Parallel multi-agent research swarm
- Paid market data integrations

## Boundary Notes

- The system may recommend actions, but it never executes them.
- Compliance must be logged as `not_implemented_mvp`, never as `passed`.
- Research is user-triggered only.
- ChromaDB is a retrieval index, not the source of truth.

