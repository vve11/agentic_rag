import { useEffect, useState } from "react";

import { EmptyState } from "../components/EmptyState";
import { HealthSummary } from "../components/HealthSummary";
import { QualityIssueTable } from "../components/QualityIssueTable";
import type { IndexHealthData, WorkbenchClient } from "../types";

export function HealthPage({ client }: { client: WorkbenchClient }) {
  const [data, setData] = useState<IndexHealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .indexHealth()
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Health unavailable.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <>
      <header className="page-header">
        <div>
          <h2>Health</h2>
          <p>Inspect corpus readiness, retrieval fallback, model configuration, and data quality.</p>
        </div>
      </header>
      {!data && !error ? (
        <EmptyState title="Loading health" detail="Checking local indexes." />
      ) : null}
      {error ? <EmptyState title="Health unavailable" detail={error} /> : null}
      {data ? (
        <>
          <HealthSummary data={data} />
          <section className="panel">
            <h3>Quality Issues</h3>
            <QualityIssueTable samples={data.corpus_quality.samples} />
          </section>
        </>
      ) : null}
    </>
  );
}
