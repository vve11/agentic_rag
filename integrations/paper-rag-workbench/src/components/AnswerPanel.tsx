import type { EvidenceChunk, QaData } from "../types";
import { CitationChips } from "./CitationChips";
import { EvidenceChunkCard } from "./EvidenceChunkCard";
import { StatusBadge } from "./StatusBadge";

export function AnswerPanel({
  answer,
  citations,
  chunks,
  abstain,
}: {
  answer: string;
  citations: string[];
  chunks: EvidenceChunk[];
  abstain: QaData["abstain"];
}) {
  const decision = typeof abstain === "string" ? abstain : abstain?.decision;
  const tone = decision === "answer" || !decision ? "good" : "warn";

  return (
    <section className="answer-panel">
      <header>
        <h3>Answer</h3>
        <StatusBadge tone={tone}>{decision ?? "answer"}</StatusBadge>
      </header>
      <p>{answer}</p>
      <CitationChips citations={citations} />
      <div className="evidence-list">
        {chunks.map((chunk) => (
          <EvidenceChunkCard key={chunk.chunk_id} chunk={chunk} />
        ))}
      </div>
    </section>
  );
}
