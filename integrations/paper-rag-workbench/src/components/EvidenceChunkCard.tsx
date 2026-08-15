import type { EvidenceChunk } from "../types";

export function EvidenceChunkCard({
  chunk,
  onInspect,
}: {
  chunk: EvidenceChunk;
  onInspect?: (chunkId: string) => void;
}) {
  const title = chunk.title ?? chunk.paper_title ?? chunk.paper_id;
  const text = chunk.text ?? chunk.snippet ?? "";

  return (
    <article className="evidence-card">
      <header>
        <strong>{title}</strong>
        <span>{chunk.paper_id}</span>
        {chunk.page !== undefined ? <span>Page {chunk.page}</span> : null}
      </header>
      <p>{text}</p>
      <footer>
        <code>chunk:{chunk.chunk_id}</code>
        {chunk.score !== undefined ? <span>score {chunk.score.toFixed(2)}</span> : null}
        {onInspect ? (
          <button type="button" onClick={() => onInspect(chunk.chunk_id)}>
            Inspect chunk {chunk.chunk_id}
          </button>
        ) : null}
      </footer>
    </article>
  );
}
