"""Request rate limiting via slowapi.

`DEFAULT_RATE_LIMIT` (`settings.rate_limit_per_minute`, per minute, per
client IP) is applied via an explicit `@limiter.limit(DEFAULT_RATE_LIMIT)`
decorator on every API route. `POST /auth/login` and `POST /auth/register`
instead carry `AUTH_RATE_LIMIT`, a stricter, fixed limit, to blunt
brute-force/credential-stuffing and registration-spam attempts
specifically, since those are the endpoints an attacker would hammer
without ever needing a valid token. `/healthz` and `/metrics` are
deliberately left undecorated — they're infrastructure-internal
(liveness probes, Prometheus scraping), not user-facing attack surface,
and throttling them risks false "unhealthy" verdicts from orchestrators
that poll them frequently.

Every route needs an explicit decorator rather than relying on
`Limiter(default_limits=[...])` applied automatically via
`SlowAPIASGIMiddleware`: this app's routers are all wired up through
`include_router()`, and slowapi's ASGI middleware resolves the matched
endpoint via `_find_route_handler(app.routes, scope)`, a shallow scan
that only finds routes attached directly to `app` — FastAPI resolves
`include_router()`-mounted routers through an internal `_IncludedRouter`
wrapper that this scan doesn't see into (the same quirk documented in
app.core.middleware._route_template), so `default_limits` would
silently never apply to any of our actual endpoints. The per-route
`@limiter.limit(...)` decorator doesn't have this problem: it checks the
limit inline, inside the endpoint call itself, with no route-lookup step
involved.

Disabled by default under pytest (see tests/conftest.py): the whole
suite shares one client "IP" through httpx's ASGITransport, and this
Limiter is a single process-wide instance, so its hit counters would
accumulate across every test and start rejecting unrelated tests' auth
calls well before the suite finishes. Tests that specifically exercise
rate limiting re-enable it (and reset its counters) for just that test.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

AUTH_RATE_LIMIT = "5/minute"
DEFAULT_RATE_LIMIT = f"{get_settings().rate_limit_per_minute}/minute"

limiter = Limiter(key_func=get_remote_address)
