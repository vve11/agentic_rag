import type { ChunkDetailData } from "../types";
import { ScoreBreakdown } from "./ScoreBreakdown";

export function ChunkDetailPanel({
  detail,
  onOpenPaper,
}: {
  detail: ChunkDetailData;
  onOpenPaper: (paperId: string) => void;
}) {
  const warnings = detail.chunk.warnings || [];
  return (
    <aside className="chunk-detail panel" aria-label="Chunk detail">
      <header>
        <div>
          <h3>{detail.paper.title || detail.chunk.paper_id}</h3>
          <code>chunk:{detail.chunk.chunk_id}</code>
        </div>
        <button type="button" onClick={() => onOpenPaper(detail.chunk.paper_id)}>
          Open paper detail
        </button>
      </header>
      <dl className="metadata-grid">
        <dt>Paper</dt>
        <dd>{detail.chunk.paper_id}</dd>
        <dt>Section</dt>
        <dd>{detail.chunk.section || "unknown"}</dd>
        <dt>Page</dt>
        <dd>{detail.chunk.page || "unknown"}</dd>
      </dl>
      <ScoreBreakdown chunk={detail.chunk} />
      {warnings.length ? (
        <div className="inline-warnings">
          {warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
      <p className="chunk-full-text">{detail.chunk.text || detail.chunk.snippet}</p>
      {detail.neighbors.length ? (
        <section>
          <h4>Nearby chunks</h4>
          {detail.neighbors.map((neighbor) => (
            <article key={neighbor.chunk_id}>
              <code>chunk:{neighbor.chunk_id}</code>
              <p>{neighbor.text || neighbor.snippet}</p>
            </article>
          ))}
        </section>
      ) : null}
    </aside>
  );
}
