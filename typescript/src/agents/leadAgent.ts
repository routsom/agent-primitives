import type { ChatModel } from "../providers/types.js";
import type { Harness, RunBudget } from "../harness/index.js";
import type { ToolRuntime } from "../tools/types.js";
import type { Tracer } from "../tracing/tracer.js";
import { runAgent } from "./runAgent.js";
import type { AgentResult } from "./types.js";

export interface RunLeadAgentParams {
  query: string;
  model: ChatModel;
  harness: Harness;
  runtime: ToolRuntime;
  tracer: Tracer;
  runId: string;
  parentSpanId?: string | null;
  runBudget?: RunBudget;
}

export async function runLeadAgent(params: RunLeadAgentParams): Promise<AgentResult> {
  return runAgent({
    roleName: "lead",
    userPrompt: params.query,
    model: params.model,
    harness: params.harness,
    runtime: params.runtime,
    tracer: params.tracer,
    taskId: params.runId,
    delegationDepth: 0,
    parentSpanId: params.parentSpanId ?? null,
    ...(params.runBudget ? { runBudget: params.runBudget } : {}),
  });
}
