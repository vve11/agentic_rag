import type { EvidenceChunk } from "../types";

export function EvidenceChunkCard({ chunk }: { chunk: EvidenceChunk }) {
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
      </footer>
    </article>
  );
}
