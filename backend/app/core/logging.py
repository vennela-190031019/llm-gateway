"""Structured logging configuration.

Uses structlog to emit JSON logs in production and pretty console output
in development. Sensitive fields (API keys, authorization headers) must
never be passed to log calls — see api middleware for redaction.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

# Substrings, not exact keys: an exact-match set only catches a literal
# key named e.g. "token", and silently misses every reasonably-named
# variation actual code tends to use — access_token, refresh_token,
# hashed_password, client_secret, jwt_secret_key, openai_api_key, and so
# on. Matching "password"/"token"/"secret"/"api_key"/"authorization" as
# substrings of the (lowercased) key catches all of those by construction,
# for every module that ever binds a log field, present or future.
_REDACTED_MARKERS = ("password", "token", "secret", "api_key", "authorization")


def _redact_sensitive(
    _logger: object, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        lowered = key.lower()
        if any(marker in lowered for marker in _REDACTED_MARKERS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(log_level: str = "INFO", json_logs: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_sensitive,
        # Renders an `exc_info=<exception>` kwarg into a formatted
        # `exception` string field. Without this, passing exc_info would
        # leave a raw (type, value, traceback) tuple in the event dict,
        # which isn't JSON-serializable and would break the log call
        # itself — needed for the global exception handler (app.main),
        # which logs full details server-side this way.
        structlog.processors.format_exc_info,
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
