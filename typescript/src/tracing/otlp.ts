import type { TraceSpan } from "./tracer.js";

/**
 * Maps a TraceSpan to the OpenTelemetry OTLP/JSON span shape. The span is already
 * OTel-compatible by construction (specs/schemas/trace-span.schema.json) - this just renames
 * fields and encodes attributes into OTLP's key/value form so the output drops straight into
 * any OTLP/HTTP collector.
 *
 * This is the *seam*: it produces the wire shape. Shipping the actual network exporter (gRPC
 * or HTTP to a collector) is left to you deliberately - it depends on your collector endpoint
 * and auth, and pulling in an OTLP transport would be exactly the kind of heavyweight
 * dependency this boilerplate avoids. See docs/extending.md.
 */
export function toOtlpSpan(span: TraceSpan): Record<string, unknown> {
  const attributes = Object.entries({
    "agent.role": span.agentRole,
    "agent.delegation_depth": span.delegationDepth,
    "span.app_kind": span.kind,
    ...(span.tokenUsage ?? {}),
    ...(span.attributes ?? {}),
  })
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([key, value]) => ({ key, value: toAnyValue(value) }));

  return {
    traceId: span.traceId,
    spanId: span.spanId,
    parentSpanId: span.parentSpanId ?? undefined,
    name: span.name,
    startTimeUnixNano: toUnixNano(span.startedAt),
    endTimeUnixNano: span.endedAt ? toUnixNano(span.endedAt) : undefined,
    kind: 1, // SPAN_KIND_INTERNAL
    status: { code: span.status === "error" ? 2 : span.status === "partial" ? 0 : 1 },
    attributes,
  };
}

/** A ready-to-use Tracer sink that prints each span in OTLP/JSON form. */
export function otlpConsoleExporter(span: TraceSpan): void {
  console.log(`[otlp] ${JSON.stringify(toOtlpSpan(span))}`);
}

function toAnyValue(value: unknown): Record<string, unknown> {
  if (typeof value === "number") return Number.isInteger(value) ? { intValue: value } : { doubleValue: value };
  if (typeof value === "boolean") return { boolValue: value };
  return { stringValue: String(value) };
}

function toUnixNano(iso: string): string {
  return `${new Date(iso).getTime()}000000`;
}
