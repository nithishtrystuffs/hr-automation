"""
Email Agent -- MailU connector. Owns the PDD provisioning item
"Email Account Creation" (all roles).

Integration approach (resolves TODO #1 from the original stub): MailU's
Admin API is reachable over plain REST (POST/GET/DELETE
{MAILU_URL}/api/v1/user[/{email}]), the same endpoints used by the
project's earlier `CreateAndSendMail.create_mailbox` /
`delete_mailbox`. No CLI shell-out needed.

IMPORTANT (unchanged from the original stub, still true): this is a
DIFFERENT system from app/email_client.py. email_client.py sends
NOTIFICATION emails (welcome email, alerts, intimations -- PDD Section
6) via an existing SMTP/IMAP account. This module PROVISIONS a new
mailbox for the employee in MailU -- two unrelated jobs that happen to
both be "email." They are kept separate here on purpose: the reference
implementation's `send_mail()` (plain SMTP) is deliberately NOT ported
into this module, since it isn't part of the MailU provisioning job and
already lives in email_client.py. Merging it in here would reintroduce
the exact duplication the original docstring warned against.

Once a mailbox exists, PDD Section 6.2's I2 ("Mailbox successfully
created" -> Welcome email w/ login instructions, temp password) fires
-- `create_mailbox()`'s return value carries `temp_password` precisely
so the orchestrator can plumb it into the welcome email draft.
"""

from __future__ import annotations

import logging
import os
import secrets
import string
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAILU_URL = os.getenv("MAILU_URL", "").rstrip("/")
MAILU_ADMIN_TOKEN = os.getenv("MAILU_ADMIN_TOKEN", "")

# NOT in the original stub's suggested env vars, but required: the
# reference implementation (CreateAndSendMail.create_mailbox) was
# handed a fully-formed `email` by its caller. Here the orchestrator
# only passes a `desired_local_part` (see
# onboarding_orchestrator.py: mailu_connector.create_mailbox(emp.name,
# emp.email.split("@")[0])), so this connector must own composing the
# full mailbox address itself -- which means it needs to know the
# MailU domain. Add MAILU_DOMAIN to your .env alongside the other two.
MAILU_DOMAIN = os.getenv("MAILU_DOMAIN", "")

_TIMEOUT_SECONDS = 10.0
_DEFAULT_QUOTA_BYTES = 1073741824  # 1 GB, same default as the reference implementation
_TEMP_PASSWORD_LENGTH = 16


class MailUConnectorError(Exception):
    """Raised on any failure talking to MailU (auth, network, 4xx/5xx, ...)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ----------------------------------------------------------------------
# Configuration / auth
# ----------------------------------------------------------------------
#
# Note on token handling: unlike keycloak_connector.py, there is no
# token caching/refresh logic here. MailU's admin API auth is a single
# static bearer token (MAILU_ADMIN_TOKEN) configured on the MailU side
# -- there is no token endpoint to call, nothing expires, and nothing
# to refresh. The "auth" responsibility here is therefore just
# validating the token is configured and attaching it to each request,
# which `_headers()` / `_require_env()` below handle.


def _require_env() -> None:
    missing = [
        name
        for name, value in (
            ("MAILU_URL", MAILU_URL),
            ("MAILU_ADMIN_TOKEN", MAILU_ADMIN_TOKEN),
            ("MAILU_DOMAIN", MAILU_DOMAIN),
        )
        if not value
    ]
    if missing:
        raise MailUConnectorError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {MAILU_ADMIN_TOKEN}",
        "Content-Type": "application/json",
    }


# ----------------------------------------------------------------------
# HTTP transport (sync equivalent of CreateAndSendMail's per-call
# httpx.AsyncClient blocks, consolidated into one helper so every
# caller gets the same error translation -- mirrors keycloak_connector's
# `_request()`, minus the 401-retry, since there's no token to refresh)
# ----------------------------------------------------------------------


def _request(method: str, path: str, *, json: Any = None, params: dict | None = None) -> httpx.Response:
    """
    Perform an authenticated request against the MailU Admin API.

    Any network error or non-2xx response is translated into
    `MailUConnectorError`, same as `create_mailbox`/`delete_mailbox` did
    individually in the reference implementation, just centralized here
    so every caller (create/get/delete) shares one code path.
    """
    _require_env()
    url = f"{MAILU_URL}{path}"

    try:
        response = httpx.request(
            method, url, json=json, params=params, headers=_headers(), timeout=_TIMEOUT_SECONDS
        )
    except httpx.RequestError as exc:
        logger.error("Network error calling MailU (%s %s): %s", method, url, exc)
        raise MailUConnectorError(f"Could not connect to MailU: {exc}") from exc

    if not response.is_success:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text
        logger.error("MailU error: %s %s -> %s | %s", method, url, response.status_code, detail)
        raise MailUConnectorError(
            f"MailU error: {method} {url} -> {response.status_code} | {detail}",
            status_code=response.status_code,
        )

    return response


# ----------------------------------------------------------------------
# Domain logic
# ----------------------------------------------------------------------


def _generate_temp_password(length: int = _TEMP_PASSWORD_LENGTH) -> str:
    """
    Generate a random temporary password for a new mailbox.

    The reference implementation received `password` as an argument
    (generated upstream by KeycloakService); this connector's public
    signature doesn't take one, so it owns generation itself, using
    `secrets` (not `random`) for a cryptographically strong value.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _build_email_address(desired_local_part: str) -> str:
    """
    Compose the full mailbox address from the requested local part and
    the configured MailU domain (e.g. "jdoe" -> "jdoe@example.com").

    Lightly sanitized (lowercased, spaces stripped) since the caller
    passes a raw string derived from an employee's existing email local
    part (see onboarding_orchestrator.py), not a validated username.
    """
    local_part = desired_local_part.strip().lower().replace(" ", "")
    return f"{local_part}@{MAILU_DOMAIN}"

import time


def check_mailu_latency() -> dict:
    """
    Measure MailU API latency and report service health.

    Returns:
    {
        "status": "UP" | "DOWN",
        "status_code": int | None,
        "latency_ms": float,
        "error": str | None
    }

    Never raises MailUConnectorError.
    """

    if not MAILU_URL:
        return {
            "status": "DOWN",
            "status_code": None,
            "latency_ms": 0.0,
            "error": "Missing MAILU_URL environment variable"
        }

    url = f"{MAILU_URL}/api/v1/user"
    start = time.perf_counter()

    try:
        response = httpx.get(
            url,
            headers=_headers(),
            timeout=_TIMEOUT_SECONDS
        )

        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "status": "UP" if response.status_code < 500 else "DOWN",
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "error": None
        }

    except httpx.RequestError as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "status": "DOWN",
            "status_code": None,
            "latency_ms": latency_ms,
            "error": str(exc)
        }


def _create_mailu_user(email: str, password: str, display_name: str) -> None:
    """
    Create the MailU mailbox itself. Direct port of
    CreateAndSendMail.create_mailbox's payload/endpoint, made sync and
    raising MailUConnectorError instead of the Keycloak-specific
    exceptions the reference implementation borrowed for convenience.
    """
    payload = {
        "email": email,
        "raw_password": password,
        "display_name": display_name,
        "quota_bytes": _DEFAULT_QUOTA_BYTES,
        "enabled": True,
    }

    logger.info("Creating MailU mailbox email=%s", email)
    _request("POST", "/api/v1/user", json=payload)
    logger.info("Created MailU mailbox email=%s", email)


def _get_mailu_user(email: str) -> dict:
    """Return a single MailU mailbox's representation by address."""
    response = _request("GET", f"/api/v1/user/{email}")
    return response.json()


# ----------------------------------------------------------------------
# Public connector interface
# ----------------------------------------------------------------------


def create_mailbox(employee_name: str, desired_local_part: str) -> dict:
    """
    Create a MailU mailbox for a newly onboarded employee.

    - Composes the full address from `desired_local_part` + MAILU_DOMAIN.
    - Generates a temporary password (MailU has no separate invite/
      reset-link flow exposed here, so this connector owns it, same
      resolution the original TODO #... left open).
    - Returns {"external_ref": "<email-address>", "email_address": "...",
      "temp_password": "...", "detail": "..."}.
    - Raises MailUConnectorError on any failure (auth, network,
      duplicate mailbox, etc.) -- never swallowed.

    Called from: app/orchestrators/onboarding_orchestrator.py, via
    _PROVISIONING_CALLS["email"].
    """
    try:
        email = _build_email_address(desired_local_part)
        password = _generate_temp_password()

        _create_mailu_user(email, password, employee_name)

        return {
            "external_ref": email,
            "email_address": email,
            "temp_password": password,
            "detail": "Mailbox created.",
        }
    except MailUConnectorError:
        raise
    except Exception as exc:
        raise MailUConnectorError(f"Failed to create MailU mailbox: {exc}") from exc


def get_mailbox_status(external_ref: str) -> dict:
    """
    Look up a previously-created MailU mailbox by address.

    Returns {"exists": bool, "enabled": bool}. A 404 from MailU is
    reported as {"exists": False, "enabled": False} rather than an
    error, same convention as keycloak_connector.get_user_status; any
    other failure raises MailUConnectorError.

    Used by the Monitoring Agent's polling loop.
    """
    try:
        mailbox = _get_mailu_user(external_ref)
        return {"exists": True, "enabled": bool(mailbox.get("enabled", False))}
    except MailUConnectorError as exc:
        if exc.status_code == 404:
            return {"exists": False, "enabled": False}
        raise
    except Exception as exc:
        raise MailUConnectorError(f"Failed to fetch MailU mailbox status: {exc}") from exc


def delete_mailbox(email: str) -> None:
    """
    Delete a MailU mailbox.

    Public (not a private helper) because, as in the reference
    implementation, this is called directly by the orchestrator to roll
    back a mailbox already created by `create_mailbox()` when a *later*
    onboarding step fails (e.g. Keycloak user creation fails after the
    mailbox was already provisioned).

    Rollback failures are logged but never raised -- same rationale as
    the reference implementation: a failed rollback must not mask the
    original error that triggered it.
    """
    logger.info("Rolling back MailU mailbox email=%s", email)
    try:
        _request("DELETE", f"/api/v1/user/{email}")
        logger.info("Rolled back MailU mailbox email=%s", email)
    except MailUConnectorError as exc:
        logger.error("Failed to roll back MailU mailbox email=%s: %s", email, exc)
