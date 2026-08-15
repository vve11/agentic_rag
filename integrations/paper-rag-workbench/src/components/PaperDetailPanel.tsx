import type { PaperDetailData } from "../types";

export function PaperDetailPanel({
  detail,
  onInspectChunk,
}: {
  detail: PaperDetailData;
  onInspectChunk: (chunkId: string) => void;
}) {
  return (
    <section className="paper-detail panel">
      <header>
        <h3>{detail.paper.title}</h3>
        <code>{detail.paper.paper_id}</code>
      </header>
      {detail.warnings.length ? (
        <div className="inline-warnings">
          {detail.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
      {detail.paper.abstract ? <p>{detail.paper.abstract}</p> : null}
      <section>
        <h4>Sections</h4>
        <ul className="section-list">
          {detail.sections.map((section) => (
            <li key={section.section_id}>
              <strong>{section.name}</strong>
              <span>{section.chunk_count} chunks</span>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h4>Chunks</h4>
        <div className="chunk-list">
          {detail.chunks.map((chunk) => (
            <button
              key={chunk.chunk_id}
              type="button"
              onClick={() => onInspectChunk(chunk.chunk_id)}
            >
              <span>{chunk.section || "Unknown section"}</span>
              <code>chunk:{chunk.chunk_id}</code>
              <span>{chunk.snippet || chunk.text}</span>
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}
