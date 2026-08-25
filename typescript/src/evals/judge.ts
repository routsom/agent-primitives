import { runAgent } from "../agents/runAgent.js";
import type { Harness } from "../harness/index.js";
import type { ChatModel } from "../providers/types.js";
import type { ToolRuntime } from "../tools/types.js";
import type { Tracer } from "../tracing/tracer.js";

export interface JudgeScores {
  accuracy: number;
  completeness: number;
  source_quality: number;
  process: number;
  disclosure: number;
}

export interface JudgeVerdict {
  scores: JudgeScores;
  justifications: Record<string, string>;
  flag_for_human_review: boolean;
}

export interface RunJudgeParams {
  task: string;
  response: string;
  traceSummary: string;
  model: ChatModel;
  harness: Harness;
  runtime: ToolRuntime;
  tracer: Tracer;
  evalId: string;
}

/** LLM-as-judge, single call, multi-criteria rubric (notes section 10; specs/prompts/judge.md). */
export async function runJudge(params: RunJudgeParams): Promise<JudgeVerdict> {
  const userPrompt = [
    `Original task: ${params.task}`,
    `Final response: ${params.response}`,
    `Trace summary: ${params.traceSummary}`,
  ].join("\n\n");

  const result = await runAgent({
    roleName: "judge",
    userPrompt,
    model: params.model,
    harness: params.harness,
    runtime: params.runtime,
    tracer: params.tracer,
    taskId: params.evalId,
    delegationDepth: 0,
  });

  try {
    return JSON.parse(result.text) as JudgeVerdict;
  } catch {
    throw new Error(`judge did not return valid JSON: ${result.text}`);
  }
}
