import { useRef, useState } from "react";

import { createInitialQaStreamState, reduceQaStreamEvent } from "../api/qaStream";
import { AgentTimeline } from "../components/AgentTimeline";
import { AnswerPanel } from "../components/AnswerPanel";
import { ChunkDetailPanel } from "../components/ChunkDetailPanel";
import { DshHandoffDialog } from "../components/DshHandoffDialog";
import { EmptyState } from "../components/EmptyState";
import { PaperDetailPanel } from "../components/PaperDetailPanel";
import { useI18n } from "../i18n";
import type {
  ChunkDetailData,
  DshHandoffData,
  PaperDetailData,
  QaData,
  QaStreamEvent,
  QaStreamState,
  WorkbenchClient,
} from "../types";

export function AskPage({ client }: { client: WorkbenchClient }) {
  const { t } = useI18n();
  const [question, setQuestion] = useState("");
  const [paperIdsText, setPaperIdsText] = useState("");
  const [topK, setTopK] = useState(8);
  const [data, setData] = useState<QaData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copyState, setCopyState] = useState<string | null>(null);
  const [chunkDetail, setChunkDetail] = useState<ChunkDetailData | null>(null);
  const [paperDetail, setPaperDetail] = useState<PaperDetailData | null>(null);
  const [handoff, setHandoff] = useState<DshHandoffData | null>(null);
  const [streamState, setStreamState] = useState<QaStreamState | null>(null);
  const askRunRef = useRef(0);

  const ask = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;

    setError(null);
    setData(null);
    setChunkDetail(null);
    setPaperDetail(null);
    setHandoff(null);
    setStreamState(null);
    setLoading(true);
    const paperIds = paperIdsText
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);

    const input = {
      question: trimmedQuestion,
      paper_ids: paperIds,
      top_k: topK,
    };
    const runId = askRunRef.current + 1;
    askRunRef.current = runId;
    const initial = createInitialQaStreamState(trimmedQuestion);
    setStreamState(initial);
    setData({ answer: "", citations: [], chunks: [], abstain: {} });

    try {
      await client.qaStream(input, (streamEvent: QaStreamEvent) => {
        if (askRunRef.current !== runId) return;
        setStreamState((current) => {
          const next = reduceQaStreamEvent(
            current || createInitialQaStreamState(trimmedQuestion),
            streamEvent,
          );
          setData(next.answer);
          return next;
        });
      });
    } catch (streamReason) {
      const envelope = await client.qa({
        question: trimmedQuestion,
        paper_ids: paperIds,
        top_k: topK,
      });

      if (!envelope.ok || !envelope.data) {
        setError(
          envelope.error?.message ||
            (streamReason instanceof Error
              ? streamReason.message
              : t("ask.unavailable")),
        );
        return;
      }

      setData(envelope.data);
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

  const sendToDsh = async () => {
    if (!data) return;
    const paperIds = Array.from(new Set(data.chunks.map((chunk) => chunk.paper_id)));
    const chunkIds = data.citations.length
      ? data.citations
      : data.chunks.map((chunk) => chunk.chunk_id);
    setHandoff(
      await client.dshHandoff({
        question: question.trim(),
        paper_ids: paperIds,
        chunk_ids: chunkIds,
        source: "ask",
      }),
    );
  };

  const copyPrompt = async () => {
    const text = `基于已入库论文回答：${question.trim()}。请给出 Paper RAG 证据引用。`;
    try {
      await navigator.clipboard?.writeText(text);
      setCopyState(t("ask.copied"));
    } catch {
      setCopyState(text);
    }
  };

  const hasAnswerData = Boolean(data && (data.answer || data.chunks.length || streamState?.done));

  return (
    <>
      <header className="page-header">
        <div>
          <h2>{t("ask.title")}</h2>
          <p>{t("ask.subtitle")}</p>
        </div>
      </header>
      <form className="panel form-grid" onSubmit={ask}>
        <label>
          <span>{t("ask.question")}</span>
          <textarea
            rows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </label>
        <label>
          <span>{t("ask.paperIds")}</span>
          <input
            value={paperIdsText}
            onChange={(event) => setPaperIdsText(event.target.value)}
            placeholder="arxiv:2310.11511, arxiv:2005.11401"
          />
        </label>
        <label>
          <span>{t("ask.topK")}</span>
          <input
            min={1}
            max={20}
            type="number"
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
          />
        </label>
        <button type="submit" disabled={!question.trim() || loading}>
          {loading ? t("ask.loading") : t("ask.submit")}
        </button>
      </form>
      {error ? <EmptyState title={t("ask.unavailable")} detail={error} /> : null}
      {data ? (
        <>
          {streamState ? (
            <AgentTimeline stages={streamState.stages} running={loading && !streamState.done} />
          ) : null}
          {hasAnswerData ? (
            <div className="toolbar-row">
              <button type="button" onClick={copyPrompt}>
                {t("ask.copyPrompt")}
              </button>
              <button type="button" onClick={sendToDsh}>
                {t("ask.sendToDsh")}
              </button>
              {copyState ? <span className="muted">{copyState}</span> : null}
            </div>
          ) : null}
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
          {handoff ? (
            <DshHandoffDialog data={handoff} onClose={() => setHandoff(null)} />
          ) : null}
        </>
      ) : null}
    </>
  );
}
