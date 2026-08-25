import { randomUUID } from "node:crypto";
import type { TokenUsage } from "../providers/types.js";
import { validateTraceSpan } from "../harness/validate.js";

export interface TraceSpan {
  spanId: string;
  traceId: string;
  parentSpanId: string | null;
  kind: "turn" | "agent" | "model_call" | "tool_call" | "a2a_call";
  name: string;
  agentRole: string | null;
  delegationDepth: number;
  startedAt: string;
  endedAt?: string;
  status: "ok" | "error" | "partial";
  tokenUsage?: TokenUsage;
  attributes?: Record<string, unknown>;
}

/**
 * Nested span tree: turn -> agent -> model/tool call (notes section 11). Default exporter is
 * console-based; swap `onSpanEnd` for an OpenTelemetry exporter in production - the span
 * shape (specs/schemas/trace-span.schema.json) is already OTel-compatible.
 */
export class Tracer {
  readonly traceId = randomUUID();
  private readonly spans: TraceSpan[] = [];

  constructor(private readonly onSpanEnd: (span: TraceSpan) => void = (span) => console.log(`[trace] ${JSON.stringify(span)}`)) {}

  startSpan(kind: TraceSpan["kind"], name: string, opts: { parentSpanId?: string | null; agentRole?: string; delegationDepth?: number } = {}): TraceSpan {
    const span: TraceSpan = {
      spanId: randomUUID(),
      traceId: this.traceId,
      parentSpanId: opts.parentSpanId ?? null,
      kind,
      name,
      agentRole: opts.agentRole ?? null,
      delegationDepth: opts.delegationDepth ?? 0,
      startedAt: new Date().toISOString(),
      status: "ok",
    };
    this.spans.push(span);
    return span;
  }

  endSpan(span: TraceSpan, status: TraceSpan["status"] = "ok", extra: Partial<Pick<TraceSpan, "tokenUsage" | "attributes">> = {}): void {
    span.endedAt = new Date().toISOString();
    span.status = status;
    if (extra.tokenUsage) span.tokenUsage = extra.tokenUsage;
    if (extra.attributes) span.attributes = extra.attributes;
    validateTraceSpan(span);
    this.onSpanEnd(span);
  }

  allSpans(): readonly TraceSpan[] {
    return this.spans;
  }
}
