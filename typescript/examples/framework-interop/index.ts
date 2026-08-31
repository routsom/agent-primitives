import { Harness, type AgentRoleDef } from "../../src/harness/index.js";
import type { ToolRuntime } from "../../src/tools/types.js";
import { createFrameworkAgentTool } from "./frameworkAgentTool.js";

/**
 * Framework interop: you own the loop; a framework agent plugs in *underneath* it.
 *
 * This boilerplate takes no position that frameworks are bad - they solve real problems. The
 * position is narrower: your orchestration, budgets, error policy, and audit trail should be
 * yours, and a framework agent should sit *below* that line as one governed unit of work, not
 * above it running your control loop. This example proves the line holds by pushing the same
 * foreign agent through the harness three ways and watching the harness - not the framework -
 * decide what happens. Runs offline; no framework dependency (see externalFrameworkAgent.ts).
 */

// A tool call never touches the runtime here (the framework agent doesn't spawn or write
// artifacts in this demo), so a minimal no-op runtime is all the harness needs.
const noRuntime: ToolRuntime = {
  async spawnSubagents() {
    throw new Error("not used in this example");
  },
  async writeArtifact() {
    return {};
  },
  async readArtifact() {
    return {};
  },
  async savePlan() {},
};

// The lead's least-privilege scope: it may call the framework agent. Note framework_agent is
// listed like any native tool - the harness sees no difference between it and search_web.
const leadRole: AgentRoleDef = {
  role: "lead",
  allowedTools: ["framework_agent"],
  canSpawn: ["subagent"],
  maxDelegationDepth: 1,
  budget: { maxToolCalls: 10 },
};

const task = "Compare orchestrator-worker and sequential-pipeline multi-agent topologies.";

async function main() {
  console.log("[framework-interop] a LangGraph/CrewAI-style agent, governed by our harness\n");

  // 1. Happy path: the harness runs the foreign agent and returns a distilled, typed result.
  const harness = new Harness([createFrameworkAgentTool()]);
  const ok = await harness.execute(leadRole, { idempotencyKey: "call-1", toolName: "framework_agent", input: { task }, delegationDepth: 0 }, noRuntime);
  console.log("1) governed call →", JSON.stringify(ok, null, 2));

  // 2. Least-privilege scope: a role without framework_agent in allowedTools is refused BEFORE
  //    the framework ever runs. The framework can't opt itself back in - our harness decides.
  const unscopedRole: AgentRoleDef = { ...leadRole, allowedTools: ["search_web"] };
  const rejected = await harness.execute(unscopedRole, { idempotencyKey: "call-2", toolName: "framework_agent", input: { task }, delegationDepth: 0 }, noRuntime);
  console.log("\n2) scope check →", rejected.status, rejected.status !== "ok" ? `(${rejected.error.type}: ${rejected.error.message})` : "");

  // 3. Deterministic error classification: whatever the framework throws, the HARNESS decides
  //    the type and whether it is retryable - the model is never asked "should I retry?".
  for (const failMode of ["transient", "permanent"] as const) {
    const flaky = new Harness([createFrameworkAgentTool(failMode)]);
    const outcome = await flaky.execute(leadRole, { idempotencyKey: `call-${failMode}`, toolName: "framework_agent", input: { task }, delegationDepth: 0 }, noRuntime);
    if (outcome.status !== "ok") {
      console.log(`\n3) framework threw a ${failMode} error → harness classified it as "${outcome.error.type}", retryable=${outcome.error.retryable}`);
    }
  }

  console.log("\n[framework-interop] The framework ran its own loop inside one tool call. Ours stayed in charge of scope, error policy, and (in a full run) budget, tracing, and audit.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
