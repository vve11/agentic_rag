import type { IndexHealthData } from "../types";
import { DiagnosticCard } from "./DiagnosticCard";
import { WarningBanner } from "./WarningBanner";

export function HealthSummary({ data }: { data: IndexHealthData }) {
  return (
    <section className="health-summary">
      <header>
        <h3>Index Health</h3>
        <span className={`status-pill ${data.status}`}>{data.status}</span>
      </header>
      <WarningBanner warnings={data.warnings} />
      <div className="diagnostic-grid">
        <DiagnosticCard title="SQLite" status={data.sqlite.available ? "healthy" : "blocked"}>
          <dl>
            <dt>Papers</dt>
            <dd>{data.sqlite.paper_count} papers</dd>
            <dt>Chunks</dt>
            <dd>{data.sqlite.chunk_count} chunks</dd>
            <dt>FTS</dt>
            <dd>{data.sqlite.fts_available ? "available" : "unavailable"}</dd>
          </dl>
        </DiagnosticCard>
        <DiagnosticCard title="Qdrant" status={data.qdrant.reachable ? "healthy" : "fallback"}>
          <dl>
            <dt>Mode</dt>
            <dd>{data.qdrant.mode}</dd>
            <dt>Dense</dt>
            <dd>{data.retrieval.dense_available ? "available" : "unavailable"}</dd>
            <dt>Fallback</dt>
            <dd>{data.retrieval.sparse_available ? "active" : "unavailable"}</dd>
          </dl>
        </DiagnosticCard>
        <DiagnosticCard title="LLM" status={data.llm.configured ? "healthy" : "blocked"}>
          <dl>
            <dt>Model</dt>
            <dd>{data.llm.chat_model}</dd>
            <dt>Host</dt>
            <dd>{data.llm.base_url_host || "not configured"}</dd>
            <dt>Credentials</dt>
            <dd>{data.llm.credential_source || "not configured"}</dd>
          </dl>
        </DiagnosticCard>
      </div>
    </section>
  );
}
