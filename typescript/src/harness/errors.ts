/**
 * Deterministic error classification (notes section 12). The harness - not the model, not a
 * regex on a message string - decides an error's type, and retryability is derived from the
 * type. This is what lets the orchestrator apply the right policy (bounded retry vs. surface-
 * as-final vs. security-log) without ever asking the model "should I retry?".
 */

export type ToolErrorType = "transient" | "permanent" | "validation" | "auth";

export interface ToolError {
  type: ToolErrorType;
  message: string;
  code?: string;
  /** Derived from type - true only for transient. Never set independently. */
  retryable: boolean;
}

/**
 * The harness's Result<T, E> - the typed outcome of a tool call. `ok` carries output;
 * `error` means the tool ran and failed; `rejected` means the harness refused before
 * execution (scope, validation, circuit breaker). Errors are never thrown across the harness
 * boundary into the agent loop - they come back as data the orchestrator can branch on.
 */
export type ToolOutcome = { status: "ok"; output: unknown } | { status: "error" | "rejected"; error: ToolError };

/** Raised by a tool (or the harness) to assert a specific classification rather than relying on heuristics. */
export class ClassifiedError extends Error {
  constructor(
    readonly type: ToolErrorType,
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ClassifiedError";
  }
}

/** validation and auth errors surfaced by the harness's own checks, so they classify precisely. */
export class ValidationFailure extends ClassifiedError {
  constructor(message: string, code?: string) {
    super("validation", message, code);
    this.name = "ValidationFailure";
  }
}

export class AuthFailure extends ClassifiedError {
  constructor(message: string, code?: string) {
    super("auth", message, code);
    this.name = "AuthFailure";
  }
}

const TRANSIENT_CODE = /\b(429|500|502|503|504|522|524|529|ETIMEDOUT|ECONNRESET|ECONNREFUSED|EAI_AGAIN|ENOTFOUND)\b/i;
const TRANSIENT_TEXT = /\b(timeout|timed out|temporarily|rate limit|overloaded|too many requests|try again|unavailable|connection reset)\b/i;
const AUTH_TEXT = /\b(unauthorized|forbidden|permission|not permitted|invalid api key|authentication)\b/i;
const VALIDATION_TEXT = /\b(invalid|malformed|missing required|schema|bad request|must be)\b/i;
const PERMANENT_TEXT = /\b(not found|does not exist|no such|already exists|conflict)\b/i;

/**
 * Best-effort classification of an arbitrary thrown value. Prefer throwing a ClassifiedError
 * from tools/providers where the type is known; this heuristic is the fallback for raw SDK
 * errors and the like. Conservative by design: only clear transient signals become retryable,
 * so an unknown error defaults to permanent (surface-as-final) rather than looping.
 */
export function classifyError(error: unknown): ToolError {
  if (error instanceof ClassifiedError) {
    return { type: error.type, message: error.message, code: error.code, retryable: error.type === "transient" };
  }

  const message = error instanceof Error ? error.message : String(error);
  const status = extractStatus(error);
  const haystack = `${status ?? ""} ${message}`;

  let type: ToolErrorType;
  if (status === 401 || status === 403 || AUTH_TEXT.test(haystack)) {
    type = "auth";
  } else if (status === 429 || (status !== undefined && status >= 500) || TRANSIENT_CODE.test(haystack) || TRANSIENT_TEXT.test(haystack)) {
    type = "transient";
  } else if (status === 400 || status === 422 || VALIDATION_TEXT.test(haystack)) {
    type = "validation";
  } else if (status === 404 || status === 409 || PERMANENT_TEXT.test(haystack)) {
    type = "permanent";
  } else {
    type = "permanent";
  }

  return {
    type,
    message,
    ...(typeof status === "number" ? { code: String(status) } : {}),
    retryable: type === "transient",
  };
}

function extractStatus(error: unknown): number | undefined {
  if (typeof error !== "object" || error === null) return undefined;
  const record = error as Record<string, unknown>;
  for (const key of ["status", "statusCode", "code"]) {
    const value = record[key];
    if (typeof value === "number") return value;
    if (typeof value === "string" && /^\d{3}$/.test(value)) return Number(value);
  }
  return undefined;
}
