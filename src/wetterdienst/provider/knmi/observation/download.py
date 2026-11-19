# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The download of KNMI's EDR API: one request, retried where a retry can change the answer."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import stamina

from wetterdienst.util.network import (
    RedirectRefusedError,
    _without_url_secrets,
    _without_url_secrets_in,
    download_file,
)

if TYPE_CHECKING:
    from wetterdienst.metadata.cache import CacheExpiry
    from wetterdienst.settings import Settings
    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

#: The statuses that are answers, which asking again cannot change: a refused request (400, 422, 413), a refused key
#: (401, 403), no data (404) and a quota that is used up (429), which asking again within the retries makes worse.
NON_RETRYABLE_STATUSES = frozenset({400, 401, 403, 404, 413, 422, 429})

RETRY_WAIT_INITIAL_SECONDS = 2
RETRY_WAIT_MAX_SECONDS = 15
RETRY_MAX_RETRIES = 2


class KnmiRetryableError(Exception):
    """Internal signal used to trigger a stamina retry on a retryable KNMI failure."""


def download_with_retry(
    url: str,
    settings: Settings,
    ttl: CacheExpiry,
    *,
    client_kwargs: dict | None = None,
    attempts: int = 1,
) -> File:
    """Download a URL, retrying on a failure that asking again may clear (a dropped connection, a 5xx).

    A modest couple of short-backoff retries, not an attempt to wait out a sustained outage. A failure that
    `download_file` classes as no network (`File.is_no_internet_error`), a refused redirect and the statuses of
    `NON_RETRYABLE_STATUSES` are not retried: they come back as they are, for the caller to answer.

    `attempts` is how often `download_file` asks before it believes a 404, which for the EDR API is "no data" and not a
    file that is being published: one request, as every request is a unit of its quota of 1,000 an hour.
    """
    last_file: File | None = None
    with contextlib.suppress(KnmiRetryableError):
        for attempt in stamina.retry_context(
            on=KnmiRetryableError,
            attempts=RETRY_MAX_RETRIES + 1,
            timeout=None,
            wait_initial=RETRY_WAIT_INITIAL_SECONDS,
            wait_max=RETRY_WAIT_MAX_SECONDS,
        ):
            with attempt:
                last_file = download_file(
                    url=url,
                    cache_dir=settings.cache_dir,
                    ttl=ttl,
                    client_kwargs=client_kwargs if client_kwargs is not None else settings.fsspec_client_kwargs,
                    cache_disable=settings.cache_disable,
                    use_certifi=settings.use_certifi,
                    attempts=attempts,
                )
                # no network is not a blip two more retries clear: report it at once
                if (
                    isinstance(last_file.content, Exception)
                    and not last_file.is_no_internet_error
                    and not isinstance(last_file.content, RedirectRefusedError)
                    and last_file.status not in NON_RETRYABLE_STATUSES
                ):
                    log.warning(
                        f"Retryable KNMI failure (status={last_file.status}) for {_without_url_secrets(url)}: "
                        f"{_without_url_secrets_in(str(last_file.content))}; retrying",
                    )
                    raise KnmiRetryableError(_without_url_secrets(url))
    if last_file is None:
        msg = "unreachable: stamina.retry_context always runs at least once"
        raise AssertionError(msg)
    return last_file
