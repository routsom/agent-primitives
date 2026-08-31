/**
 * A stand-in for an agent you already built in someone else's framework - a LangGraph
 * `StateGraph`, a CrewAI `Crew`, an AutoGen team. This boilerplate does NOT depend on any of
 * them (see CLAUDE.md "What not to do"); this file fakes one so the example runs offline.
 *
 * The point of the example is the *boundary*, not this code: in a real project the body of
 * `invoke` would be
 *
 *   import { StateGraph } from "@langchain/langgraph";
 *   const graph = new StateGraph(...).compile();
 *   return await graph.invoke({ input });
 *
 * ...and everything in frameworkAgentTool.ts around it would be unchanged. The framework owns
 * its own internal control loop; we treat the whole thing as one opaque, governed call.
 */
export interface ExternalAgentInput {
  task: string;
}

export interface ExternalAgentOutput {
  /** Deliberately verbose - a real framework agent returns a lot of chatter, intermediate
   * steps, and scratch reasoning. Our adapter distills this rather than passing it upward. */
  transcript: string[];
  answer: string;
}

/**
 * Set `failMode` to simulate the two failure shapes an external framework typically throws, so
 * the example can show the harness classifying them deterministically (transient -> retryable,
 * everything else -> surface-as-final). See src/harness/errors.ts.
 */
export async function invokeExternalFrameworkAgent(
  input: ExternalAgentInput,
  failMode?: "transient" | "permanent",
): Promise<ExternalAgentOutput> {
  if (failMode === "transient") throw new Error("503 upstream model temporarily unavailable, please try again");
  if (failMode === "permanent") throw new Error("graph node 'retrieve' does not exist in the compiled workflow");

  return {
    transcript: [
      `[langgraph] node 'plan' -> decomposed task: ${input.task}`,
      "[langgraph] node 'retrieve' -> pulled 7 candidate passages",
      "[langgraph] node 'rank' -> kept top 3 by relevance",
      "[langgraph] node 'write' -> drafted answer, 2 revision loops",
    ],
    answer: `Orchestrator-worker parallelizes independent subtasks and isolates their contexts, at the cost of a fan-in/synthesis step; sequential-pipeline is simpler and cheaper but serializes latency and lets errors compound stage to stage. (answer produced by the external framework agent for: ${input.task})`,
  };
}
