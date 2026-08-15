import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import type { QaStreamStage } from "../types";

function StageIcon({ stage }: { stage: QaStreamStage }) {
  if (stage.status === "failed") return <AlertCircle aria-hidden="true" size={16} />;
  if (stage.status === "running") {
    return <Loader2 aria-hidden="true" size={16} className="spin" />;
  }
  return <CheckCircle2 aria-hidden="true" size={16} />;
}

export function AgentTimeline({
  stages,
  running,
}: {
  stages: QaStreamStage[];
  running: boolean;
}) {
  if (!running && stages.length === 0) return null;
  return (
    <section className="agent-timeline" aria-label="Agent Timeline">
      <header>
        <h3>Agent Timeline</h3>
        {running ? <span className="status-pill degraded">running</span> : null}
      </header>
      <ol>
        {stages.map((stage) => (
          <li key={stage.stage}>
            <StageIcon stage={stage} />
            <div>
              <strong>{stage.label}</strong>
              <span>{stage.status}</span>
              {typeof stage.elapsed_ms === "number" ? <span>{stage.elapsed_ms} ms</span> : null}
              {stage.summary ? <p>{stage.summary}</p> : null}
              {stage.error ? <p className="error-text">{stage.error}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
