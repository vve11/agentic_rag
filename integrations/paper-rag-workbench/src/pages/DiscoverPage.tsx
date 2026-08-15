import { useState, type FormEvent } from "react";

import {
  ApprovalDialog,
  candidateIngestSideEffects,
} from "../components/ApprovalDialog";
import { CandidateTable } from "../components/CandidateTable";
import { EmptyState } from "../components/EmptyState";
import type { Candidate, IngestData, WorkbenchClient } from "../types";

export function DiscoverPage({ client }: { client: WorkbenchClient }) {
  const [topic, setTopic] = useState("");
  const [sourcesText, setSourcesText] = useState("arxiv");
  const [maxCandidates, setMaxCandidates] = useState(5);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [ingestData, setIngestData] = useState<IngestData | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const discover = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedTopic = topic.trim();
    if (!trimmedTopic) return;

    setLoading(true);
    setError(null);
    setIngestData(null);
    setCandidates([]);
    setSelectedIds([]);

    try {
      const sources = sourcesText
        .split(",")
        .map((source) => source.trim())
        .filter(Boolean);
      const envelope = await client.discover({
        topic: trimmedTopic,
        max_candidates: maxCandidates,
        sources,
      });

      if (!envelope.ok || !envelope.data) {
        setError(envelope.error?.message ?? "Discovery is unavailable.");
        return;
      }

      setCandidates(envelope.data.candidates);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Discovery is unavailable.");
    } finally {
      setLoading(false);
    }
  };

  const toggleCandidate = (id: number) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((candidateId) => candidateId !== id) : [...current, id],
    );
  };

  const approveIngest = async () => {
    setIngesting(true);
    setError(null);

    try {
      const envelope = await client.ingestCandidates({
        candidate_ids: selectedIds,
        force: false,
        approval: {
          approved: true,
          operation: "discovery_candidate_ingest",
          candidate_ids: selectedIds,
          destination: "real-library",
          side_effects: candidateIngestSideEffects,
        },
      });

      if (!envelope.ok || !envelope.data) {
        setError(envelope.error?.message ?? "Candidate ingest is unavailable.");
        return;
      }

      setIngestData(envelope.data);
      setApprovalOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Candidate ingest is unavailable.");
    } finally {
      setIngesting(false);
    }
  };

  return (
    <>
      <header className="page-header">
        <div>
          <h2>Discover</h2>
          <p>Find candidate papers, then explicitly approve any ingest side effects.</p>
        </div>
      </header>
      <form className="panel form-grid" onSubmit={discover}>
        <label>
          <span>Topic</span>
          <input value={topic} onChange={(event) => setTopic(event.target.value)} />
        </label>
        <label>
          <span>Sources</span>
          <input value={sourcesText} onChange={(event) => setSourcesText(event.target.value)} />
        </label>
        <label>
          <span>Max candidates</span>
          <input
            min={1}
            max={20}
            type="number"
            value={maxCandidates}
            onChange={(event) => setMaxCandidates(Number(event.target.value))}
          />
        </label>
        <button type="submit" disabled={!topic.trim() || loading}>
          {loading ? "Discovering..." : "Discover"}
        </button>
      </form>
      {error ? <EmptyState title="Discovery unavailable" detail={error} /> : null}
      {candidates.length > 0 ? (
        <>
          <div className="toolbar-row">
            <button
              type="button"
              disabled={selectedIds.length === 0}
              onClick={() => setApprovalOpen(true)}
            >
              Ingest selected
            </button>
            <span className="muted">{selectedIds.length} selected</span>
          </div>
          <CandidateTable
            candidates={candidates}
            selectedIds={selectedIds}
            onToggle={toggleCandidate}
          />
        </>
      ) : null}
      {ingestData ? (
        <section className="panel ingest-receipt" aria-label="Ingest receipt">
          <h3>Ingest receipt</h3>
          <ul>
            {ingestData.results.map((result) => (
              <li key={`${result.candidate_id}-${result.paper_id}`}>
                {result.paper_id} {result.status ? `- ${result.status}` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <ApprovalDialog
        open={approvalOpen}
        candidateIds={selectedIds}
        onCancel={() => setApprovalOpen(false)}
        onApprove={approveIngest}
      />
      {ingesting ? <p className="loading">Ingesting approved candidates...</p> : null}
    </>
  );
}
