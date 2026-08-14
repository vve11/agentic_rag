import { appendFile } from "node:fs/promises";

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const statusInputSchema = {
  type: "object",
  properties: {
    question: { type: "string" },
  },
  required: ["question"],
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

async function auditToolCall(toolName, args, receivedMeta) {
  if (process.env.PAPER_RAG_PRIVATE_AUDIT_PATH === undefined) {
    return;
  }

  await appendFile(
    process.env.PAPER_RAG_PRIVATE_AUDIT_PATH,
    `${JSON.stringify({
      tool_name: toolName,
      received_arguments: args,
      received_meta: receivedMeta,
    })}\n`,
    "utf8",
  );
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
      name: "fixture_status",
      description: "Private fixture status tool.",
      inputSchema: statusInputSchema,
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

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const args = request.params.arguments ?? {};
  const receivedMeta = request.params._meta ?? {};
  await auditToolCall(request.params.name, args, receivedMeta);

  if (request.params.name === "fixture_status") {
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
