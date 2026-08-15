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

  test("fixture client manages workspace project state", async () => {
    const client = createWorkbenchClient({ fixtureMode: true });

    const created = await client.createProject({
      name: "Self-RAG 调研",
      description: "project",
    });
    const projectId = created.project.project_id;
    const paper = await client.addProjectPaper(projectId, {
      paper_id: "arxiv:2310.11511",
      title_snapshot: "Self-RAG",
      source: "library",
    });
    const evidence = await client.pinEvidence(projectId, {
      chunk_id: "chunk-self-rag-1",
      paper_id: "arxiv:2310.11511",
      quote_snapshot: "SELF-RAG retrieves passages on demand.",
      source: "search",
    });
    const note = await client.createNote(projectId, {
      target_type: "chunk",
      target_id: "chunk-self-rag-1",
      body: "local note",
    });
    const saved = await client.saveQuestion(projectId, {
      question: "What is Self-RAG?",
      answer: "It retrieves and critiques.",
      citations: ["chunk-self-rag-1"],
      chunk_ids: ["chunk-self-rag-1"],
      trace_id: "trace-workbench-fixture",
      abstain: { decision: "answer" },
    });
    const detail = await client.project(projectId);
    const handoff = await client.projectDshHandoff(projectId, {
      instruction: "Compare methods.",
    });

    expect(paper.paper.paper_id).toBe("arxiv:2310.11511");
    expect(evidence.evidence.chunk_id).toBe("chunk-self-rag-1");
    expect(note.note.body).toBe("local note");
    expect(saved.question.citations).toEqual(["chunk-self-rag-1"]);
    expect(detail.summary.evidence_count).toBe(1);
    expect(handoff.prompt).toContain("Compare methods.");
  });
});
