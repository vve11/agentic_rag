import { screen, waitForElementToBeRemoved } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { createWorkbenchClient } from "../api/client";
import { AskPage } from "../pages/AskPage";
import { DiscoverPage } from "../pages/DiscoverPage";
import { HealthPage } from "../pages/HealthPage";
import { LibraryPage } from "../pages/LibraryPage";
import { OverviewPage } from "../pages/OverviewPage";
import { SearchPage } from "../pages/SearchPage";
import { renderWithI18n } from "../test/render";

describe("Overview and Library pages", () => {
  test("overview shows corpus health, model status, and DSH bridge", async () => {
    window.localStorage.clear();
    renderWithI18n(<OverviewPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/正在加载概览/));

    expect(screen.getByRole("heading", { name: "概览" })).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("345")).toBeInTheDocument();
    expect(screen.getAllByText("deepseek-v4-flash").length).toBeGreaterThan(0);
    expect(screen.getByText("已配置")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /打开 DSH 对话/ })).toHaveAttribute(
      "href",
      "http://127.0.0.1:3080",
    );
  });

  test("library filters papers and opens a readable section drawer", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();

    renderWithI18n(<LibraryPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/正在加载论文库/));
    expect(screen.getByText(/Self-RAG/)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/筛选论文/), "2005");

    expect(screen.getByText(/Retrieval-Augmented Generation/)).toBeInTheDocument();
    expect(screen.queryByText(/Self-RAG/)).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText(/筛选论文/));
    await user.click(screen.getByRole("button", { name: /打开章节 self-rag/i }));

    expect(await screen.findByRole("heading", { name: /引言/ })).toBeInTheDocument();
    expect(screen.getByText(/retrieves passages on demand/i)).toBeInTheDocument();
  });

  test("search page renders evidence chunks", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    renderWithI18n(<SearchPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await user.type(screen.getByLabelText(/检索证据/), "reflection tokens");
    await user.click(screen.getByRole("button", { name: /^检索$/ }));

    expect(await screen.findByText("chunk:chunk-self-rag-1")).toBeInTheDocument();
    expect(screen.getByText(/retrieves passages on demand/i)).toBeInTheDocument();
  });

  test("ask page renders answer citations and DSH prompt bridge", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    renderWithI18n(<AskPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await user.type(screen.getByLabelText(/问题/), "What is Self-RAG?");
    await user.click(screen.getByRole("button", { name: /^提问$/ }));

    expect(await screen.findByText(/decide when to retrieve/i)).toBeInTheDocument();
    expect(screen.getByText("chunk-self-rag-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /复制 DSH 提示词/ })).toBeInTheDocument();
  });

  test("discover requires approval before candidate ingest", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    const baseClient = createWorkbenchClient({ fixtureMode: true });
    const ingestCandidates = vi.fn(baseClient.ingestCandidates);
    const client = { ...baseClient, ingestCandidates };

    renderWithI18n(<DiscoverPage client={client} />);

    await user.type(screen.getByLabelText(/主题/), "agentic rag");
    await user.click(screen.getByRole("button", { name: /^发现$/ }));
    expect(await screen.findByText(/Agentic Retrieval/)).toBeInTheDocument();

    await user.click(screen.getByLabelText(/选择候选 11/));
    await user.click(screen.getByRole("button", { name: /入库所选/ }));
    expect(ingestCandidates).not.toHaveBeenCalled();
    expect(screen.getByText(/写入索引论文和分块/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /批准入库/ }));
    expect(await screen.findByText(/arxiv:2601.00001/)).toBeInTheDocument();
    expect(ingestCandidates).toHaveBeenCalledWith(
      expect.objectContaining({
        candidate_ids: [11],
        approval: expect.objectContaining({
          approved: true,
          operation: "discovery_candidate_ingest",
          candidate_ids: [11],
          destination: "real-library",
        }),
      }),
    );
  });

  test("health page loads index diagnostics", async () => {
    window.localStorage.clear();
    renderWithI18n(<HealthPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/正在加载健康检查/));

    expect(screen.getByRole("heading", { name: "健康检查" })).toBeInTheDocument();
    expect(screen.getByText(/Dense retrieval is unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/345/)).toBeInTheDocument();
  });

  test("library opens paper detail", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    renderWithI18n(<LibraryPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/正在加载论文库/));
    await user.click(screen.getByRole("button", { name: /查看论文 self-rag/i }));

    expect(await screen.findByRole("heading", { name: /Self-RAG/i })).toBeInTheDocument();
    expect(screen.getByText(/Abstract/)).toBeInTheDocument();
  });

  test("ask citation opens chunk drilldown", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    renderWithI18n(<AskPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await user.type(screen.getByLabelText(/问题/), "What is Self-RAG?");
    await user.click(screen.getByRole("button", { name: /^提问$/ }));
    await user.click(await screen.findByRole("button", { name: /chunk-self-rag-1/i }));

    expect(await screen.findByText(/critiques its own generations/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /打开论文详情/ })).toBeInTheDocument();
  });

  test("search evidence card opens chunk drilldown", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    renderWithI18n(<SearchPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await user.type(screen.getByLabelText(/检索证据/), "reflection tokens");
    await user.click(screen.getByRole("button", { name: /^检索$/ }));
    await user.click(
      await screen.findByRole("button", { name: /查看分块 chunk-self-rag-1/i }),
    );

    expect(await screen.findByText(/critiques its own generations/i)).toBeInTheDocument();
  });

  test("ask page creates a structured dsh handoff", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    const baseClient = createWorkbenchClient({ fixtureMode: true });
    const dshHandoff = vi.fn(baseClient.dshHandoff);
    const client = { ...baseClient, dshHandoff };

    renderWithI18n(<AskPage client={client} />);

    await user.type(screen.getByLabelText(/问题/), "What is Self-RAG?");
    await user.click(screen.getByRole("button", { name: /^提问$/ }));
    await user.click(await screen.findByRole("button", { name: /发送到 DSH/ }));

    expect(dshHandoff).toHaveBeenCalledWith(
      expect.objectContaining({
        question: "What is Self-RAG?",
        paper_ids: expect.arrayContaining(["arxiv:2310.11511"]),
        chunk_ids: expect.arrayContaining(["chunk-self-rag-1"]),
        source: "ask",
      }),
    );
    expect(await screen.findByRole("dialog", { name: /发送到 DSH/ })).toBeInTheDocument();
  });

  test("ask page streams answer and shows agent timeline", async () => {
    const user = userEvent.setup();
    window.localStorage.clear();
    renderWithI18n(<AskPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await user.type(screen.getByLabelText(/问题/), "What is Self-RAG?");
    await user.click(screen.getByRole("button", { name: /^提问$/ }));

    expect(await screen.findByRole("heading", { name: /执行轨迹/ })).toBeInTheDocument();
    expect(await screen.findByText(/Understanding question/i)).toBeInTheDocument();
    expect(await screen.findByText(/decide when to retrieve/i)).toBeInTheDocument();
    expect(screen.getByText("chunk-self-rag-1")).toBeInTheDocument();
  });
});
