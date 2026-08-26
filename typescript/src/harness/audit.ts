import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { ToolError } from "./errors.js";

/**
 * The audit log is NOT the eval trace (notes section 12, 22). Two separate streams that share
 * correlation IDs but have different retention, access control, and completeness guarantees:
 *
 *   - Audit  (this file): 100% of tool calls, PII-redacted params, for compliance and
 *              forensics. Queryable by session or customer. An independent record of what the
 *              system actually did - not reliant on what the model claims happened.
 *   - Trace  (tracing/tracer.ts): spans for quality measurement, sampled, async.
 *
 * Every tool call routes through Harness.execute, which is the single 100%-coverage chokepoint
 * where these entries are emitted.
 */
export interface AuditCorrelation {
  traceId: string;
  sessionId: string;
  requestId: string;
}

export interface AuditEntry extends AuditCorrelation {
  timestamp: string;
  agentRole: string;
  toolName: string;
  idempotencyKey: string;
  delegationDepth: number;
  /** Tool input with sensitive values redacted at the point of logging (never raw). */
  paramsRedacted: Record<string, unknown>;
  resultStatus: "ok" | "error" | "rejected";
  errorType?: ToolError["type"];
}

export interface AuditSink {
  record(entry: AuditEntry): void;
}

/** Silent default - audit is opt-in for the boilerplate. Wire a real sink in production. */
export class NoopAuditSink implements AuditSink {
  record(): void {}
}

export class ConsoleAuditSink implements AuditSink {
  record(entry: AuditEntry): void {
    console.log(`[audit] ${JSON.stringify(entry)}`);
  }
}

/** Appends one JSON line per tool call - the shape any log pipeline (Splunk/Datadog/Loki) ingests. */
export class JsonlAuditSink implements AuditSink {
  constructor(private readonly filePath: string) {
    mkdirSync(dirname(filePath), { recursive: true });
  }
  record(entry: AuditEntry): void {
    appendFileSync(this.filePath, JSON.stringify(entry) + "\n", "utf-8");
  }
}

const SENSITIVE_KEY = /(token|password|secret|api[_-]?key|authorization|ssn|card|cvv|email|amount|balance)/i;

/**
 * Redacts sensitive values before they reach the audit log, by key name (notes section 22:
 * "PII-redacted at the point of logging"). Deliberately conservative and deterministic - never
 * an LLM call on the logging path. Deep-walks objects/arrays.
 */
export function redact(value: unknown, keyHint = ""): unknown {
  if (SENSITIVE_KEY.test(keyHint)) return "[redacted]";
  if (Array.isArray(value)) return value.map((v) => redact(v));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) out[k] = redact(v, k);
    return out;
  }
  return value;
}
