import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { runSubagent } from "../agents/subagent.js";
import type { AgentTask } from "../agents/types.js";
import { RunBudget, SlidingWindowRateLimiter, validateAgentTask } from "../harness/index.js";
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
  /** Bearer token required on inbound tasks. When unset, auth is disabled (dev only) and a warning is logged. */
  authToken?: string;
  /** Sliding-window rate limit per caller. Defaults to 60 requests / 60s. */
  rateLimit?: { maxRequests: number; windowMs: number };
  /** Per-request session token ceiling. 0 = unlimited. Each inbound task gets its own budget. */
  maxRunTokens?: number;
}

/**
 * Minimal A2A server: publishes an agent card and accepts delegated tasks over HTTP+JSON.
 * Every inbound task is authenticated, rate-limited, validated, and run through the same
 * harness as a local subagent spawn - no shortcut for remote callers (specs/protocols/a2a.md,
 * notes section 7). Auth and rate limiting happen *before* the model runs, so abusive traffic
 * is rejected at near-zero cost (notes section 19).
 */
export function startA2AServer(opts: A2AServerOptions) {
  const card = buildAgentCard("subagent", opts.baseUrl);
  const limit = opts.rateLimit ?? { maxRequests: 60, windowMs: 60_000 };
  const rateLimiter = new SlidingWindowRateLimiter(limit.maxRequests, limit.windowMs);

  if (!opts.authToken) {
    console.warn("[a2a] WARNING: A2A server started with no authToken - inbound tasks are unauthenticated. Set A2A_AUTH_TOKEN in production.");
  }

  const server = createServer((req, res) => {
    void handleRequest(req, res, opts, card, rateLimiter);
  });
  server.listen(opts.port);
  return server;
}

async function handleRequest(
  req: IncomingMessage,
  res: ServerResponse,
  opts: A2AServerOptions,
  card: ReturnType<typeof buildAgentCard>,
  rateLimiter: SlidingWindowRateLimiter,
): Promise<void> {
  // The agent card is public discovery metadata - no auth required, so callers can decide
  // whether to talk to this agent before authenticating.
  if (req.method === "GET" && req.url === "/.well-known/agent.json") {
    respondJson(res, 200, card);
    return;
  }

  if (req.method === "POST" && req.url === "/tasks") {
    // 1. Authenticate before anything else touches the request body.
    const presentedToken = bearerToken(req);
    if (opts.authToken && presentedToken !== opts.authToken) {
      respondJson(res, 401, { error: "unauthorized" });
      return;
    }

    // 2. Rate-limit per caller identity (token when authenticated, else remote address).
    const callerKey = presentedToken ?? req.socket.remoteAddress ?? "anonymous";
    if (!rateLimiter.tryAcquire(callerKey)) {
      respondJson(res, 429, { error: "rate limit exceeded" });
      return;
    }

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
      // Fresh per-request budget: a long-lived server must not accumulate spend across callers.
      const runBudget = new RunBudget(opts.maxRunTokens ?? 0);
      const result = await runSubagent({
        task,
        model: opts.model,
        harness: opts.harness,
        runtime: opts.runtime,
        tracer: opts.tracer,
        parentSpanId: null,
        delegationDepth: depth,
        runBudget,
      });
      respondJson(res, 200, result);
    } catch (error) {
      respondJson(res, 400, { error: String(error) });
    }
    return;
  }

  respondJson(res, 404, { error: "not found" });
}

function bearerToken(req: IncomingMessage): string | undefined {
  const header = req.headers["authorization"];
  if (typeof header !== "string") return undefined;
  const match = /^Bearer (.+)$/.exec(header);
  return match?.[1];
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
