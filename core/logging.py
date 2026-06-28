"""core/logging.py -- structured (JSON) logging via structlog.

Replaces scattered print() calls with structured events that carry context
(release-note size, affected counts, errors) so the deployed app's logs are
machine-readable instead of free-form strings. Configured lazily on first use.
"""

from __future__ import annotations

import logging
import sys

import structlog

_configured = False


def _configure():
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name="sopatch"):
    global _configured
    if not _configured:
        _configure()
        _configured = True
    return structlog.get_logger(name)
