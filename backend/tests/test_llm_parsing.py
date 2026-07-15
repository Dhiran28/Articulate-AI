"""
Tests for response_parser.parse_json_response and
schema_validator.validate_schema (Sprint 4.4) — the two-stage
parse-then-validate pipeline.

See tests/README.md for how this file fits into the overall suite.
"""

import pytest
from pydantic import BaseModel

from app.llm.errors import LLMInvalidResponseError, LLMSchemaError
from app.llm.response_parser import parse_json_response
from app.llm.schema_validator import validate_schema


class _ExampleSchema(BaseModel):
    label: str
    explanation: str


class TestParseJsonResponse:
    def test_parses_plain_json(self) -> None:
        result = parse_json_response('{"label": "clear", "explanation": "fine"}')
        assert result == {"label": "clear", "explanation": "fine"}

    def test_strips_a_markdown_json_code_fence(self) -> None:
        raw = '```json\n{"label": "clear", "explanation": "fine"}\n```'
        result = parse_json_response(raw)
        assert result == {"label": "clear", "explanation": "fine"}

    def test_strips_a_bare_code_fence_without_json_tag(self) -> None:
        raw = '```\n{"label": "clear", "explanation": "fine"}\n```'
        result = parse_json_response(raw)
        assert result == {"label": "clear", "explanation": "fine"}

    def test_malformed_json_raises_llm_invalid_response_error(self) -> None:
        with pytest.raises(LLMInvalidResponseError) as exc_info:
            parse_json_response("this is not json at all {")

        assert exc_info.value.raw_response == "this is not json at all {"

    def test_valid_json_that_is_not_an_object_is_rejected(self) -> None:
        with pytest.raises(LLMInvalidResponseError):
            parse_json_response('["not", "an", "object"]')

        with pytest.raises(LLMInvalidResponseError):
            parse_json_response('"just a string"')

    def test_never_force_repairs_broken_json(self) -> None:
        # Trailing comma, a common LLM slip-up — must be rejected, not
        # silently "fixed" into something that might not reflect what
        # the model actually meant to say.
        with pytest.raises(LLMInvalidResponseError):
            parse_json_response('{"label": "clear",}')


class TestValidateSchema:
    def test_valid_data_returns_a_populated_instance(self) -> None:
        result = validate_schema({"label": "clear", "explanation": "fine"}, _ExampleSchema)
        assert isinstance(result, _ExampleSchema)
        assert result.label == "clear"

    def test_missing_field_raises_llm_schema_error(self) -> None:
        with pytest.raises(LLMSchemaError) as exc_info:
            validate_schema({"label": "clear"}, _ExampleSchema)

        assert exc_info.value.details["validation_errors"]
        assert any(e["loc"] == ("explanation",) for e in exc_info.value.details["validation_errors"])

    def test_wrong_type_raises_llm_schema_error(self) -> None:
        with pytest.raises(LLMSchemaError):
            validate_schema({"label": 123, "explanation": "fine"}, _ExampleSchema)

    def test_raw_response_is_preserved_on_schema_failure(self) -> None:
        with pytest.raises(LLMSchemaError) as exc_info:
            validate_schema({"label": "clear"}, _ExampleSchema, raw_response='{"label": "clear"}')

        assert exc_info.value.raw_response == '{"label": "clear"}'

    def test_extra_unexpected_fields_do_not_fail_by_default(self) -> None:
        # pydantic's default mode ignores unknown fields rather than
        # rejecting them — a model adding a bonus field the schema
        # doesn't ask for isn't the same failure as a missing field.
        result = validate_schema(
            {"label": "clear", "explanation": "fine", "confidence": 0.9}, _ExampleSchema
        )
        assert result.label == "clear"
