import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { runLeadAgent } from "../../src/agents/leadAgent.js";
import { runCitationAgent } from "../../src/agents/citationAgent.js";
import { loadConfig } from "../../src/config/index.js";
import { Harness, RunBudget } from "../../src/harness/index.js";
import { Orchestrator } from "../../src/orchestrator/orchestrator.js";
import { resolveResilientModel } from "../../src/providers/index.js";
import { buildToolRegistry } from "../../src/tools/registry.js";
import { Tracer } from "../../src/tracing/tracer.js";
import { maybeOpen, writeDashboard } from "../../src/tracing/dashboard.js";
import { startDashboardServer } from "../../src/tracing/dashboardServer.js";
import type { ChatCompletionRequest, ChatModel } from "../../src/providers/types.js";

/** In live mode, add a small latency per model call so even the fast mock run is watchable. */
function withDelay(base: ChatModel, delayMs: number): ChatModel {
  return {
    provider: base.provider,
    model: base.model,
    async complete(req: ChatCompletionRequest) {
      await new Promise((r) => setTimeout(r, delayMs));
      return base.complete(req);
    },
  };
}

/**
 * Full orchestrator-worker flow end to end: a lead agent decomposes the query, spawns
 * parallel subagents (each with an isolated context), and a citation agent synthesizes their
 * distilled findings. Runs on the mock provider with zero API keys; set ANTHROPIC_API_KEY
 * (or OPENAI_API_KEY / GOOGLE_API_KEY with DEFAULT_PROVIDER set accordingly) to use a real
 * model instead.
 */
async function main() {
  const config = loadConfig();
  const runId = randomUUID();
  const live = process.env["PROFILER"] === "live";
  const baseModel = resolveResilientModel(config.defaultProvider, config.resilience);
  const model = live ? withDelay(baseModel, 450) : baseModel;
  // In live mode, keep the console quiet and stream to the dashboard instead.
  const tracer = new Tracer(live ? () => {} : undefined);
  const harness = new Harness(buildToolRegistry());

  console.log(`[research-task] run ${runId} using provider "${model.provider}" (${model.model})`);

  // Live profiler: start the SSE server and open it BEFORE the run, so the gauges fill in real time.
  const server = live
    ? startDashboardServer({ tracer, meta: { runId, tokenBudget: config.caps.maxRunTokens }, port: Number(process.env["PROFILER_PORT"] ?? 8790) })
    : undefined;
  if (server) {
    console.log(`[research-task] ⚡ live profiler → ${server.url} (Ctrl-C to exit)`);
    maybeOpen(server.url);
  }

  const turnSpan = tracer.startSpan("turn", "research-task");
  // One shared token ceiling for the whole run - lead + every subagent + citation count against it.
  const runBudget = new RunBudget(config.caps.maxRunTokens);

  const orchestrator = new Orchestrator({
    model,
    harness,
    tracer,
    caps: config.caps,
    artifactStoreDir: resolve(config.artifactStoreDir),
    planMemoryDir: resolve(config.artifactStoreDir, "plans"),
    runId,
    parentSpanId: turnSpan.spanId,
    runBudget,
  });

  const query = "What are the main tradeoffs between orchestrator-worker and sequential-pipeline multi-agent topologies?";

  const leadResult = await runLeadAgent({
    query,
    model,
    harness,
    runtime: orchestrator,
    tracer,
    runId,
    parentSpanId: turnSpan.spanId,
    runBudget,
  });

  console.log("\n[lead agent result]");
  console.log(leadResult.text);

  // In a real run the lead agent's spawn_subagents tool call already produced findings; this
  // example also demonstrates the citation agent explicitly for clarity.
  const citationResult = await runCitationAgent({
    findings: [leadResult],
    model,
    harness,
    runtime: orchestrator,
    tracer,
    runId,
    parentSpanId: turnSpan.spanId,
    runBudget,
  });

  tracer.endSpan(turnSpan, "ok");

  console.log("\n[citation agent result]");
  console.log(citationResult.text);
  console.log(`\n[research-task] done. ${tracer.allSpans().length} spans recorded, ${runBudget.consumed} tokens spent (ceiling ${config.caps.maxRunTokens || "unlimited"}).`);

  if (server) {
    // Live mode: mark the run done (stops the LIVE pulse) but keep the server up so the
    // dashboard stays interactive. Exit on Ctrl-C.
    server.done();
    console.log("[research-task] run complete - dashboard still live. Press Ctrl-C to exit.");
    process.on("SIGINT", () => {
      server.close();
      process.exit(0);
    });
    await new Promise(() => {});
    return;
  }

  // Default: write the self-contained profiler dashboard for this run and open it (no server).
  const dashPath = writeDashboard(tracer.allSpans(), resolve(config.artifactStoreDir, `dashboard-${runId}.html`), {
    runId,
    tokenBudget: config.caps.maxRunTokens,
  });
  console.log(`[research-task] profiler dashboard → ${dashPath}`);
  maybeOpen(dashPath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
