# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""File index for the MIDAS Open archive on CEDA.

Confirmed live against the real archive: MIDAS Open has no single combined station-list file.
Instead, CEDA publishes one flat manifest per annual release --
``https://dap.ceda.ac.uk/badc/ukmo-midas-open/midas-open-v<version>-md5s.txt`` -- listing every
file path (with its md5) across *all* datasets for that release in one ~700k-line text file. All 8
datasets share the same ``dataset-version-<version>`` tag within a release, so one manifest is
enough to index the whole archive: no per-station or per-county directory walking required.

Each station directory (``.../<dataset>/dataset-version-<v>/<county>/<src_id>_<slug>/``) holds a
``*_capability.csv`` (the station's BADC-CSV header block: name, lat/lon, height, operating dates
-- no data rows) plus one ``qc-version-<n>/*_<year>.csv`` per year of data. The capability file is
the cheapest way to get a station's metadata without downloading a full data file.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

_ARCHIVE_ROOT = "https://data.ceda.ac.uk/badc/ukmo-midas-open"
_DOWNLOAD_ROOT = "https://dap.ceda.ac.uk/badc/ukmo-midas-open"

_RELEASE_LISTING_URL = f"{_ARCHIVE_ROOT}/?json"
_MANIFEST_URL_TEMPLATE = f"{_DOWNLOAD_ROOT}/midas-open-v{{version}}-md5s.txt?download=1"

_MANIFEST_NAME_RE = re.compile(r"^midas-open-v(\d{6})-md5s\.txt$")

# ``./data/<dataset>/dataset-version-<version>/<county>/<src_id>_<slug>/[qc-version-<qc>/]<filename>``
_PATH_RE = re.compile(
    r"^\./data/(?P<dataset>[^/]+)/dataset-version-(?P<version>\d+)/(?P<county>[^/]+)/"
    r"(?P<src_id>\d+)_(?P<slug>[^/]+)/(?:qc-version-(?P<qc_version>\d+)/)?(?P<filename>[^/]+)$",
)
_DATA_FILENAME_RE = re.compile(r"_(?P<year>\d{4})\.csv$")

_EMPTY_MANIFEST_SCHEMA = {
    "dataset": pl.String,
    "county": pl.String,
    "station_id": pl.String,
    "station_slug": pl.String,
    "qc_version": pl.Int64,
    "kind": pl.String,
    "year": pl.Int64,
    "path": pl.String,
}


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


def load_manifest(version: str, settings: Settings, token: str | None) -> pl.DataFrame:
    """Download and parse the release-wide file manifest into one row per archive file.

    Cached for twelve hours: the manifest is ~30 MB and only changes once a year, but a token
    that's gone stale mid-session (3-day TTL) should not keep serving a request built with it, so
    this deliberately does not use the long-lived ``METAINDEX`` expiry.
    """
    file = download_file(
        url=_MANIFEST_URL_TEMPLATE.format(version=version),
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.TWELVE_HOURS,
        client_kwargs={**settings.fsspec_client_kwargs, "headers": _headers(settings, token)},
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    if isinstance(file.content, Exception):
        return pl.DataFrame(schema=_EMPTY_MANIFEST_SCHEMA)
    rows = []
    for line in file.content.read().decode("utf-8").splitlines():
        # lines are "<md5>  <path>"; skip the two blank/comment lines files like this sometimes end with
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        match = _PATH_RE.match(parts[1])
        if not match:
            continue
        filename = match.group("filename")
        is_capability = filename.endswith("_capability.csv")
        year_match = _DATA_FILENAME_RE.search(filename)
        rows.append(
            {
                "dataset": match.group("dataset"),
                "county": match.group("county"),
                "station_id": match.group("src_id"),
                "station_slug": match.group("slug"),
                "qc_version": int(match.group("qc_version")) if match.group("qc_version") else None,
                "kind": "capability" if is_capability else "data",
                "year": int(year_match.group("year")) if year_match else None,
                "path": parts[1].removeprefix("./"),
            },
        )
    if not rows:
        return pl.DataFrame(schema=_EMPTY_MANIFEST_SCHEMA)
    return pl.DataFrame(rows, schema=_EMPTY_MANIFEST_SCHEMA)


def download_url(path: str) -> str:
    """Build the authenticated-download URL for a manifest ``path`` entry."""
    return f"{_DOWNLOAD_ROOT}/{path}?download=1"
