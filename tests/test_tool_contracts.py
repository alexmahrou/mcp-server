import json

import pytest

from main import mcp
from tool_contract import get_tool_contract_configs, list_safe_tools

ALLOWED_TYPES = {"string", "number", "boolean", "object", "array"}


def _collect_types(schema: dict) -> None:
    """Recursively validate that the schema uses only the allowed JSON types."""

    if not isinstance(schema, dict):
        return

    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        assert schema_type in ALLOWED_TYPES, f"Disallowed type '{schema_type}'"
    elif isinstance(schema_type, list):
        raise AssertionError(f"Union types are not allowed: {schema_type}")

    if "oneOf" in schema or "anyOf" in schema or "allOf" in schema:
        raise AssertionError("Union schemas (oneOf/anyOf/allOf) are not allowed")

    for value in schema.values():
        if isinstance(value, dict):
            _collect_types(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _collect_types(item)


def test_tool_schemas_are_codex_compatible():
    tool_manager = mcp._tool_manager  # pylint: disable=protected-access

    for tool in tool_manager.list_tools():
        schema = tool.parameters
        assert schema["type"] == "object", f"Tool {tool.name} must declare an object input"
        assert schema.get("additionalProperties") is False, (
            f"Tool {tool.name} must forbid additional properties"
        )

        properties = schema.get("properties", {})
        if properties:
            required = schema.get("required")
            assert isinstance(required, list) and required, (
                f"Tool {tool.name} must declare required fields"
            )
            for field in required:
                assert field in properties, (
                    f"Tool {tool.name} lists unknown required field '{field}'"
                )

        _collect_types(schema)


@pytest.mark.asyncio
async def test_safe_tools_smoke_and_serialization():
    configs = get_tool_contract_configs()
    safe_tool_names = list_safe_tools()
    assert safe_tool_names, "At least one safe tool should be registered for smoke tests"

    for name in safe_tool_names:
        config = configs[name]
        payload = dict(config.defaults)

        unstructured, structured = await mcp.call_tool(name, payload)
        assert isinstance(unstructured, list), "Unstructured content should be list of ContentBlocks"
        assert isinstance(structured, dict), "Structured response must be a dictionary"
        assert structured.get("success") is True, f"Safe tool {name} should succeed"
        assert isinstance(structured.get("data"), dict), "Tool data must be a dictionary"

        # Ensure the response is JSON serializable and contains no nulls.
        serialized = json.dumps(structured)
        assert "null" not in serialized, "Responses should avoid null values"


@pytest.mark.asyncio
async def test_legacy_model_wrapper_is_supported():
    # Choose the first safe tool and call it using the legacy {"model": {...}} shape.
    safe_tool_names = list_safe_tools()
    assert safe_tool_names, "Expected at least one safe tool"
    tool_name = safe_tool_names[0]
    config = get_tool_contract_configs()[tool_name]

    _, structured = await mcp.call_tool(tool_name, {"model": dict(config.defaults)})
    assert structured.get("success") is True
