"""
Schema validation (Sprint 4.4): stage two of the parse-then-validate
pipeline (see response_parser.py for stage one). A response can be
perfectly valid JSON and still be *wrong* — missing a required field, a
field of the wrong type, an unexpected shape — and that's a distinct
failure from "not JSON at all."

Schemas are plain pydantic models, the same tool every other typed shape
in this codebase already uses (AudioAsset, RawTranscriptionResult,
ModuleResult, ...) — no second schema language (e.g. raw JSON Schema +
a `jsonschema` dependency) is introduced just for this one layer.
"""

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .errors import LLMSchemaError

T = TypeVar("T", bound=BaseModel)


def validate_schema(data: dict[str, Any], schema: type[T], *, raw_response: str | None = None) -> T:
    """
    Validates `data` (already-parsed JSON, see response_parser.py)
    against `schema` and returns a populated instance. Never repairs,
    fills in defaults the model doesn't already define, or coerces a
    close-but-wrong shape into passing — a schema mismatch is always a
    loud LLMSchemaError, carrying pydantic's own detailed error list in
    `.details` and the original raw response for debugging.
    """
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise LLMSchemaError(
            f"The provider's response didn't match the expected schema ({schema.__name__}).",
            raw_response=raw_response,
            details={"validation_errors": exc.errors()},
        ) from exc
