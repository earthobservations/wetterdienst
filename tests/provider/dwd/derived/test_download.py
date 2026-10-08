# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for downloading DWD derived archives."""

import polars as pl
import pytest
from fsspec.exceptions import FSTimeoutError

from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.dwd.derived import download as dwd_derived_download
from wetterdienst.provider.dwd.derived.download import download_climate_derived_data
from wetterdienst.util.network import File

_MISSING = File(url="https://example.invalid/missing.zip", content=FileNotFoundError("missing.zip"), status=404)


@pytest.mark.parametrize(
    "failed",
    [
        pytest.param(File(url="https://example.invalid/a.zip", content=ConnectionError("503"), status=503), id="5xx"),
        pytest.param(File(url="https://example.invalid/a.zip", content=FSTimeoutError(), status=408), id="timeout"),
    ],
)
def test_download_climate_derived_data_raises_a_failed_download(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    failed: File,
) -> None:
    """A download that failed for any reason but a 404 is raised, not dropped as a missing file (GH-2430).

    Dropped, an outage read as a station without data: an empty result with a success status.
    """
    monkeypatch.setattr(dwd_derived_download, "download_files", lambda **_kwargs: [_MISSING, failed])
    with pytest.raises(DownloadError) as caught:
        download_climate_derived_data(pl.Series(["unused"]), default_settings)
    assert caught.value.__cause__ is failed.content


@pytest.mark.parametrize(
    "skipped",
    [
        pytest.param(_MISSING, id="404"),
        pytest.param(
            File(url="https://example.invalid/a.zip", content=NoInternetError("offline"), status=503),
            id="no-internet",
        ),
    ],
)
def test_download_climate_derived_data_drops_a_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    skipped: File,
) -> None:
    """A 404 is a file that is not there, and no connection at all stays an empty result (GH-2430)."""
    monkeypatch.setattr(dwd_derived_download, "download_files", lambda **_kwargs: [skipped])
    assert download_climate_derived_data(pl.Series(["unused"]), default_settings) == []
