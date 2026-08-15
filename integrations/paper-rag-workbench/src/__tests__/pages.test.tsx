import { render, screen, waitForElementToBeRemoved } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import { createWorkbenchClient } from "../api/client";
import { LibraryPage } from "../pages/LibraryPage";
import { OverviewPage } from "../pages/OverviewPage";

describe("Overview and Library pages", () => {
  test("overview shows corpus health, model status, and DSH bridge", async () => {
    render(<OverviewPage client={createWorkbenchClient({ fixtureMode: true })} />);

    await waitForElementToBeRemoved(() => screen.queryByText(/loading overview/i));

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("345")).toBeInTheDocument();
    expect(screen.getByText("deepseek-v4-flash")).toBeInTheDocument();
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
});
