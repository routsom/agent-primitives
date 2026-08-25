import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { runSubagent } from "../agents/subagent.js";
import type { AgentTask } from "../agents/types.js";
import { validateAgentTask } from "../harness/index.js";
import type { Harness } from "../harness/index.js";
import type { ToolRuntime } from "../tools/types.js";
import type { ChatModel } from "../providers/types.js";
import type { Tracer } from "../tracing/tracer.js";
import { buildAgentCard } from "./agentCard.js";

export interface A2AServerOptions {
  port: number;
  baseUrl: string;
  model: ChatModel;
  harness: Harness;
  runtime: ToolRuntime;
  tracer: Tracer;
  maxDelegationDepth: number;
}

/**
 * Minimal A2A server: publishes an agent card and accepts delegated tasks over HTTP+JSON.
 * Every inbound task is validated and run through the same harness as a local subagent
 * spawn - no shortcut for remote callers (specs/protocols/a2a.md, notes section 7).
 */
export function startA2AServer(opts: A2AServerOptions) {
  const card = buildAgentCard("subagent", opts.baseUrl);

  const server = createServer((req, res) => {
    void handleRequest(req, res, opts, card);
  });
  server.listen(opts.port);
  return server;
}

async function handleRequest(
  req: IncomingMessage,
  res: ServerResponse,
  opts: A2AServerOptions,
  card: ReturnType<typeof buildAgentCard>,
): Promise<void> {
  if (req.method === "GET" && req.url === "/.well-known/agent.json") {
    respondJson(res, 200, card);
    return;
  }

  if (req.method === "POST" && req.url === "/tasks") {
    try {
      const body = await readBody(req);
      const inboundDepth = typeof body.delegationDepth === "number" ? body.delegationDepth : 0;
      // Depth accumulates across the A2A boundary rather than resetting - a remote caller
      // cannot use A2A to bypass the local depth cap (specs/protocols/a2a.md).
      const depth = inboundDepth + 1;
      if (depth > opts.maxDelegationDepth) {
        respondJson(res, 429, { error: `delegation depth ${depth} exceeds this server's cap ${opts.maxDelegationDepth}` });
        return;
      }

      validateAgentTask(body);
      const task = body as unknown as AgentTask;
      const result = await runSubagent({
        task,
        model: opts.model,
        harness: opts.harness,
        runtime: opts.runtime,
        tracer: opts.tracer,
        parentSpanId: null,
        delegationDepth: depth,
      });
      respondJson(res, 200, result);
    } catch (error) {
      respondJson(res, 400, { error: String(error) });
    }
    return;
  }

  respondJson(res, 404, { error: "not found" });
}

function respondJson(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

function readBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolvePromise, reject) => {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      try {
        resolvePromise(raw ? (JSON.parse(raw) as Record<string, unknown>) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}
