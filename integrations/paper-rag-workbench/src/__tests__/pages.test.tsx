import { render, screen, waitForElementToBeRemoved } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { createWorkbenchClient } from "../api/client";
import { AskPage } from "../pages/AskPage";
import { DiscoverPage } from "../pages/DiscoverPage";
import { HealthPage } from "../pages/HealthPage";
import { LibraryPage } from "../pages/LibraryPage";
import { OverviewPage } from "../pages/OverviewPage";
import { SearchPage } from "../pages/SearchPage";

describe("Overview and Library pages", () => {
  test("overview shows corpus health, model status, and DSH bridge", async () => {
    render(<OverviewPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/loading overview/i));

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("345")).toBeInTheDocument();
    expect(screen.getAllByText("deepseek-v4-flash").length).toBeGreaterThan(0);
    expect(screen.getByText("Configured")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open dsh chat/i })).toHaveAttribute(
      "href",
      "http://127.0.0.1:3080",
    );
  });

  test("library filters papers and opens a readable section drawer", async () => {
    const user = userEvent.setup();

    render(<LibraryPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/loading library/i));
    expect(screen.getByText(/Self-RAG/)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/filter papers/i), "2005");

    expect(screen.getByText(/Retrieval-Augmented Generation/)).toBeInTheDocument();
    expect(screen.queryByText(/Self-RAG/)).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText(/filter papers/i));
    await user.click(screen.getByRole("button", { name: /open section self-rag/i }));

    expect(await screen.findByRole("heading", { name: /introduction/i })).toBeInTheDocument();
    expect(screen.getByText(/retrieves passages on demand/i)).toBeInTheDocument();
  });

  test("search page renders evidence chunks", async () => {
    const user = userEvent.setup();
    render(<SearchPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await user.type(screen.getByLabelText(/search evidence/i), "reflection tokens");
    await user.click(screen.getByRole("button", { name: /^search$/i }));

    expect(await screen.findByText("chunk:chunk-self-rag-1")).toBeInTheDocument();
    expect(screen.getByText(/retrieves passages on demand/i)).toBeInTheDocument();
  });

  test("ask page renders answer citations and DSH prompt bridge", async () => {
    const user = userEvent.setup();
    render(<AskPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await user.type(screen.getByLabelText(/question/i), "What is Self-RAG?");
    await user.click(screen.getByRole("button", { name: /^ask$/i }));

    expect(await screen.findByText(/decide when to retrieve/i)).toBeInTheDocument();
    expect(screen.getByText("chunk-self-rag-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy prompt for dsh/i })).toBeInTheDocument();
  });

  test("discover requires approval before candidate ingest", async () => {
    const user = userEvent.setup();
    const baseClient = createWorkbenchClient({ fixtureMode: true });
    const ingestCandidates = vi.fn(baseClient.ingestCandidates);
    const client = { ...baseClient, ingestCandidates };

    render(<DiscoverPage client={client} />);

    await user.type(screen.getByLabelText(/topic/i), "agentic rag");
    await user.click(screen.getByRole("button", { name: /discover/i }));
    expect(await screen.findByText(/Agentic Retrieval/)).toBeInTheDocument();

    await user.click(screen.getByLabelText(/select candidate 11/i));
    await user.click(screen.getByRole("button", { name: /ingest selected/i }));
    expect(ingestCandidates).not.toHaveBeenCalled();
    expect(screen.getByText(/write indexed paper and chunks/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /approve ingest/i }));
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
    render(<HealthPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/loading health/i));

    expect(screen.getByRole("heading", { name: "Health" })).toBeInTheDocument();
    expect(screen.getByText(/Dense retrieval is unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/345/)).toBeInTheDocument();
  });
});
