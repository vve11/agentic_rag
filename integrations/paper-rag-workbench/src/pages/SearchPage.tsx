import { useState } from "react";

import { ChunkDetailPanel } from "../components/ChunkDetailPanel";
import { EmptyState } from "../components/EmptyState";
import { EvidenceChunkCard } from "../components/EvidenceChunkCard";
import { PaperDetailPanel } from "../components/PaperDetailPanel";
import type { ChunkDetailData, PaperDetailData, SearchData, WorkbenchClient } from "../types";

export function SearchPage({ client }: { client: WorkbenchClient }) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(8);
  const [data, setData] = useState<SearchData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [chunkDetail, setChunkDetail] = useState<ChunkDetailData | null>(null);
  const [paperDetail, setPaperDetail] = useState<PaperDetailData | null>(null);

  const search = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    setError(null);
    setData(null);
    setChunkDetail(null);
    setPaperDetail(null);
    setLoading(true);

    try {
      const envelope = await client.search({ query: trimmedQuery, top_k: topK });
      if (!envelope.ok || !envelope.data) {
        setError(envelope.error?.message ?? "Evidence search is unavailable.");
        return;
      }
      setData(envelope.data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Evidence search is unavailable.");
    } finally {
      setLoading(false);
    }
  };

  const inspectChunk = async (chunkId: string) => {
    setChunkDetail(await client.chunkDetail(chunkId));
  };

  const openPaper = async (paperId: string) => {
    setPaperDetail(await client.paperDetail(paperId));
  };

  return (
    <>
      <header className="page-header">
        <div>
          <h2>Search</h2>
          <p>Retrieve source chunks before asking the model to synthesize.</p>
        </div>
      </header>
      <form className="panel form-grid" onSubmit={search}>
        <label>
          <span>Search evidence</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label>
          <span>Top K</span>
          <input
            min={1}
            max={20}
            type="number"
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
          />
        </label>
        <button type="submit" disabled={!query.trim() || loading}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>
      {error ? <EmptyState title="Search unavailable" detail={error} /> : null}
      {data ? (
        <section className="evidence-list" aria-label="Search results">
          {data.results.map((chunk) => (
            <EvidenceChunkCard key={chunk.chunk_id} chunk={chunk} onInspect={inspectChunk} />
          ))}
        </section>
      ) : null}
      {chunkDetail ? <ChunkDetailPanel detail={chunkDetail} onOpenPaper={openPaper} /> : null}
      {paperDetail ? (
        <PaperDetailPanel detail={paperDetail} onInspectChunk={inspectChunk} />
      ) : null}
    </>
  );
}
