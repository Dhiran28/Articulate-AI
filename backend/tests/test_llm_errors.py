"""
Tests for the LLM abstraction layer's error hierarchy (Sprint 4.4).

See tests/README.md for how this file fits into the overall suite.
"""

import pytest

from app.llm.errors import (
    LLMError,
    LLMErrorReason,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMSchemaError,
    LLMTimeoutError,
    NoProviderConfiguredError,
    PromptNotFoundError,
)

_SUBCLASSES = [
    (LLMTimeoutError, LLMErrorReason.LLM_TIMEOUT),
    (LLMProviderError, LLMErrorReason.LLM_PROVIDER_ERROR),
    (LLMInvalidResponseError, LLMErrorReason.LLM_INVALID_RESPONSE),
    (LLMSchemaError, LLMErrorReason.LLM_SCHEMA_ERROR),
    (PromptNotFoundError, LLMErrorReason.PROMPT_NOT_FOUND),
    (NoProviderConfiguredError, LLMErrorReason.NO_PROVIDER_CONFIGURED),
]


class TestErrorHierarchy:
    @pytest.mark.parametrize("error_cls,expected_reason", _SUBCLASSES)
    def test_every_subclass_is_an_llm_error(self, error_cls, expected_reason) -> None:
        instance = error_cls("something went wrong")
        assert isinstance(instance, LLMError)
        assert instance.reason == expected_reason

    @pytest.mark.parametrize("error_cls,_reason", _SUBCLASSES)
    def test_reason_is_fixed_not_caller_supplied(self, error_cls, _reason) -> None:
        # The class itself determines `reason` — nothing in the
        # constructor lets a caller override it, which is what keeps the
        # exception-type-to-reason mapping from ever drifting apart.
        instance = error_cls("message")
        assert instance.reason == error_cls.reason

    def test_carries_message_raw_response_and_details(self) -> None:
        error = LLMSchemaError(
            "bad shape",
            raw_response='{"foo": 1}',
            details={"validation_errors": [{"loc": ["bar"], "msg": "field required"}]},
        )
        assert error.message == "bad shape"
        assert error.raw_response == '{"foo": 1}'
        assert error.details["validation_errors"][0]["msg"] == "field required"
        assert str(error) == "bad shape"

    def test_raw_response_and_details_default_to_empty(self) -> None:
        error = LLMProviderError("boom")
        assert error.raw_response is None
        assert error.details == {}

    def test_a_caller_can_catch_the_base_class_generically(self) -> None:
        for error_cls, _ in _SUBCLASSES:
            with pytest.raises(LLMError):
                raise error_cls("x")
