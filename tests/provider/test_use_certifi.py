# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that the downloads of a provider go out with the CA bundle `WD_USE_CERTIFI` asks for."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import BUFR_AVAILABLE
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

#: the URL of every download a provider made, beside the `use_certifi` it was made with
Seen = list[tuple[str, object]]

START = dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
END = dt.datetime(2020, 1, 2, tzinfo=ZoneInfo("UTC"))


def _record(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    answer: Callable[[str], File],
) -> Seen:
    """Stand in for the provider's `download_file`, answering each URL and noting how it was asked."""
    seen: Seen = []

    def _download(*, url: str, use_certifi: object = False, **_kwargs: object) -> File:
        seen.append((url, use_certifi))
        return answer(url)

    monkeypatch.setattr(module, "download_file", _download)
    return seen


def _ok(url: str, payload: bytes) -> File:
    return File(url=url, content=BytesIO(payload), status=200)


def _geosphere(monkeypatch: pytest.MonkeyPatch) -> Seen:
    """Request the station list, then one station's values."""
    from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest, api  # noqa: PLC0415

    stations = (
        "id,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,Sonnenschein,Globalstrahlung\n"
        "4821,Test,16.0,48.0,200,1992-05-20 00:00:00+00:00,2100-01-01 00:00:00+00:00,Wien,True,True\n"
    ).encode()

    def answer(url: str) -> File:
        if url.endswith("/metadata/stations"):
            return _ok(url, stations)
        return _ok(url, b'{"timestamps": [], "features": []}')

    seen = _record(monkeypatch, api, answer)
    request = GeosphereObservationRequest(
        parameters=[("10_minutes", "data", "humidity_relative")],
        start=START,
        end=END,
    )
    request.filter_by_station_id("4821").values.all()
    return seen


def _ea(monkeypatch: pytest.MonkeyPatch) -> Seen:
    """Request the station list, then a station's measures, then the readings of one of them."""
    from wetterdienst.provider.ea.hydrology import EAHydrologyRequest  # noqa: PLC0415
    from wetterdienst.provider.ea.hydrology import api as ea_api  # noqa: PLC0415

    measure = {
        "@id": "https://environment.data.gov.uk/hydrology/id/measures/0001-flow-m-86400-m3s-qualified",
        "parameter": "flow",
        "parameterName": "Flow",
        "period": 86400,
    }
    station = {
        "label": "Station 0001",
        "notation": "0001",
        "easting": 400000,
        "northing": 300000,
        "lat": 51.5,
        "long": -1.0,
        "dateOpened": "1990-01-01",
        "dateClosed": None,
        "measures": [measure],
    }
    responses = {
        "https://environment.data.gov.uk/hydrology/id/stations.json": {"items": [station]},
        "https://environment.data.gov.uk/hydrology/id/stations/0001.json": {"items": [{"measures": [measure]}]},
    }
    readings = {"items": [{"dateTime": "2020-01-01T00:00:00", "value": 1.0, "quality": "Good"}]}

    def answer(url: str) -> File:
        return _ok(url, json.dumps(responses.get(url, readings)).encode())

    seen = _record(monkeypatch, ea_api, answer)
    EAHydrologyRequest(parameters=[("daily", "data", "discharge_mean")]).all().values.all()
    return seen


def _metno_frost(monkeypatch: pytest.MonkeyPatch) -> Seen:
    """Request the station list, each way to a station's values, and the credential probe.

    The two fallbacks past the first values request are what a 404 from Frost is to lead to. Each is
    called directly here rather than reached through that 404, as each makes downloads of its own.
    """
    from wetterdienst.provider.metno.frost import MetnoFrostRequest  # noqa: PLC0415
    from wetterdienst.provider.metno.frost import api as frost_api  # noqa: PLC0415

    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    sources = {
        "data": [
            {
                "id": "SN18700",
                "name": "OSLO - BLINDERN",
                "validFrom": "1937-01-01T00:00:00.000Z",
                "geometry": {"coordinates": [10.72, 59.94]},
                "county": "OSLO",
                "countryCode": "NO",
                "masl": 94,
            },
        ],
    }
    available = {
        "data": [
            {
                "validFrom": "2000-01-01T00:00:00Z",
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
            },
        ],
    }

    def answer(url: str) -> File:
        if "/sources/" in url:
            return _ok(url, json.dumps(sources).encode())
        if "/availableTimeSeries/" in url:
            return _ok(url, json.dumps(available).encode())
        # no data for the window, which ends each path without a further request
        return File(url=url, content=FileNotFoundError(url), status=412)

    seen = _record(monkeypatch, frost_api, answer)
    request = MetnoFrostRequest(parameters=[("hourly", "data", "temperature_air_mean_2m")], start=START, end=END)
    values = request.filter_by_station_id("SN18700").values
    values.all()
    parameter = request.parameters[0]
    settings = request.settings
    values._collect_single_parameter("SN18700", parameter, START, END, settings, {})  # noqa: SLF001
    values._collect_via_time_series_discovery("SN18700", parameter, START, END, settings, {})  # noqa: SLF001
    MetnoFrostRequest.is_valid()
    return seen


def _dwd_road(monkeypatch: pytest.MonkeyPatch) -> Seen:
    """Request the files a station group published for the window."""
    from tests.provider.dwd.road.test_api import _stub_stations  # noqa: PLC0415
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    listed = ["https://example.com/road/DD/swis2-ISXD70_DWDD_141915-2609141915-DD---bin"]
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: listed)
    seen: Seen = []

    def _download_files(*, urls: list[str], use_certifi: object = False, **_kwargs: object) -> list[File]:
        seen.extend((url, use_certifi) for url in urls)
        return []

    monkeypatch.setattr(api, "download_files", _download_files)
    _stub_stations().values.all()
    return seen


@pytest.mark.parametrize(
    ("collect", "downloads"),
    [
        pytest.param(_geosphere, 2, id="geosphere"),
        pytest.param(_ea, 3, id="ea"),
        pytest.param(_metno_frost, 6, id="metno_frost"),
        pytest.param(
            _dwd_road,
            1,
            id="dwd_road",
            marks=pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required"),
        ),
    ],
)
def test_downloads_use_certifi_when_the_settings_ask_for_it(
    monkeypatch: pytest.MonkeyPatch,
    collect: Callable[[pytest.MonkeyPatch], Seen],
    downloads: int,
) -> None:
    """Test that every download of a request goes out with `WD_USE_CERTIFI`.

    `download_file` defaults `use_certifi` to off, so a call that did not pass the setting on went
    out with the system CA store whatever the caller had set -- and on a host whose store cannot
    verify the upstream, the station list loaded and the values then failed verification (GH-2463).
    """
    monkeypatch.setenv("WD_USE_CERTIFI", "true")
    seen = collect(monkeypatch)
    # every download the request makes, so that none of them is left out of the check below
    assert len(seen) == downloads, seen
    assert [url for url, use_certifi in seen if use_certifi is not True] == []
