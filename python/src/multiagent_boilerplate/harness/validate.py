"""Minimal structural validator for the flat JSON Schemas in specs/schemas.

Deliberately not a full JSON Schema engine (no $ref/oneOf resolution) - mirrors
harness/validate.ts in the TypeScript runtime so both runtimes enforce the same contracts
without pulling in a full validation library for three flat, mostly-one-level-deep schemas.
"""

from __future__ import annotations

from typing import Any

from .schemas import load_schema


class SchemaValidationError(Exception):
    def __init__(self, schema_file: str, path: str, message: str) -> None:
        super().__init__(f'schema validation failed for {schema_file} at "{path}": {message}')


def _matches_type(type_name: str, data: Any) -> bool:
    if type_name == "object":
        return isinstance(data, dict)
    if type_name == "array":
        return isinstance(data, list)
    if type_name == "string":
        return isinstance(data, str)
    if type_name == "integer":
        return isinstance(data, int) and not isinstance(data, bool)
    if type_name == "number":
        return isinstance(data, (int, float)) and not isinstance(data, bool)
    if type_name == "boolean":
        return isinstance(data, bool)
    if type_name == "null":
        return data is None
    return True


def _check(schema: dict, data: Any, path: str, schema_file: str) -> None:
    enum = schema.get("enum")
    if enum is not None and data not in enum:
        raise SchemaValidationError(schema_file, path, f"expected one of {enum!r}, got {data!r}")

    schema_type = schema.get("type")
    types = schema_type if isinstance(schema_type, list) else ([schema_type] if schema_type else [])
    if types and not any(_matches_type(t, data) for t in types):
        raise SchemaValidationError(schema_file, path, f"expected type {'|'.join(types)}, got {type(data).__name__}")

    if schema_type == "object" and isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                raise SchemaValidationError(schema_file, path, f'missing required property "{key}"')
        for key, prop_schema in schema.get("properties", {}).items():
            if key in data:
                _check(prop_schema, data[key], f"{path}.{key}", schema_file)

    if schema_type == "array" and isinstance(data, list) and "items" in schema:
        for i, item in enumerate(data):
            _check(schema["items"], item, f"{path}[{i}]", schema_file)


def validate_against(schema_file: str, data: Any) -> None:
    _check(load_schema(schema_file), data, "$", schema_file)


def validate_agent_task(data: Any) -> None:
    validate_against("agent-task.schema.json", data)


def validate_artifact_ref(data: Any) -> None:
    validate_against("artifact-ref.schema.json", data)


def validate_trace_span(data: Any) -> None:
    validate_against("trace-span.schema.json", data)
