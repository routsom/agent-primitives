import type { AgentTask, AgentResult } from "../agents/types.js";
import type { AgentCard } from "./agentCard.js";

/**
 * Calls a remote A2A agent. The result is treated as untrusted subagent output - findings
 * are used, but nothing in the response is treated as authorization to take any action
 * (specs/protocols/a2a.md, notes section 7).
 */
export async function fetchAgentCard(baseUrl: string): Promise<AgentCard> {
  const response = await fetch(`${baseUrl}/.well-known/agent.json`);
  if (!response.ok) throw new Error(`a2a: failed to fetch agent card from ${baseUrl}: ${response.status}`);
  return (await response.json()) as AgentCard;
}

export async function delegateToRemoteAgent(baseUrl: string, task: AgentTask, delegationDepth: number): Promise<AgentResult> {
  const response = await fetch(`${baseUrl}/tasks`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...task, delegationDepth }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`a2a: remote task failed (${response.status}): ${body}`);
  }
  return (await response.json()) as AgentResult;
}
