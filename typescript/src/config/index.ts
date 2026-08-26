import "dotenv/config";
import type { ProviderName } from "../providers/index.js";

export interface HarnessCaps {
  maxSubagents: number;
  maxDelegationDepth: number;
  maxToolCallsPerSubagent: number;
  /** Session-level token ceiling shared across the whole run (lead + all subagents). 0 = unlimited. */
  maxRunTokens: number;
}

export interface ResilienceConfig {
  timeoutMs: number;
  maxRetries: number;
  baseDelayMs: number;
}

export interface Config {
  defaultProvider: ProviderName;
  caps: HarnessCaps;
  resilience: ResilienceConfig;
  artifactStoreDir: string;
}

function intFromEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function loadConfig(): Config {
  const provider = (process.env["DEFAULT_PROVIDER"] as ProviderName | undefined) ?? "mock";
  return {
    defaultProvider: provider,
    caps: {
      maxSubagents: intFromEnv("MAX_SUBAGENTS", 8),
      maxDelegationDepth: intFromEnv("MAX_DELEGATION_DEPTH", 2),
      maxToolCallsPerSubagent: intFromEnv("MAX_TOOL_CALLS_PER_SUBAGENT", 15),
      maxRunTokens: intFromEnv("MAX_RUN_TOKENS", 250000),
    },
    resilience: {
      timeoutMs: intFromEnv("MODEL_TIMEOUT_MS", 60000),
      maxRetries: intFromEnv("MAX_MODEL_RETRIES", 2),
      baseDelayMs: intFromEnv("RETRY_BASE_DELAY_MS", 500),
    },
    artifactStoreDir: process.env["ARTIFACT_STORE_DIR"] ?? ".artifacts",
  };
}
