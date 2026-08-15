import type {
  DiscoverData,
  IngestData,
  McpEnvelope,
  PaperListData,
  QaData,
  SearchData,
  SectionData,
  StatusData,
} from "../types";

export const statusFixture: McpEnvelope<StatusData> = {
  ok: true,
  tool: "paper_status",
  evidence_role: "metadata",
  warnings: [],
  data: {
    sqlite: { available: true, paper_count: 8, chunk_count: 345 },
    llm: { chat_model: "deepseek-v4-flash", configured: true },
    workbench: { credentials: { configured: true, source: "file", writable: true } },
  },
};

export const papersFixture: McpEnvelope<PaperListData> = {
  ok: true,
  tool: "paper_list",
  evidence_role: "metadata",
  warnings: [],
  data: {
    count: 2,
    papers: [
      {
        paper_id: "arxiv:2310.11511",
        title: "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection",
        arxiv_id: "2310.11511",
        chunk_count: 58,
      },
      {
        paper_id: "arxiv:2005.11401",
        title: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        arxiv_id: "2005.11401",
        chunk_count: 42,
      },
    ],
  },
};

export const searchFixture: McpEnvelope<SearchData> = {
  ok: true,
  tool: "paper_search",
  evidence_role: "indexed_chunks",
  warnings: [],
  data: {
    count: 2,
    results: [
      {
        chunk_id: "chunk-self-rag-1",
        paper_id: "arxiv:2310.11511",
        title: "Self-RAG",
        page: 3,
        snippet: "SELF-RAG retrieves passages on demand and critiques its own generations.",
        score: 0.92,
      },
      {
        chunk_id: "chunk-self-rag-2",
        paper_id: "arxiv:2310.11511",
        title: "Self-RAG",
        page: 10,
        snippet: "The model learns to retrieve, generate, and critique through reflection tokens.",
        score: 0.88,
      },
    ],
  },
};

export const qaFixture: McpEnvelope<QaData> = {
  ok: true,
  tool: "paper_qa",
  evidence_role: "indexed_chunks",
  trace_id: "trace-workbench-fixture",
  warnings: [],
  data: {
    answer:
      "Self-RAG trains a model to decide when to retrieve, then critique whether retrieved evidence supports generated claims.",
    citations: ["chunk-self-rag-1", "chunk-self-rag-2"],
    chunks: searchFixture.data!.results,
    abstain: { decision: "answer" },
  },
};

export const sectionFixture: McpEnvelope<SectionData> = {
  ok: true,
  tool: "paper_section",
  evidence_role: "indexed_chunks",
  warnings: [],
  data: {
    section: { name: "Introduction" },
    chunks: searchFixture.data!.results,
  },
};

export const discoverFixture: McpEnvelope<DiscoverData> = {
  ok: true,
  tool: "paper_discover",
  evidence_role: "discovery_only",
  warnings: [],
  data: {
    run: { id: 7, topic: "agentic rag" },
    count: 2,
    candidates: [
      {
        id: 11,
        title: "Agentic Retrieval for Language Models",
        source: "arxiv",
        year: 2026,
        rank: 1,
        rank_reason: "retrieval planning focus",
        evidence_role: "discovery_only_not_answer_evidence",
      },
      {
        id: 12,
        title: "Evaluating Self-Reflective RAG",
        source: "arxiv",
        year: 2025,
        rank: 2,
        rank_reason: "evaluation focus",
        evidence_role: "discovery_only_not_answer_evidence",
      },
    ],
  },
};

export const ingestFixture: McpEnvelope<IngestData> = {
  ok: true,
  tool: "discovery_candidate_ingest",
  evidence_role: "metadata",
  warnings: [],
  data: {
    count: 1,
    results: [
      {
        candidate_id: 11,
        paper_id: "arxiv:2601.00001",
        status: "ingested",
        n_chunks: 39,
      },
    ],
  },
};
