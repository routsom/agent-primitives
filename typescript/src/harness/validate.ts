import { loadSchema } from "./schemas.js";

/**
 * Minimal structural validator for the flat JSON Schemas in specs/schemas - deliberately not
 * a full JSON Schema engine (no $ref/oneOf resolution). Three schemas, all flat objects with
 * at most one level of nesting; a hand-rolled ~60 line checker is simpler and has one fewer
 * dependency than pulling in a full validation library for this. If specs/schemas grows more
 * complex, revisit this call.
 */
export class SchemaValidationError extends Error {
  constructor(schemaFile: string, path: string, message: string) {
    super(`schema validation failed for ${schemaFile} at "${path}": ${message}`);
  }
}

type JsonSchema = {
  type?: string | string[];
  required?: string[];
  properties?: Record<string, JsonSchema>;
  items?: JsonSchema;
  enum?: unknown[];
};

function check(schema: JsonSchema, data: unknown, path: string, schemaFile: string): void {
  if (schema.enum && !schema.enum.includes(data)) {
    throw new SchemaValidationError(schemaFile, path, `expected one of ${JSON.stringify(schema.enum)}, got ${JSON.stringify(data)}`);
  }

  const types = Array.isArray(schema.type) ? schema.type : schema.type ? [schema.type] : [];
  if (types.length && !types.some((t) => matchesType(t, data))) {
    throw new SchemaValidationError(schemaFile, path, `expected type ${types.join("|")}, got ${typeof data}`);
  }

  if (schema.type === "object" && data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    for (const key of schema.required ?? []) {
      if (!(key in obj)) throw new SchemaValidationError(schemaFile, path, `missing required property "${key}"`);
    }
    for (const [key, propSchema] of Object.entries(schema.properties ?? {})) {
      if (key in obj) check(propSchema, obj[key], `${path}.${key}`, schemaFile);
    }
  }

  if (schema.type === "array" && Array.isArray(data) && schema.items) {
    data.forEach((item, i) => check(schema.items as JsonSchema, item, `${path}[${i}]`, schemaFile));
  }
}

function matchesType(type: string, data: unknown): boolean {
  switch (type) {
    case "object":
      return typeof data === "object" && data !== null && !Array.isArray(data);
    case "array":
      return Array.isArray(data);
    case "string":
      return typeof data === "string";
    case "integer":
      return typeof data === "number" && Number.isInteger(data);
    case "number":
      return typeof data === "number";
    case "boolean":
      return typeof data === "boolean";
    case "null":
      return data === null;
    default:
      return true;
  }
}

const cache = new Map<string, JsonSchema>();
function getSchema(schemaFile: string): JsonSchema {
  let schema = cache.get(schemaFile);
  if (!schema) {
    schema = loadSchema(schemaFile) as JsonSchema;
    cache.set(schemaFile, schema);
  }
  return schema;
}

export function validateAgainst(schemaFile: string, data: unknown): void {
  check(getSchema(schemaFile), data, "$", schemaFile);
}

export const validateAgentTask = (data: unknown) => validateAgainst("agent-task.schema.json", data);
export const validateArtifactRef = (data: unknown) => validateAgainst("artifact-ref.schema.json", data);
export const validateTraceSpan = (data: unknown) => validateAgainst("trace-span.schema.json", data);
