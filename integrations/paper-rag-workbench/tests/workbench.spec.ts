import { expect, test } from "@playwright/test";

test("workbench v2 fixture flow", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: /workbench navigation/i });

  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  await nav.getByRole("button", { name: /health/i }).click();
  await expect(page.getByRole("heading", { name: "Health", exact: true })).toBeVisible();
  await expect(page.getByText(/Dense retrieval is unavailable/i)).toBeVisible();

  await nav.getByRole("button", { name: /library/i }).click();
  await expect(page.getByText(/Self-RAG/)).toBeVisible();
  await page.getByRole("button", { name: /inspect paper self-rag/i }).click();
  await expect(page.getByText(/Abstract/)).toBeVisible();

  await nav.getByRole("button", { name: /^search$/i }).click();
  await page.getByLabel(/search evidence/i).fill("reflection tokens");
  await page.locator("form").getByRole("button", { name: /^search$/i }).click();
  await page.getByRole("button", { name: /inspect chunk chunk-self-rag-1/i }).click();
  await expect(page.getByText(/critiques its own generations/i)).toBeVisible();

  await nav.getByRole("button", { name: /^ask$/i }).click();
  await page.getByLabel(/question/i).fill("What is Self-RAG?");
  await page.locator("form").getByRole("button", { name: /^ask$/i }).click();
  await expect(page.getByRole("heading", { name: /Agent Timeline/i })).toBeVisible();
  await expect(page.getByText(/Understanding question/i)).toBeVisible();
  await page.getByRole("button", { name: /chunk-self-rag-1/i }).click();
  await expect(page.getByText(/critiques its own generations/i)).toBeVisible();
  await page.getByRole("button", { name: /send to dsh/i }).click();
  await expect(page.getByRole("dialog", { name: /send to dsh/i })).toBeVisible();
  await page.getByRole("button", { name: /close dsh handoff/i }).click();

  await nav.getByRole("button", { name: /discover/i }).click();
  await page.getByLabel(/topic/i).fill("agentic rag");
  await page.locator("form").getByRole("button", { name: /discover/i }).click();
  await page.getByLabel(/select candidate 11/i).check();
  await page.getByRole("button", { name: /ingest selected/i }).click();
  await expect(page.getByText(/write indexed paper and chunks/i)).toBeVisible();
});
