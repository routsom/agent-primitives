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
}
