import type { ChatModel } from "../providers/types.js";
import type { Harness } from "../harness/index.js";
import type { ToolRuntime } from "../tools/types.js";
import type { Tracer } from "../tracing/tracer.js";
import { runAgent } from "./runAgent.js";
import type { AgentResult } from "./types.js";

export interface RunCitationAgentParams {
  findings: AgentResult[];
  model: ChatModel;
  harness: Harness;
  runtime: ToolRuntime;
  tracer: Tracer;
  runId: string;
  parentSpanId?: string | null;
}

export async function runCitationAgent(params: RunCitationAgentParams): Promise<AgentResult> {
  const findingsText = params.findings
    .map((f) => `[${f.taskId}] (${f.status}) ${f.text}` + (f.artifactRefs.length ? ` refs: ${f.artifactRefs.map((r) => r.artifactId).join(", ")}` : ""))
    .join("\n\n");

  return runAgent({
    roleName: "citation",
    userPrompt: findingsText,
    model: params.model,
    harness: params.harness,
    runtime: params.runtime,
    tracer: params.tracer,
    taskId: `${params.runId}-citation`,
    delegationDepth: 0,
    parentSpanId: params.parentSpanId ?? null,
  });
}
