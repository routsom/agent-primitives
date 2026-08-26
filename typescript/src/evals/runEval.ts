import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runLeadAgent } from "../agents/leadAgent.js";
import { loadConfig } from "../config/index.js";
import { Harness, RunBudget } from "../harness/index.js";
import { Orchestrator } from "../orchestrator/orchestrator.js";
import { resolveResilientModel } from "../providers/index.js";
import { buildToolRegistry } from "../tools/registry.js";
import { Tracer } from "../tracing/tracer.js";
import { runJudge } from "./judge.js";

interface SeedTask {
  id: string;
  query: string;
}

const seedTasksPath = resolve(dirname(fileURLToPath(import.meta.url)), "seedTasks.json");
const seedTasks = JSON.parse(readFileSync(seedTasksPath, "utf-8")) as SeedTask[];

/**
 * Runs the seed task set end to end and scores each with the LLM judge. CI-runnable on the
 * mock provider; point DEFAULT_PROVIDER at a real model to eval actual behavior. Start small
 * and early per notes section 10 - this seed set is a starting point, not a finished suite.
 */
async function main() {
  const config = loadConfig();
  const model = resolveResilientModel(config.defaultProvider, config.resilience);
  const harness = new Harness(buildToolRegistry());

  let flagged = 0;

  for (const seed of seedTasks) {
    const runId = randomUUID();
    const tracer = new Tracer(() => {});
    const turnSpan = tracer.startSpan("turn", seed.id);

    const runBudget = new RunBudget(config.caps.maxRunTokens);
    const orchestrator = new Orchestrator({
      model,
      harness,
      tracer,
      caps: config.caps,
      artifactStoreDir: resolve(config.artifactStoreDir, "evals"),
      planMemoryDir: resolve(config.artifactStoreDir, "evals", "plans"),
      runId,
      parentSpanId: turnSpan.spanId,
      runBudget,
    });

    const leadResult = await runLeadAgent({ query: seed.query, model, harness, runtime: orchestrator, tracer, runId, parentSpanId: turnSpan.spanId, runBudget });
    tracer.endSpan(turnSpan, "ok");

    const traceSummary = `${tracer.allSpans().length} spans, kinds: ${[...new Set(tracer.allSpans().map((s) => s.kind))].join(", ")}`;
    const verdict = await runJudge({
      task: seed.query,
      response: leadResult.text,
      traceSummary,
      model,
      harness,
      runtime: orchestrator,
      tracer,
      evalId: `${seed.id}-judge`,
    });

    // Triggered review (notes section 16a): the run's own deterministic review flags force a
    // human-review flag regardless of what the judge concluded - a structural signal (partial
    // completion, an unrecovered error) is a hard trigger, not a soft opinion.
    const forced = leadResult.needsReview;
    const flag = verdict.flag_for_human_review || forced;
    if (flag) flagged++;
    const reason = forced ? ` (FLAGGED - structural: ${leadResult.reviewFlags.join(", ")})` : verdict.flag_for_human_review ? " (FLAGGED by judge)" : "";
    console.log(`[eval] ${seed.id}: ${JSON.stringify(verdict.scores)}${reason}`);
  }

  console.log(`\n[eval] ${seedTasks.length} tasks run, ${flagged} flagged for human review.`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
