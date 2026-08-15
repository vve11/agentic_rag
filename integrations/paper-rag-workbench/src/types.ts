export type McpEnvelope<TData = Record<string, unknown>> = {
  ok: boolean;
  tool: string;
  trace_id?: string | null;
  evidence_role?: string;
  warnings?: string[];
  data?: TData;
  error?: {
    code: string;
    message: string;
    retryable?: boolean;
    details?: Record<string, unknown>;
  };
};

export type HealthData = {
  ok: boolean;
  service: string;
  dsh_url: string;
  models: { chat_model: string; small_model: string };
};

export type HealthStatus = "healthy" | "degraded" | "blocked";

export type HealthSample = {
  kind: "duplicate_chunk" | "parser_artifact" | "missing_section" | string;
  paper_id?: string;
  chunk_id?: string;
  chunk_ids?: string[];
  warnings?: string[];
  preview?: string;
};

export type IndexHealthData = {
  status: HealthStatus;
  sqlite: {
    available: boolean;
    paper_count: number;
    chunk_count: number;
    fts_available: boolean;
  };
  qdrant: {
    configured: boolean;
    mode: "server" | "embedded" | "none";
    reachable: boolean;
    collection_chunks?: string;
    degraded_reason?: string | null;
  };
  retrieval: {
    dense_available: boolean;
    sparse_available: boolean;
    hybrid_available: boolean;
  };
  llm: {
    configured: boolean;
    chat_model: string;
    base_url_host?: string | null;
    credential_source?: "env" | "file" | null;
  };
  corpus_quality: {
    duplicate_chunk_count: number;
    parser_artifact_count: number;
    missing_section_count: number;
    samples: HealthSample[];
  };
  warnings: string[];
};

export type PaperSummary = {
  paper_id: string;
  title: string;
  arxiv_id?: string | null;
  chunk_count?: number;
  ingested_at?: string;
};

export type EvidenceChunk = {
  chunk_id: string;
  paper_id: string;
  title?: string;
  paper_title?: string;
  page?: number;
  section?: string;
  snippet?: string;
  text?: string;
  score?: number;
};

export type PaperSectionSummary = {
  section_id: string;
  name: string;
  idx: number;
  page_start?: number | null;
  page_end?: number | null;
  chunk_count: number;
};

export type PaperDetailData = {
  paper: PaperSummary & {
    abstract?: string | null;
    year?: number | null;
    venue?: string | null;
    doi?: string | null;
    status?: string;
    parsed_with?: string | null;
    updated_at?: string;
  };
  sections: PaperSectionSummary[];
  chunks: EvidenceChunk[];
  warnings: string[];
};

export type ChunkDetailData = {
  chunk: EvidenceChunk & {
    warnings?: string[];
    char_start?: number | null;
    char_end?: number | null;
  };
  paper: PaperSummary;
  neighbors: EvidenceChunk[];
};

export type StatusData = {
  sqlite?: { available?: boolean; paper_count?: number; chunk_count?: number };
  llm?: { chat_model?: string; configured?: boolean };
  workbench?: {
    credentials?: { configured: boolean; source: string | null; writable: boolean };
  };
  papers?: PaperSummary[];
};

export type PaperListData = { count: number; papers: PaperSummary[] };
export type SearchData = { count: number; results: EvidenceChunk[]; truncated?: boolean };
export type QaData = {
  answer: string;
  citations: string[];
  chunks: EvidenceChunk[];
  abstain?: { decision?: string } | string;
};
export type SectionData = {
  section?: { name?: string };
  section_name?: string;
  chunks: EvidenceChunk[];
};
export type Candidate = {
  id: number;
  title: string;
  source?: string;
  year?: number;
  published_year?: number;
  rank?: number;
  rank_reason?: string;
  reason?: string;
  evidence_role?: string;
};
export type DiscoverData = { run?: { id?: number; topic?: string }; candidates: Candidate[]; count: number };
export type IngestData = {
  results: Array<{ candidate_id?: number; paper_id?: string; status?: string; n_chunks?: number }>;
  count?: number;
};

export type SearchInput = { query: string; top_k?: number; year_min?: number; year_max?: number };
export type QaInput = {
  question: string;
  paper_ids?: string[];
  resolved_question?: string;
  top_k?: number;
};
export type SectionInput = { paper_id: string; section_name: string };
export type DiscoverInput = { topic: string; max_candidates?: number; sources?: string[] };
export type CandidateIngestInput = {
  candidate_ids: number[];
  force?: boolean;
  approval: {
    approved: true;
    operation: "discovery_candidate_ingest";
    candidate_ids: number[];
    destination: "real-library" | "isolated-library";
    side_effects: string[];
  };
};

export type DshHandoffInput = {
  question: string;
  paper_ids: string[];
  chunk_ids: string[];
  source: "ask" | "search" | "library" | "health" | "workbench";
};

export type DshHandoffData = {
  dsh_url: string;
  prompt: string;
};

export type WorkbenchClient = {
  health(): Promise<HealthData>;
  indexHealth(): Promise<IndexHealthData>;
  status(): Promise<McpEnvelope<StatusData>>;
  papers(limit?: number): Promise<McpEnvelope<PaperListData>>;
  paperDetail(paperId: string): Promise<PaperDetailData>;
  chunkDetail(chunkId: string): Promise<ChunkDetailData>;
  search(input: SearchInput): Promise<McpEnvelope<SearchData>>;
  qa(input: QaInput): Promise<McpEnvelope<QaData>>;
  section(input: SectionInput): Promise<McpEnvelope<SectionData>>;
  discover(input: DiscoverInput): Promise<McpEnvelope<DiscoverData>>;
  ingestCandidates(input: CandidateIngestInput): Promise<McpEnvelope<IngestData>>;
  dshHandoff(input: DshHandoffInput): Promise<DshHandoffData>;
};
