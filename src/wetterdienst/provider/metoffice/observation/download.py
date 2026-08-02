# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""CEDA authentication for the Met Office MIDAS Open archive.

MIDAS Open files are only reachable with a bearer token (confirmed live: browsing
``data.ceda.ac.uk`` is anonymous, but downloading from ``dap.ceda.ac.uk`` 302-redirects to a login
page without one, and plain HTTP Basic auth against the download host does *not* work either --
CEDA requires the token exchange below). The token is minted from the user's CEDA username/password
(``Settings(auth={"ceda": "username:password"})`` / ``WD_AUTH__CEDA=username:password``) via
CEDA's token API and is a Keycloak-issued JWT, confirmed 3 days validity for both browser- and
API-issued tokens -- there is no refresh endpoint, so an expired token is simply replaced by
minting a new one.

The minted token is cached in-process (keyed by credentials) until shortly before its own ``exp``
claim, so a values query spanning many stations reuses one token instead of hitting CEDA's token
endpoint once per station (which is slow and risks rate-limiting the free account).
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import json
import logging
import threading
import time
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_TOKEN_URL = "https://services.ceda.ac.uk/api/token/create/"  # noqa: S105 -- URL, not a credential

# re-mint this many seconds before the token's own expiry, to avoid handing out a token that expires
# mid-request.
_EXPIRY_MARGIN_SECONDS = 300
# used only if the token's ``exp`` claim can't be read; comfortably under the ~3-day real lifetime.
_FALLBACK_TTL_SECONDS = 3600

# in-process cache: (username, password) -> (token, epoch seconds after which it must be re-minted).
_TOKEN_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
# serialises the check-then-mint so concurrent callers (e.g. the REST API's thread pool) don't each
# mint a redundant token on a cold cache.
_TOKEN_LOCK = threading.Lock()


def _token_valid_until(token: str) -> float:
    """Return the epoch second up to which ``token`` may be reused (its ``exp`` minus a margin).

    Reads the ``exp`` claim from the JWT payload without verifying the signature (the token is used
    as an opaque bearer; CEDA is the authority on validity). Falls back to a short TTL if the token
    is not a readable JWT.
    """
    # TypeError covers a payload that is valid JSON but not a dict (e.g. ``null``/list/number)
    with contextlib.suppress(IndexError, ValueError, TypeError, binascii.Error, json.JSONDecodeError, KeyError):
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)  # restore base64 padding
        exp = json.loads(base64.urlsafe_b64decode(payload_b64))["exp"]
        return float(exp) - _EXPIRY_MARGIN_SECONDS
    return time.time() + _FALLBACK_TTL_SECONDS


def get_ceda_token(settings: Settings) -> str | None:
    """Return a valid CEDA bearer token for the configured (username, password) credentials.

    A cached token is reused while it is still valid; otherwise a fresh one is minted from the
    credentials and cached. Returns None (rather than raising) if no credentials are configured or
    the exchange fails, so callers can surface a clear "not authenticated" data gap instead of a
    hard crash.
    """
    credentials = settings.auth.ceda
    if not credentials:
        log.warning(
            "No CEDA credentials configured. Register a free account at https://services.ceda.ac.uk "
            "and set WD_AUTH__CEDA=<username>:<password> (env var) "
            "or Settings(auth={'ceda': '<username>:<password>'}) (Python).",
        )
        return None
    cached = _TOKEN_CACHE.get(credentials)
    if cached is not None and cached[1] > time.time():
        return cached[0]
    username, password = credentials
    with _TOKEN_LOCK:
        # re-check under the lock: another thread may have minted while we waited
        cached = _TOKEN_CACHE.get(credentials)
        if cached is not None and cached[1] > time.time():
            return cached[0]
        try:
            response = httpx.post(_TOKEN_URL, auth=(username, password), timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as e:
            log.warning(f"Failed to obtain CEDA access token: {e}")
            return None
        try:
            # a 200 with a non-JSON body (e.g. an HTML login/error page) or a JSON body missing the
            # access_token field is an exchange failure, not data -- surface it as "not authenticated"
            token = response.json()["access_token"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning(f"Unexpected CEDA token response: {e}")
            return None
        _TOKEN_CACHE[credentials] = (token, _token_valid_until(token))
        return token
