import { appendFile } from "node:fs/promises";

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const statusInputSchema = {
  type: "object",
  properties: {},
  additionalProperties: false,
};

const listInputSchema = {
  type: "object",
  properties: {
    limit: { type: "number" },
  },
  additionalProperties: false,
};

const searchInputSchema = {
  type: "object",
  properties: {
    query: { type: "string" },
    top_k: { type: "number" },
    year_min: { type: "number" },
    year_max: { type: "number" },
  },
  required: ["query"],
  additionalProperties: false,
};

const qaInputSchema = {
  type: "object",
  properties: {
    question: { type: "string" },
    paper_ids: { type: "array", items: { type: "string" } },
    resolved_question: { type: "string" },
    top_k: { type: "number" },
  },
  required: ["question"],
  additionalProperties: false,
};

const sectionInputSchema = {
  type: "object",
  properties: {
    paper_id: { type: "string" },
    section_name: { type: "string" },
  },
  required: ["paper_id", "section_name"],
  additionalProperties: false,
};

const compareInputSchema = {
  type: "object",
  properties: {
    paper_ids: { type: "array", items: { type: "string" } },
    dimensions: { type: "array", items: { type: "string" } },
  },
  required: ["paper_ids", "dimensions"],
  additionalProperties: false,
};

const wikiInputSchema = {
  type: "object",
  properties: {
    concept: { type: "string" },
  },
  required: ["concept"],
  additionalProperties: false,
};

const writeInputSchema = {
  type: "object",
  properties: {
    note: { type: "string" },
  },
  required: ["note"],
  additionalProperties: false,
};

const structuredOutputSchema = {
  type: "object",
  additionalProperties: true,
};

let writeCallCount = 0;

async function auditToolCall(toolName, args, receivedMeta, extra = {}) {
  if (process.env.PAPER_RAG_PRIVATE_AUDIT_PATH === undefined) {
    return;
  }

  await appendFile(
    process.env.PAPER_RAG_PRIVATE_AUDIT_PATH,
    `${JSON.stringify({
      tool_name: toolName,
      received_arguments: args,
      received_meta: receivedMeta,
      ...extra,
    })}\n`,
    "utf8",
  );
}

function abortReason(signal) {
  if (signal?.reason instanceof Error) {
    return signal.reason;
  }
  return new Error(String(signal?.reason ?? "cancelled"));
}

function delayOrAbort(signal, ms) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortReason(signal));
      return;
    }

    const timeout = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timeout);
        reject(abortReason(signal));
      },
      { once: true },
    );
  });
}

function credentialGeneration() {
  if (process.env.PAPER_RAG_TEST_TOKEN === "rotated-test-token") {
    return "rotated";
  }
  if (process.env.PAPER_RAG_TEST_TOKEN !== undefined) {
    return "initial";
  }
  return "absent";
}

const server = new Server(
  {
    name: "paper-rag-private-fixture",
    version: "0.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "paper_status",
      description: "Private fixture status tool.",
      inputSchema: statusInputSchema,
      outputSchema: structuredOutputSchema,
    },
    {
      name: "paper_list",
      description: "Private fixture paper list tool.",
      inputSchema: listInputSchema,
      outputSchema: structuredOutputSchema,
    },
    {
      name: "paper_search",
      description: "Private fixture paper search tool.",
      inputSchema: searchInputSchema,
      outputSchema: structuredOutputSchema,
    },
    {
      name: "paper_qa",
      description: "Private fixture paper qa tool.",
      inputSchema: qaInputSchema,
      outputSchema: structuredOutputSchema,
    },
    {
      name: "paper_section",
      description: "Private fixture paper section tool.",
      inputSchema: sectionInputSchema,
      outputSchema: structuredOutputSchema,
    },
    {
      name: "paper_compare",
      description: "Private fixture paper compare tool.",
      inputSchema: compareInputSchema,
      outputSchema: structuredOutputSchema,
    },
    {
      name: "wiki_lookup",
      description: "Private fixture wiki lookup tool.",
      inputSchema: wikiInputSchema,
      outputSchema: structuredOutputSchema,
    },
    {
      name: "write_probe",
      description: "Private fixture write probe.",
      inputSchema: writeInputSchema,
      outputSchema: structuredOutputSchema,
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request, extra) => {
  const args = request.params.arguments ?? {};
  const receivedMeta = request.params._meta ?? {};
  await auditToolCall(request.params.name, args, receivedMeta);

  if (request.params.name === "paper_status" || request.params.name === "paper_search") {
    if (args.question === "slow-cancel" || args.query === "slow-cancel") {
      try {
        await delayOrAbort(extra.signal, 1000);
      } catch (error) {
        await auditToolCall(request.params.name, args, receivedMeta, {
          lifecycle: "cancelled",
        });
        throw error;
      }
    }

    const structuredContent = {
      ok: true,
      received_arguments: args,
      received_meta: receivedMeta,
      has_test_credential: Boolean(process.env.PAPER_RAG_TEST_TOKEN),
      credential_generation: credentialGeneration(),
      write_call_count: writeCallCount,
    };
    return {
      content: [{ type: "text", text: JSON.stringify({ ok: true }) }],
      structuredContent,
    };
  }

  if (
    [
      "paper_list",
      "paper_qa",
      "paper_section",
      "paper_compare",
      "wiki_lookup",
    ].includes(request.params.name)
  ) {
    const structuredContent = {
      ok: true,
      tool: request.params.name,
      received_arguments: args,
      received_meta: receivedMeta,
      has_test_credential: Boolean(process.env.PAPER_RAG_TEST_TOKEN),
      credential_generation: credentialGeneration(),
      write_call_count: writeCallCount,
      citations: request.params.name === "paper_qa" ? ["chunk:c1"] : [],
    };
    return {
      content: [{ type: "text", text: JSON.stringify({ ok: true }) }],
      structuredContent,
    };
  }

  if (request.params.name === "write_probe") {
    writeCallCount += 1;
    const structuredContent = {
      approved: true,
      received_arguments: args,
      received_meta: receivedMeta,
    };
    return {
      content: [{ type: "text", text: JSON.stringify({ approved: true }) }],
      structuredContent,
    };
  }

  throw new Error(`unknown fixture tool: ${request.params.name}`);
});

await server.connect(new StdioServerTransport());
