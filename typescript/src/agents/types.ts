export interface AgentTaskBudget {
  maxToolCalls: number;
  maxDelegationDepth?: number;
}

/** Mirrors specs/schemas/agent-task.schema.json - every field is required deliberately. */
export interface AgentTask {
  taskId: string;
  role: string;
  objective: string;
  outputFormat: string;
  allowedTools: string[];
  boundaries: string;
  budget: AgentTaskBudget;
  parentTaskId?: string | null;
}

export interface AgentResult {
  taskId: string;
  role: string;
  text: string;
  artifactRefs: { artifactId: string; kind: string; summary: string; uri: string }[];
  status: "ok" | "partial" | "error";
  /**
   * Deterministically derived from the run's own trace - NOT an LLM judgment and NOT parsed
   * from prose (notes section 16a). Set when a structural signal (partial completion, an
   * unrecovered tool error, token truncation, an empty answer) means a human or the judge
   * should look at this specific run. Zero extra model calls.
   */
  needsReview: boolean;
  reviewFlags: string[];
}
