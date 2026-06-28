"""Tests for the LLM retry policy -- which errors are retried, no API key needed."""

import anthropic

from core.llm import RETRYABLE_ERRORS


def test_retryable_includes_transient_errors():
    assert anthropic.RateLimitError in RETRYABLE_ERRORS
    assert anthropic.APIConnectionError in RETRYABLE_ERRORS
    assert anthropic.APITimeoutError in RETRYABLE_ERRORS
    assert anthropic.InternalServerError in RETRYABLE_ERRORS


def test_retryable_excludes_client_errors():
    # Retrying a bad request or an auth failure just wastes time -- fail fast.
    assert anthropic.BadRequestError not in RETRYABLE_ERRORS
    assert anthropic.AuthenticationError not in RETRYABLE_ERRORS
