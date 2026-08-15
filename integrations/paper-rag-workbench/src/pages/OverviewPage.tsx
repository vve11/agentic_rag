import { useEffect, useState } from "react";

import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import type { StatusData, WorkbenchClient } from "../types";

export function OverviewPage({ client }: { client: WorkbenchClient }) {
  const [data, setData] = useState<StatusData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    client
      .status()
      .then((envelope) => {
        if (!active) return;
        if (!envelope.ok || !envelope.data) {
          setError(envelope.error?.message ?? "Corpus status is unavailable.");
          return;
        }
        setData(envelope.data);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Corpus status is unavailable.");
      });

    return () => {
      active = false;
    };
  }, [client]);

  if (error) {
    return <EmptyState title="Overview unavailable" detail={error} />;
  }

  if (!data) {
    return <p className="loading">Loading overview...</p>;
  }

  const credentialsConfigured = data.workbench?.credentials?.configured ?? false;

  return (
    <>
      <header className="page-header">
        <div>
          <h2>Overview</h2>
          <p>Corpus status, model readiness, and quick actions.</p>
        </div>
        <a className="button-link" href="http://127.0.0.1:3080" target="_blank" rel="noreferrer">
          Open DSH Chat
        </a>
      </header>
      <section className="metric-grid" aria-label="Corpus status">
        <article>
          <span>Papers</span>
          <strong>{data.sqlite?.paper_count ?? 0}</strong>
        </article>
        <article>
          <span>Chunks</span>
          <strong>{data.sqlite?.chunk_count ?? 0}</strong>
        </article>
        <article>
          <span>Model</span>
          <strong>{data.llm?.chat_model ?? "unknown"}</strong>
        </article>
        <article>
          <span>Credentials</span>
          <StatusBadge tone={credentialsConfigured ? "good" : "warn"}>
            {credentialsConfigured ? "Configured" : "Missing"}
          </StatusBadge>
        </article>
      </section>
    </>
  );
}
