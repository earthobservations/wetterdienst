# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""File index for the MIDAS Open archive on CEDA.

MIDAS Open is published as annual releases tagged ``dataset-version-<version>`` (e.g.
``202607``). The set of releases is discoverable from the archive root listing
(``https://data.ceda.ac.uk/badc/ukmo-midas-open/?json``), which names one
``midas-open-v<version>-md5s.txt`` manifest per release; ``latest_release_version`` reads the newest
version tag from there. Within a release, every dataset shares that same version tag, so the
per-station file URLs are built directly in ``api.py`` from the station-metadata catalogue (county +
slug) rather than by walking the archive tree.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

_ARCHIVE_ROOT = "https://data.ceda.ac.uk/badc/ukmo-midas-open"
_DOWNLOAD_ROOT = "https://dap.ceda.ac.uk/badc/ukmo-midas-open"

_RELEASE_LISTING_URL = f"{_ARCHIVE_ROOT}/?json"
_MANIFEST_NAME_RE = re.compile(r"^midas-open-v(\d{6})-md5s\.txt$")


def _headers(settings: Settings, token: str | None) -> dict:
    headers = dict(settings.fsspec_client_kwargs.get("headers", {}))
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def latest_release_version(settings: Settings, token: str | None) -> str | None:
    """Return the most recent MIDAS Open release version tag, e.g. ``"202607"``."""
    file = download_file(
        url=_RELEASE_LISTING_URL,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.TWELVE_HOURS,
        client_kwargs={**settings.fsspec_client_kwargs, "headers": _headers(settings, token)},
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    if isinstance(file.content, Exception):
        return None
    listing = json.loads(file.content.read())
    versions = [m.group(1) for item in listing.get("items", []) if (m := _MANIFEST_NAME_RE.match(item.get("name", "")))]
    return max(versions) if versions else None


def download_url(path: str) -> str:
    """Build the authenticated-download URL for an archive ``path`` (relative to the archive root)."""
    return f"{_DOWNLOAD_ROOT}/{path}?download=1"
