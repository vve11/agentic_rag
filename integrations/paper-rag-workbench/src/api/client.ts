import {
  discoverFixture,
  ingestFixture,
  papersFixture,
  qaFixture,
  searchFixture,
  sectionFixture,
  statusFixture,
} from "./fixtures";
import type {
  CandidateIngestInput,
  DiscoverData,
  DiscoverInput,
  HealthData,
  IngestData,
  McpEnvelope,
  PaperListData,
  QaData,
  QaInput,
  SearchData,
  SearchInput,
  SectionData,
  SectionInput,
  StatusData,
  WorkbenchClient,
} from "../types";

type FetchLike = typeof fetch;

export function createWorkbenchClient(
  options: { baseUrl?: string; fixtureMode?: boolean; fetchImpl?: FetchLike } = {},
): WorkbenchClient {
  const baseUrl = options.baseUrl ?? "";
  const fetchImpl = options.fetchImpl ?? fetch;
  const fixtureMode = options.fixtureMode ?? import.meta.env.VITE_WORKBENCH_FIXTURES === "1";

  const get = async <T>(path: string): Promise<T> => {
    const response = await fetchImpl(`${baseUrl}${path}`);
    if (!response.ok) throw new Error(`GET ${path} failed with ${response.status}`);
    return response.json() as Promise<T>;
  };
  const post = async <T>(path: string, body: unknown): Promise<T> => {
    const response = await fetchImpl(`${baseUrl}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) return response.json() as Promise<T>;
    return response.json() as Promise<T>;
  };

  return {
    health: (): Promise<HealthData> =>
      fixtureMode
        ? Promise.resolve({
            ok: true,
            service: "paper-rag-workbench",
            dsh_url: "http://127.0.0.1:3080",
            models: {
              chat_model: "deepseek-v4-flash",
              small_model: "deepseek-v4-flash",
            },
          })
        : get("/api/health"),
    status: (): Promise<McpEnvelope<StatusData>> =>
      fixtureMode ? Promise.resolve(statusFixture) : get("/api/status"),
    papers: (limit = 20): Promise<McpEnvelope<PaperListData>> =>
      fixtureMode
        ? Promise.resolve(papersFixture)
        : get(`/api/papers?limit=${encodeURIComponent(limit)}`),
    search: (input: SearchInput): Promise<McpEnvelope<SearchData>> =>
      fixtureMode ? Promise.resolve(searchFixture) : post("/api/search", input),
    qa: (input: QaInput): Promise<McpEnvelope<QaData>> =>
      fixtureMode ? Promise.resolve(qaFixture) : post("/api/qa", input),
    section: (input: SectionInput): Promise<McpEnvelope<SectionData>> =>
      fixtureMode ? Promise.resolve(sectionFixture) : post("/api/section", input),
    discover: (input: DiscoverInput): Promise<McpEnvelope<DiscoverData>> =>
      fixtureMode ? Promise.resolve(discoverFixture) : post("/api/discover", input),
    ingestCandidates: (input: CandidateIngestInput): Promise<McpEnvelope<IngestData>> =>
      fixtureMode ? Promise.resolve(ingestFixture) : post("/api/ingest/candidates", input),
  };
}

export const workbenchClient = createWorkbenchClient();
