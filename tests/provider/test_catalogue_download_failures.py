# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A failed download of a station catalogue is raised, not read as a network without stations (GH-2519).

The values downloads of these networks were made to raise in GH-2461. Their catalogues still logged the failure and
returned an empty frame, so a timeout or a 5xx on the one file listing the stations answered a station request with an
empty result and a success status. Each catalogue is a single required file, so a 404 raises as well, and
`NoInternetError` stays quiet.
"""

import logging
from collections.abc import Callable
from typing import Any

import polars as pl
import pytest

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.dwd.phenology import api as phenology_api
from wetterdienst.provider.dwd.swsmos import api as swsmos_api
from wetterdienst.provider.fmi.observation import api as fmi_api
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.lhmt.observation import api as lhmt_api
from wetterdienst.provider.metoffice.observation import api as metoffice_api
from wetterdienst.provider.metoffice.observation import fileindex as metoffice_fileindex
from wetterdienst.provider.metoffice.observation.metadata import MetOfficeObservationMetadata
from wetterdienst.settings import Settings
from wetterdienst.util.network import File


def _settings() -> Settings:
    return Settings(cache_disable=True)


def _request(request_class: type, **attributes: object) -> Any:  # noqa: ANN401
    """Build a request that holds only what the catalogue under test reads off `self`."""
    request = object.__new__(request_class)
    request.settings = _settings()
    for name, value in attributes.items():
        setattr(request, name, value)
    return request


def _chmi() -> object:
    return _request(chmi_api.ChmiObservationRequest)._all()  # noqa: SLF001


def _fmi() -> object:
    return _request(fmi_api.FmiObservationRequest)._all()  # noqa: SLF001


def _ipma() -> object:
    return _request(ipma_api.IpmaObservationRequest)._all()  # noqa: SLF001


def _lhmt() -> object:
    return _request(lhmt_api.LhmtObservationRequest)._all()  # noqa: SLF001


def _swsmos() -> object:
    return _request(swsmos_api.DwdSwsmosRequest)._all()  # noqa: SLF001


def _phenology() -> object:
    return _request(phenology_api.DwdPhenologyRequest)._stations("annual_reporters")  # noqa: SLF001


def _metoffice_dataset_catalogue(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the catalogue of one MIDAS dataset, the release listing having been read fine."""
    monkeypatch.setattr(metoffice_api, "get_ceda_token", lambda _settings: "token")
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda _settings, _token: "202607")
    dataset = MetOfficeObservationMetadata["daily"].datasets[0]
    return _request(metoffice_api.MetOfficeObservationRequest, parameters=[dataset.parameters[0]])._all()  # noqa: SLF001


def _metoffice_release_listing(monkeypatch: pytest.MonkeyPatch) -> object:
    """Read the catalogue of a request whose release listing is the file that fails."""
    monkeypatch.setattr(metoffice_api, "get_ceda_token", lambda _settings: "token")
    dataset = MetOfficeObservationMetadata["daily"].datasets[0]
    return _request(metoffice_api.MetOfficeObservationRequest, parameters=[dataset.parameters[0]])._all()  # noqa: SLF001


def _metoffice_release_version() -> object:
    return metoffice_fileindex.latest_release_version(_settings(), "token")


# (id, the modules whose `download_file` serves the failure, driver)
_SITES = [
    pytest.param([chmi_api], lambda _mp: _chmi(), id="chmi"),
    pytest.param([fmi_api], lambda _mp: _fmi(), id="fmi"),
    pytest.param([ipma_api], lambda _mp: _ipma(), id="ipma"),
    pytest.param([lhmt_api], lambda _mp: _lhmt(), id="lhmt"),
    pytest.param([swsmos_api], lambda _mp: _swsmos(), id="dwd/swsmos"),
    pytest.param([phenology_api], lambda _mp: _phenology(), id="dwd/phenology"),
    pytest.param([metoffice_api], _metoffice_dataset_catalogue, id="metoffice/catalogue"),
    pytest.param([metoffice_fileindex], lambda _mp: _metoffice_release_version(), id="metoffice/release-listing"),
    pytest.param([metoffice_fileindex], _metoffice_release_listing, id="metoffice/release-listing-in-catalogue"),
]


def _gives_nothing(result: object) -> bool:
    """Say whether a site's answer holds no data: `None`, or a frame without rows."""
    if result is None:
        return True
    assert isinstance(result, (pl.DataFrame, pl.LazyFrame)), type(result)
    frame = result.collect() if isinstance(result, pl.LazyFrame) else result
    return frame.is_empty()


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[Any], Exception, int], None]:
    """Make every download of the given provider modules answer with a failure."""

    def serve(modules: list[Any], error: Exception, status: int) -> None:
        def download_file(*, url: str, **_: object) -> File:
            return File(url=url, content=error, status=status)

        for module in modules:
            monkeypatch.setattr(module, "download_file", download_file)

    return serve


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(TimeoutError(), 408, id="timeout"),
        pytest.param(OSError("503 Service Unavailable"), 503, id="server-error"),
        pytest.param(FileNotFoundError("404 Not Found"), 404, id="not-found"),
    ],
)
@pytest.mark.parametrize(("modules", "driver"), _SITES)
def test_a_failed_catalogue_download_is_raised(
    serve: Callable[[list[Any], Exception, int], None],
    monkeypatch: pytest.MonkeyPatch,
    modules: list[Any],
    driver: Callable[[pytest.MonkeyPatch], object],
    error: Exception,
    status: int,
) -> None:
    """A timeout, a 5xx or a 404 raises, where it used to read as a network without stations."""
    serve(modules, error, status)

    with pytest.raises(DownloadError) as excinfo:
        driver(monkeypatch)

    assert excinfo.value.__cause__ is error


@pytest.mark.parametrize(("modules", "driver"), _SITES)
def test_no_connection_at_all_stays_quiet(
    serve: Callable[[list[Any], Exception, int], None],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    modules: list[Any],
    driver: Callable[[pytest.MonkeyPatch], object],
) -> None:
    """A `NoInternetError` gives no stations and no warning, so working offline still returns empty.

    The catalogues used to warn here as for any failure; `raise_if_exception` logs it at debug, as `dmi` and `rmi` do.
    """
    serve(modules, NoInternetError("offline"), 503)
    caplog.set_level(logging.WARNING)

    assert _gives_nothing(driver(monkeypatch))
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
