"""Central Prometheus metric definitions.

All metrics are defined here so there is a single source of truth and no
duplicate registration errors across modules. Services import the metric
objects they need rather than creating their own.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM requests processed",
    ["model", "provider", "status"],
)

llm_request_latency_seconds = Histogram(
    "llm_request_latency_seconds",
    "Latency of LLM requests in seconds",
    ["model", "provider"],
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens processed",
    ["model", "provider", "type"],  # label values: input, output
)

llm_cost_total = Counter(
    "llm_cost_total",
    "Total estimated cost in USD",
    ["model", "provider"],
)

llm_errors_total = Counter(
    "llm_errors_total",
    "Total number of LLM request errors",
    ["model", "provider", "error_type"],
)

llm_cache_hits_total = Counter(
    "llm_cache_hits_total",
    "Total number of cache hits",
)

llm_cache_misses_total = Counter(
    "llm_cache_misses_total",
    "Total number of cache misses",
)

# HTTP-level metrics — transport-layer traffic (every request handled by
# the app), distinct from the LLM-specific metrics above (only requests
# that actually call an LLM provider).

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Latency of HTTP requests in seconds",
    ["method", "path"],
)
