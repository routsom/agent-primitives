import { loadAgentRole } from "../harness/schemas.js";

export interface AgentCard {
  name: string;
  role: string;
  description: string;
  capabilities: { allowedTools: string[]; maxToolCalls: number };
  url: string;
}

/** Published at /.well-known/agent.json - generated from specs/agents/, so it can never overstate what the agent will do (specs/protocols/a2a.md). */
export function buildAgentCard(roleName: string, baseUrl: string): AgentCard {
  const role = loadAgentRole(roleName) as {
    role: string;
    description: string;
    allowedTools: string[];
    budget: { maxToolCalls: number };
  };
  return {
    name: `agent-primitives:${role.role}`,
    role: role.role,
    description: role.description,
    capabilities: { allowedTools: role.allowedTools, maxToolCalls: role.budget.maxToolCalls },
    url: baseUrl,
  };
}
