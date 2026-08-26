/**
 * Reference production entrypoint: starts the A2A server exposing the subagent role, backed
 * by a real Orchestrator (harness, artifact store, plan memory) rather than the dummy runtime
 * used in tests. This is what deploy/Dockerfile.typescript runs by default - swap it for your
 * own entrypoint (e.g. exposing the lead role, or wiring in your own HTTP API) as needed.
 */
import { randomUUID } from "node:crypto";
import { startA2AServer } from "./a2a/server.js";
import { loadConfig } from "./config/index.js";
import { ConsoleAuditSink, Harness } from "./harness/index.js";
import { Orchestrator } from "./orchestrator/orchestrator.js";
import { resolveResilientModel } from "./providers/index.js";
import { buildToolRegistry } from "./tools/registry.js";
import { Tracer } from "./tracing/tracer.js";

const config = loadConfig();
const model = resolveResilientModel(config.defaultProvider, config.resilience);
// Production path: audit every tool call (100% coverage). Swap ConsoleAuditSink for a
// JsonlAuditSink or your own sink wired to a log pipeline. Examples leave this as the silent
// default (NoopAuditSink) so their trace output stays readable.
const harness = new Harness(buildToolRegistry(), { auditSink: new ConsoleAuditSink() });
const tracer = new Tracer();
const port = Number(process.env["PORT"] ?? 8787);
const baseUrl = process.env["BASE_URL"] ?? `http://localhost:${port}`;

const orchestrator = new Orchestrator({
  model,
  harness,
  tracer,
  caps: config.caps,
  artifactStoreDir: config.artifactStoreDir,
  planMemoryDir: `${config.artifactStoreDir}/plans`,
  runId: randomUUID(),
});

startA2AServer({
  port,
  baseUrl,
  model,
  harness,
  runtime: orchestrator,
  tracer,
  maxDelegationDepth: config.caps.maxDelegationDepth,
  ...(process.env["A2A_AUTH_TOKEN"] ? { authToken: process.env["A2A_AUTH_TOKEN"] } : {}),
  maxRunTokens: config.caps.maxRunTokens,
});

console.log(`[server] provider "${model.provider}" (${model.model}), A2A subagent server listening on ${baseUrl}`);
