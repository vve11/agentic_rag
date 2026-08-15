import { describe, expect, test, vi } from "vitest";

import { createWorkbenchClient } from "../api/client";

describe("Workbench API client", () => {
  test("uses fixture responses without touching fetch", async () => {
    const fetchImpl = vi.fn();
    const client = createWorkbenchClient({ fixtureMode: true, fetchImpl: fetchImpl as never });

    const status = await client.status();
    const qa = await client.qa({ question: "What is Self-RAG?", top_k: 5 });

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(status.tool).toBe("paper_status");
    expect(status.data?.sqlite?.paper_count).toBeGreaterThan(0);
    expect(qa.tool).toBe("paper_qa");
    expect(qa.data?.citations).toContain("chunk-self-rag-1");
  });

  test("posts JSON and returns MCP envelopes", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        tool: "paper_search",
        data: { results: [{ chunk_id: "c1", text: "evidence" }] },
      }),
    });
    const client = createWorkbenchClient({
      baseUrl: "http://127.0.0.1:3091",
      fetchImpl: fetchImpl as never,
    });

    const result = await client.search({ query: "reflection", top_k: 3 });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:3091/api/search",
      expect.objectContaining({
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query: "reflection", top_k: 3 }),
      }),
    );
    expect(result.data?.results[0].chunk_id).toBe("c1");
  });
});
