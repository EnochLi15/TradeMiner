from __future__ import annotations

from typing import Any


def validate_strategy_params(
    definitions: dict[str, Any],
    provided: dict[str, Any],
) -> dict[str, Any]:
    unknown = set(provided) - set(definitions)
    if unknown:
        raise ValueError(f"Unknown strategy parameter: {sorted(unknown)[0]}")

    validated: dict[str, Any] = {}
    for name, definition in definitions.items():
        if not isinstance(definition, dict):
            raise ValueError(f"{name} definition must be an object")
        value = provided.get(name, definition.get("default"))
        if value is None:
            raise ValueError(f"{name} is required")

        param_type = definition.get("type", "str")
        coerced = _coerce_value(name, value, param_type)
        _validate_bounds(name, coerced, definition)
        validated[name] = coerced

    return validated


def _coerce_value(name: str, value: Any, param_type: str) -> Any:
    if param_type == "int":
        if isinstance(value, bool):
            raise ValueError(f"{name} must be an int")
        try:
            return int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{name} must be an int") from error
    if param_type == "float":
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a float")
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{name} must be a float") from error
    if param_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError(f"{name} must be a bool")
    if param_type == "str":
        return str(value)
    raise ValueError(f"{name} has unsupported type {param_type}")


def _validate_bounds(name: str, value: Any, definition: dict[str, Any]) -> None:
    if "min" in definition and value < definition["min"]:
        raise ValueError(f"{name} must be >= {definition['min']}")
    if "max" in definition and value > definition["max"]:
        raise ValueError(f"{name} must be <= {definition['max']}")
