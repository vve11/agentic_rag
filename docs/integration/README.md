# DeerFlow Integration Reference

Snapshot of the deerflow-side files that wire `paper_rag` into a DeerFlow
deployment. The runnable checkout under `integrations/deer-flow` now contains
the primary Gateway router, Harness tool adapter, and `paper-research` subagent;
this folder keeps lightweight reference copies for review and external ports.

| Folder | Purpose |
|---|---|
| `router/` | paper_rag HTTP endpoints + Prometheus `/metrics` router |
| `middleware/gateway/` | 8-layer gateway middleware (auth / observability / protection) |
| `middleware/langgraph/` | 4 langgraph middleware (token cost / latency / recursion guard / PII scrub) |
| `subagent/` | community/paper_rag tools + paper-research subagent config |
| `frontend/` | Next.js workspace/paper-rag page |
| `observability/` | Prometheus + Grafana docker-compose override + alert rules |

See:

- `paper_rag/docs/adrs/0015-m8-service-deerflow-gateway.md`
- `paper_rag/docs/adrs/0020-gateway-middleware-and-observability.md`
- `paper_rag/docs/adrs/0021-langgraph-middleware-hardening.md`

for the design rationale behind each integration layer.
