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

export type WorkbenchClient = {
  health(): Promise<HealthData>;
  status(): Promise<McpEnvelope<StatusData>>;
  papers(limit?: number): Promise<McpEnvelope<PaperListData>>;
  search(input: SearchInput): Promise<McpEnvelope<SearchData>>;
  qa(input: QaInput): Promise<McpEnvelope<QaData>>;
  section(input: SectionInput): Promise<McpEnvelope<SectionData>>;
  discover(input: DiscoverInput): Promise<McpEnvelope<DiscoverData>>;
  ingestCandidates(input: CandidateIngestInput): Promise<McpEnvelope<IngestData>>;
};
