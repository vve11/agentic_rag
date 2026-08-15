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

  test("client reads v2 endpoints", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/health/index")) {
        return new Response(JSON.stringify({ status: "healthy", warnings: [] }), {
          status: 200,
        });
      }
      if (url.endsWith("/api/papers/arxiv%3A2310.11511")) {
        return new Response(
          JSON.stringify({
            paper: { paper_id: "arxiv:2310.11511" },
            sections: [],
            chunks: [],
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/api/chunks/chunk-a")) {
        return new Response(
          JSON.stringify({
            chunk: { chunk_id: "chunk-a" },
            paper: {},
            neighbors: [],
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/api/dsh/handoff") && init?.method === "POST") {
        return new Response(
          JSON.stringify({ dsh_url: "http://127.0.0.1:3080", prompt: "prompt" }),
          { status: 200 },
        );
      }
      return new Response("not found", { status: 404 });
    });

    const client = createWorkbenchClient({ fetchImpl, baseUrl: "" });

    await expect(client.indexHealth()).resolves.toMatchObject({ status: "healthy" });
    await expect(client.paperDetail("arxiv:2310.11511")).resolves.toMatchObject({
      paper: { paper_id: "arxiv:2310.11511" },
    });
    await expect(client.chunkDetail("chunk-a")).resolves.toMatchObject({
      chunk: { chunk_id: "chunk-a" },
    });
    await expect(
      client.dshHandoff({
        question: "Question?",
        paper_ids: ["arxiv:2310.11511"],
        chunk_ids: ["chunk-a"],
        source: "ask",
      }),
    ).resolves.toMatchObject({ prompt: "prompt" });
  });
});
