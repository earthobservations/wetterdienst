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
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_TOKEN_URL = "https://services.ceda.ac.uk/api/token/create/"  # noqa: S105 -- URL, not a credential


def get_ceda_token(settings: Settings) -> str | None:
    """Mint a fresh CEDA bearer token from the configured (username, password) credentials.

    Returns None (rather than raising) if no credentials are configured or the exchange fails, so
    callers can surface a clear "not authenticated" data gap instead of a hard crash.
    """
    credentials = settings.auth.ceda
    if not credentials:
        log.warning(
            "No CEDA credentials configured. Register a free account at https://services.ceda.ac.uk "
            "and set WD_AUTH__CEDA=<username>:<password> (env var) "
            "or Settings(auth={'ceda': '<username>:<password>'}) (Python).",
        )
        return None
    username, password = credentials
    try:
        response = httpx.post(_TOKEN_URL, auth=(username, password), timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as e:
        log.warning(f"Failed to obtain CEDA access token: {e}")
        return None
    return response.json()["access_token"]
