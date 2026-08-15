import { useState } from "react";

import { AnswerPanel } from "../components/AnswerPanel";
import { ChunkDetailPanel } from "../components/ChunkDetailPanel";
import { EmptyState } from "../components/EmptyState";
import { PaperDetailPanel } from "../components/PaperDetailPanel";
import type { ChunkDetailData, PaperDetailData, QaData, WorkbenchClient } from "../types";

export function AskPage({ client }: { client: WorkbenchClient }) {
  const [question, setQuestion] = useState("");
  const [paperIdsText, setPaperIdsText] = useState("");
  const [topK, setTopK] = useState(8);
  const [data, setData] = useState<QaData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copyState, setCopyState] = useState<string | null>(null);
  const [chunkDetail, setChunkDetail] = useState<ChunkDetailData | null>(null);
  const [paperDetail, setPaperDetail] = useState<PaperDetailData | null>(null);

  const ask = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;

    setError(null);
    setData(null);
    setChunkDetail(null);
    setPaperDetail(null);
    setLoading(true);
    const paperIds = paperIdsText
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);

    try {
      const envelope = await client.qa({
        question: trimmedQuestion,
        paper_ids: paperIds,
        top_k: topK,
      });

      if (!envelope.ok || !envelope.data) {
        setError(envelope.error?.message ?? "Question answering is unavailable.");
        return;
      }

      setData(envelope.data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Question answering is unavailable.");
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

  const copyPrompt = async () => {
    const text = `基于已入库论文回答：${question.trim()}。请给出 Paper RAG 证据引用。`;
    try {
      await navigator.clipboard?.writeText(text);
      setCopyState("Copied");
    } catch {
      setCopyState(text);
    }
  };

  return (
    <>
      <header className="page-header">
        <div>
          <h2>Ask</h2>
          <p>Ask grounded questions and inspect the evidence used for each answer.</p>
        </div>
      </header>
      <form className="panel form-grid" onSubmit={ask}>
        <label>
          <span>Question</span>
          <textarea
            rows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </label>
        <label>
          <span>Paper IDs</span>
          <input
            value={paperIdsText}
            onChange={(event) => setPaperIdsText(event.target.value)}
            placeholder="arxiv:2310.11511, arxiv:2005.11401"
          />
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
        <button type="submit" disabled={!question.trim() || loading}>
          {loading ? "Asking..." : "Ask"}
        </button>
      </form>
      {error ? <EmptyState title="Answer unavailable" detail={error} /> : null}
      {data ? (
        <>
          <div className="toolbar-row">
            <button type="button" onClick={copyPrompt}>
              Copy prompt for DSH
            </button>
            {copyState ? <span className="muted">{copyState}</span> : null}
          </div>
          <AnswerPanel
            answer={data.answer}
            citations={data.citations}
            chunks={data.chunks}
            abstain={data.abstain}
            onCitationSelect={inspectChunk}
          />
          {chunkDetail ? (
            <ChunkDetailPanel detail={chunkDetail} onOpenPaper={openPaper} />
          ) : null}
          {paperDetail ? (
            <PaperDetailPanel detail={paperDetail} onInspectChunk={inspectChunk} />
          ) : null}
        </>
      ) : null}
    </>
  );
}
