import { AuthFailure } from "./errors.js";

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

/** A scope violation is an authorization failure - it classifies as `auth` (no retry, security-logged). */
export class HarnessScopeError extends AuthFailure {}
