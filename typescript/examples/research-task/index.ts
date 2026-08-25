import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { runLeadAgent } from "../../src/agents/leadAgent.js";
import { runCitationAgent } from "../../src/agents/citationAgent.js";
import { loadConfig } from "../../src/config/index.js";
import { Harness } from "../../src/harness/index.js";
import { Orchestrator } from "../../src/orchestrator/orchestrator.js";
import { resolveProvider } from "../../src/providers/index.js";
import { buildToolRegistry } from "../../src/tools/registry.js";
import { Tracer } from "../../src/tracing/tracer.js";

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
  const model = resolveProvider(config.defaultProvider);
  const tracer = new Tracer();
  const harness = new Harness(buildToolRegistry());

  console.log(`[research-task] run ${runId} using provider "${model.provider}" (${model.model})`);

  const turnSpan = tracer.startSpan("turn", "research-task");

  const orchestrator = new Orchestrator({
    model,
    harness,
    tracer,
    caps: config.caps,
    artifactStoreDir: resolve(config.artifactStoreDir),
    planMemoryDir: resolve(config.artifactStoreDir, "plans"),
    runId,
    parentSpanId: turnSpan.spanId,
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
  });

  tracer.endSpan(turnSpan, "ok");

  console.log("\n[citation agent result]");
  console.log(citationResult.text);
  console.log(`\n[research-task] done. ${tracer.allSpans().length} spans recorded.`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
