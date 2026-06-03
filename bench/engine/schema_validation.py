from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class SchemaValidationError(ValueError):
    pass


def load_schema(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(instance: Any, schema: dict[str, Any], root: dict[str, Any] | None = None, path: str = "$") -> None:
    root = schema if root is None else root
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise SchemaValidationError(f"{path}: external refs are not supported: {ref}")
        target: Any = root
        for part in ref[2:].split("/"):
            target = target[part]
        validate(instance, target, root, path)
        return

    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                validate(instance, option, root, path)
                return
            except SchemaValidationError as exc:
                errors.append(str(exc))
        raise SchemaValidationError(f"{path}: did not match any allowed schema: {errors[0] if errors else ''}")

    if "allOf" in schema:
        for option in schema["allOf"]:
            validate(instance, option, root, path)
        return

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaValidationError(f"{path}: {instance!r} not in enum {schema['enum']!r}")

    expected = schema.get("type")
    if expected:
        if expected == "object":
            if not isinstance(instance, dict):
                raise SchemaValidationError(f"{path}: expected object")
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    raise SchemaValidationError(f"{path}: missing required key {key!r}")
            properties = schema.get("properties", {})
            if schema.get("additionalProperties") is False:
                extra = set(instance) - set(properties)
                if extra:
                    raise SchemaValidationError(f"{path}: unexpected keys {sorted(extra)!r}")
            additional = schema.get("additionalProperties")
            for key, value in instance.items():
                if key in properties:
                    validate(value, properties[key], root, f"{path}.{key}")
                elif isinstance(additional, dict):
                    validate(value, additional, root, f"{path}.{key}")
            return
        if expected == "array":
            if not isinstance(instance, list):
                raise SchemaValidationError(f"{path}: expected array")
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if min_items is not None and len(instance) < min_items:
                raise SchemaValidationError(f"{path}: expected at least {min_items} items")
            if max_items is not None and len(instance) > max_items:
                raise SchemaValidationError(f"{path}: expected at most {max_items} items")
            item_schema = schema.get("items")
            if item_schema:
                for index, value in enumerate(instance):
                    validate(value, item_schema, root, f"{path}[{index}]")
            return
        if expected == "string" and not isinstance(instance, str):
            raise SchemaValidationError(f"{path}: expected string")
        if expected == "integer" and not (isinstance(instance, int) and not isinstance(instance, bool)):
            raise SchemaValidationError(f"{path}: expected integer")
        if expected == "number" and not (
            (isinstance(instance, int) or isinstance(instance, float)) and not isinstance(instance, bool)
        ):
            raise SchemaValidationError(f"{path}: expected number")
        if expected == "boolean" and not isinstance(instance, bool):
            raise SchemaValidationError(f"{path}: expected boolean")
        if expected == "null" and instance is not None:
            raise SchemaValidationError(f"{path}: expected null")

    if isinstance(instance, str) and "pattern" in schema:
        if re.search(schema["pattern"], instance) is None:
            raise SchemaValidationError(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaValidationError(f"{path}: {instance} below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaValidationError(f"{path}: {instance} above maximum {schema['maximum']}")


def validate_file(instance_path: str | Path, schema_path: str | Path) -> None:
    validate(json.loads(Path(instance_path).read_text(encoding="utf-8")), load_schema(schema_path))
