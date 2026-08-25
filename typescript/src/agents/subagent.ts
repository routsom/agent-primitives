import type { ChatModel } from "../providers/types.js";
import type { Harness } from "../harness/index.js";
import type { ToolRuntime } from "../tools/types.js";
import type { Tracer } from "../tracing/tracer.js";
import { runAgent } from "./runAgent.js";
import type { AgentResult, AgentTask } from "./types.js";

export interface RunSubagentParams {
  task: AgentTask;
  model: ChatModel;
  harness: Harness;
  runtime: ToolRuntime;
  tracer: Tracer;
  parentSpanId?: string | null;
  delegationDepth: number;
}

export async function runSubagent(params: RunSubagentParams): Promise<AgentResult> {
  const extraSystemContext = [
    `Objective: ${params.task.objective}`,
    `Output format: ${params.task.outputFormat}`,
    `Boundaries: ${params.task.boundaries}`,
  ].join("\n");

  return runAgent({
    roleName: "subagent",
    userPrompt: params.task.objective,
    model: params.model,
    harness: params.harness,
    runtime: params.runtime,
    tracer: params.tracer,
    taskId: params.task.taskId,
    delegationDepth: params.delegationDepth,
    parentSpanId: params.parentSpanId,
    extraSystemContext,
    maxTurns: params.task.budget.maxToolCalls + 2,
  });
}
