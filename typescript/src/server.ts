/**
 * Reference production entrypoint: starts the A2A server exposing the subagent role, backed
 * by a real Orchestrator (harness, artifact store, plan memory) rather than the dummy runtime
 * used in tests. This is what deploy/Dockerfile.typescript runs by default - swap it for your
 * own entrypoint (e.g. exposing the lead role, or wiring in your own HTTP API) as needed.
 */
import { randomUUID } from "node:crypto";
import { startA2AServer } from "./a2a/server.js";
import { loadConfig } from "./config/index.js";
import { Harness } from "./harness/index.js";
import { Orchestrator } from "./orchestrator/orchestrator.js";
import { resolveProvider } from "./providers/index.js";
import { buildToolRegistry } from "./tools/registry.js";
import { Tracer } from "./tracing/tracer.js";

const config = loadConfig();
const model = resolveProvider(config.defaultProvider);
const harness = new Harness(buildToolRegistry());
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
});

console.log(`[server] provider "${model.provider}" (${model.model}), A2A subagent server listening on ${baseUrl}`);
