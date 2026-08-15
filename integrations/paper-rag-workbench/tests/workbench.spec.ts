import { expect, test } from "@playwright/test";

test("Workbench fixture workflow covers overview, library, search, ask, and discovery approval", async ({
  page,
}) => {
  await page.goto("/");

  const nav = page.getByRole("navigation", { name: /workbench navigation/i });

  await expect(page.getByRole("heading", { name: /overview/i })).toBeVisible();
  await expect(page.getByText("deepseek-v4-flash")).toBeVisible();

  await nav.getByRole("button", { name: /library/i }).click();
  await expect(page.getByText(/Self-RAG/)).toBeVisible();

  await nav.getByRole("button", { name: /^search$/i }).click();
  await page.getByLabel(/search evidence/i).fill("reflection tokens");
  await page.locator("form").getByRole("button", { name: /^search$/i }).click();
  await expect(page.getByText("chunk:chunk-self-rag-1")).toBeVisible();

  await nav.getByRole("button", { name: /^ask$/i }).click();
  await page.getByLabel(/question/i).fill("What is Self-RAG?");
  await page.locator("form").getByRole("button", { name: /^ask$/i }).click();
  await expect(page.getByText(/decide when to retrieve/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "chunk-self-rag-1" })).toBeVisible();

  await nav.getByRole("button", { name: /discover/i }).click();
  await page.getByLabel(/topic/i).fill("agentic rag");
  await page.locator("form").getByRole("button", { name: /discover/i }).click();
  await expect(page.getByText(/Agentic Retrieval/)).toBeVisible();
  await page.getByLabel(/select candidate 11/i).check();
  await page.getByRole("button", { name: /ingest selected/i }).click();
  await expect(page.getByRole("dialog", { name: /approve candidate ingest/i })).toBeVisible();
  await page.getByRole("button", { name: /approve ingest/i }).click();
  await expect(page.getByText("arxiv:2601.00001")).toBeVisible();
});
