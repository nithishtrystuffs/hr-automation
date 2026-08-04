"""
Health Check Orchestrator -- periodic reachability/latency monitoring for
every downstream integration used by the onboarding pipeline (Keycloak,
MailU, Snipe-IT, Kimai, OpenKM, Microsoft 365, GLPI), aggregated into the
shape the frontend's System Health panel expects.

Self-contained by design -- this file is the ONLY change; no existing
connector, router, or main.py is touched:

  - Keycloak already exposes integrations/keycloak_connector.py's
    check_keycloak_latency() -- called directly here, unmodified.
  - MailU / Snipe-IT / Kimai / OpenKM connectors don't have a
    check_*_latency() function yet, and Microsoft 365 / GLPI have no
    connector module in this project at all. Rather than edit those
    files (or add two brand-new connector modules) just to add one, the
    equivalent lightweight reachability probe is implemented once,
    locally, as _ping() below -- same {"status","status_code",
    "latency_ms","error"} contract as check_keycloak_latency() -- and
    reused for every integration that doesn't have its own real check
    function. Existing connectors' own URL constants (MAILU_URL,
    SNIPEIT_URL, KIMAI_URL, OPENKM_URL) are imported and reused rather
    than re-reading the env vars under new names, so there's exactly one
    source of truth per integration's base URL.

Follows agents/monitoring_agent.py's own "not self-registering"
convention: this module exposes a background loop (health_check_loop())
and a cache reader (get_cached_health()) but does not wire itself into
main.py's on_startup() or any router -- see the TODO at the bottom of
this file for the two one-line hookups needed once you're ready to
expose GET /system-health, the same pattern monitoring_agent.py already
leaves open for its own loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import httpx

from app.integrations import (
    keycloak_connector,
    mailu_connector,
    snipeit_connector,
    kimai_connector,
    openkm_connector,
)

logger = logging.getLogger(__name__)

# How often the background loop refreshes the cache. 30 minutes per spec;
# overridable via env var the same way monitoring_agent.py's
# MONITORING_POLL_INTERVAL_SECONDS is.
CHECK_INTERVAL_SECONDS = int(os.getenv("SYSTEM_HEALTH_CHECK_INTERVAL_SECONDS", str(30 * 60)))

_TIMEOUT_SECONDS = 10.0
_DEGRADED_THRESHOLD_MS = 1000  # UP but >= this many ms -> "Degraded", not "Operational"

# Microsoft 365 and GLPI have no connector module in this project (see
# module docstring) -- their base URLs are read directly here, same
# missing-env-var-is-DOWN convention every other integration below uses.
MICROSOFT365_HEALTH_URL = os.getenv("MICROSOFT365_HEALTH_URL", "")
GLPI_URL = os.getenv("GLPI_URL", "")


def _ping(url: str) -> dict:
    """
    Generic reachability probe, identical contract to
    keycloak_connector.check_keycloak_latency(): a plain GET against the
    given base URL, UP only on a 200, DOWN (with latency/error filled in)
    on anything else -- never raises. Used for every integration that
    doesn't have its own real check_*_latency() function (see module
    docstring).
    """
    if not url:
        return {
            "status": "DOWN",
            "status_code": None,
            "latency_ms": 0.0,
            "error": "Integration base URL is not configured",
        }

    start = time.perf_counter()
    try:
        response = httpx.get(url, timeout=_TIMEOUT_SECONDS)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "UP" if response.status_code == 200 else "DOWN",
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "error": None,
        }
    except httpx.RequestError as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "DOWN",
            "status_code": None,
            "latency_ms": latency_ms,
            "error": str(exc),
        }


# Frontend display name -> zero-arg callable returning the
# {"status","status_code","latency_ms","error"} contract. Keycloak's is
# the connector's own real check; the rest fall back to _ping() against
# each connector's already-configured base URL (see module docstring).
_HEALTH_CHECKS: list[tuple[str, Callable[[], dict]]] = [
    ("Keycloak", keycloak_connector.check_keycloak_latency),
    ("MailU", mailu_connector.check_mailu_latency),
    ("Snipe-IT", lambda: _ping(snipeit_connector.SNIPEIT_URL)),
    ("Kimai", lambda: _ping(kimai_connector.KIMAI_URL)),
    ("OpenKM", lambda: _ping(openkm_connector.OPENKM_URL)),
    ("Microsoft 365", lambda: _ping(MICROSOFT365_HEALTH_URL)),
    ("GLPI", lambda: _ping(GLPI_URL)),
]


def _to_frontend_status(result: dict) -> dict:
    """
    Maps one connector-style result into the frontend's
    {"status","latency"} shape, per the fixed rule:
      - connector status != UP     -> "Down", latency "Timeout"
      - UP and latency_ms < 1000   -> "Operational"
      - UP and latency_ms >= 1000  -> "Degraded"
    Nothing here is hardcoded per-integration -- purely a function of the
    connector's own reported status/latency.
    """
    if result.get("status") != "UP":
        return {"status": "Down", "latency": "Timeout"}

    latency_ms = result.get("latency_ms") or 0.0
    status = "Operational" if latency_ms < _DEGRADED_THRESHOLD_MS else "Degraded"
    return {"status": status, "latency": f"{latency_ms:.0f}ms"}


def _run_single_check(name: str, check_fn: Callable[[], dict]) -> dict:
    """
    Runs one integration's check function, translating any exception it
    raises (the documented contract is that these never raise, but a
    reused connector -- e.g. one whose _auth()/_require_env() path raises
    on missing credentials -- must not take down the whole sweep) into
    the same DOWN shape _ping() would have returned. Failures are logged,
    not swallowed silently, per the "log failures but continue checking
    remaining integrations" requirement.
    """
    try:
        result = check_fn()
    except Exception as exc:
        logger.error("Health check failed for %s: %s", name, exc)
        result = {"status": "DOWN", "status_code": None, "latency_ms": 0.0, "error": str(exc)}

    return {"name": name, **_to_frontend_status(result)}


def run_health_checks() -> dict:
    """
    Runs every integration's health check concurrently -- a
    ThreadPoolExecutor, since check_keycloak_latency()/_ping() are plain
    blocking httpx calls (consistent with every connector in this
    project, all sync) -- so the slowest integration's own
    _TIMEOUT_SECONDS bounds the whole sweep instead of the sum of all
    seven. Returns the consolidated frontend payload directly; does not
    touch the cache (see refresh_health_cache() for that).
    """
    with ThreadPoolExecutor(max_workers=len(_HEALTH_CHECKS)) as pool:
        futures = [pool.submit(_run_single_check, name, fn) for name, fn in _HEALTH_CHECKS]
        details = [future.result() for future in futures]

    return {"systemHealthDetail": details}


# ----------------------------------------------------------------------
# Cache -- an API layer must only ever read this, never trigger a live
# sweep (see module docstring's TODO #2).
# ----------------------------------------------------------------------

_cache_lock = threading.Lock()
_cached_result: dict | None = None


def get_cached_health() -> dict:
    """
    Returns the latest cached sweep without running a new one. Returns an
    empty-but-valid payload if the background loop hasn't completed its
    first run yet, rather than blocking the caller on a live check.
    """
    with _cache_lock:
        if _cached_result is None:
            return {"systemHealthDetail": []}
        return _cached_result


def refresh_health_cache() -> dict:
    """Runs a fresh sweep and stores it as the new cached result. Called
    by health_check_loop() every CHECK_INTERVAL_SECONDS; also safe to
    call directly (e.g. a manual-refresh admin action) if ever needed."""
    global _cached_result
    result = run_health_checks()
    with _cache_lock:
        _cached_result = result
    return result


async def health_check_loop():
    """
    Background loop: refreshes the cached health sweep every
    CHECK_INTERVAL_SECONDS (default 30 minutes). Same
    asyncio.create_task()-from-main.py's-on_startup() convention as
    agents/monitoring_agent.py's monitoring_loop() -- deliberately NOT
    self-registering, so main.py stays the single place background tasks
    are wired up (see this file's TODO below).

    Unlike monitoring_loop() (which sleeps first), this runs an initial
    sweep immediately so the cache isn't empty for the first 30 minutes
    after the backend starts. The blocking sweep itself runs via
    asyncio.to_thread() so it never stalls the FastAPI event loop while
    waiting on network I/O.
    """
    while True:
        try:
            await asyncio.to_thread(refresh_health_cache)
        except Exception as exc:
            logger.error("[HEALTH CHECK ORCHESTRATOR] Sweep failed: %s", exc)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


# TODO (wiring -- deliberately not done in this change; this file is the
# only file touched, per instruction). Once you're ready to expose this:
#   1. main.py's on_startup(): add
#        from app.orchestrators import health_check_orchestrator
#        asyncio.create_task(health_check_orchestrator.health_check_loop())
#      same pattern as agents/monitoring_agent.py's own (currently also
#      unwired) monitoring_loop().
#   2. A GET /system-health endpoint (e.g. in routers/monitoring.py, or a
#      new router) whose body is just
#        return health_check_orchestrator.get_cached_health()
#      -- must call get_cached_health(), never run_health_checks() /
#      refresh_health_cache() directly, per the caching requirement.
