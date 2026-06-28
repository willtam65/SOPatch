"""core/llm.py -- shared Anthropic client and retry policy.

A single place to create the client and call the model, so a transient failure
(rate limit, 5xx, dropped connection, timeout) is retried with exponential
backoff instead of killing the request. Non-retryable errors (bad request, auth)
are raised immediately -- retrying those just wastes time and tokens.
"""

from __future__ import annotations

import os

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from core.logging import get_logger

log = get_logger("sopatch.llm")

# Transient, worth-retrying failures. A 400/401 is a bug or a config problem,
# so those are deliberately excluded and surface immediately.
RETRYABLE_ERRORS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)


def get_client():
    """Create an Anthropic client from the ANTHROPIC_API_KEY env var."""
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _log_retry(state):
    log.warning(
        "llm.retry",
        attempt=state.attempt_number,
        error=str(state.outcome.exception()),
    )


@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    wait=wait_random_exponential(min=1, max=20),
    stop=stop_after_attempt(4),
    before_sleep=_log_retry,
    reraise=True,
)
def complete(client, **kwargs):
    """Call client.messages.create(**kwargs), retrying on transient errors."""
    return client.messages.create(**kwargs)
