export interface AgentRoleDef {
  role: string;
  allowedTools: string[];
  canSpawn: string[];
  maxDelegationDepth: number;
  budget: { maxToolCalls: number; maxSubagents?: number };
}

/** Least-privilege check: a role may only call tools explicitly listed for it (notes section 6-7). */
export function assertToolAllowed(role: AgentRoleDef, toolName: string): void {
  if (!role.allowedTools.includes(toolName)) {
    throw new HarnessScopeError(`role "${role.role}" is not permitted to call tool "${toolName}"`);
  }
}

export function assertCanSpawn(role: AgentRoleDef, targetRole: string): void {
  if (!role.canSpawn.includes(targetRole)) {
    throw new HarnessScopeError(`role "${role.role}" is not permitted to spawn role "${targetRole}"`);
  }
}

export class HarnessScopeError extends Error {}
