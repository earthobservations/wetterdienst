# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that the downloads of a provider go out with the CA bundle `WD_USE_CERTIFI` asks for."""

from __future__ import annotations

import ast
import datetime as dt
import json
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

import wetterdienst
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
    """Request the station list, the values by each way to them, and the credential probe.

    One hourly parameter is requested, out of a dataset of several: a 404 for the request of the
    dataset is followed by the request of that parameter alone, and a 404 for that by the
    discovery of its time series.
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
        # no data for the window, which ends the discovered series without a further request
        if "timeseriesids=" in url:
            return File(url=url, content=FileNotFoundError(url), status=412)
        return File(url=url, content=FileNotFoundError(url), status=404)

    seen = _record(monkeypatch, frost_api, answer)
    request = MetnoFrostRequest(parameters=[("hourly", "data", "temperature_air_mean_2m")], start=START, end=END)
    request.filter_by_station_id("SN18700").values.all()
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
@pytest.mark.parametrize("use_certifi", [True, False])
def test_downloads_follow_the_use_certifi_setting(
    monkeypatch: pytest.MonkeyPatch,
    collect: Callable[[pytest.MonkeyPatch], Seen],
    downloads: int,
    *,
    use_certifi: bool,
) -> None:
    """Test that every download of a request goes out as `WD_USE_CERTIFI` says.

    `download_file` defaults `use_certifi` to off, so a call that did not pass the setting on went
    out with the system CA store whatever the caller had set -- and on a host whose store cannot
    verify the upstream, it failed verification with the setting on (GH-2463). The setting off is
    asked as well, so that a call passing `True` whatever the setting says does not pass either.
    """
    monkeypatch.setenv("WD_USE_CERTIFI", str(use_certifi).lower())
    seen = collect(monkeypatch)
    # every download the request makes, so that none of them is left out of the check below
    assert len(seen) == downloads, seen
    assert [url for url, used in seen if used is not use_certifi] == []


def test_every_network_call_passes_use_certifi() -> None:
    """Test that every call to a network helper taking `use_certifi` passes it, not the default.

    The test above runs the four providers GH-2463 found. This one reads every call in the package
    that names a helper of `util/network.py` taking the keyword with a default of off, so a call
    added later that leaves it out fails here too. It reads calls written with the helper's own
    name: one through an alias or a `functools.partial` is not seen. And it checks that the keyword
    is passed, not what it is passed.
    """
    functions = {"download_file", "download_files", "post_file", "HTTPFileSystem"}
    methods = {("NetworkFilesystemManager", "get"), ("NetworkFilesystemManager", "register")}
    root = Path(wetterdienst.__file__).parent
    missing = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            called = (
                (isinstance(func, ast.Name) and func.id in functions)
                or (isinstance(func, ast.Attribute) and func.attr in functions)
                or (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and (func.value.id, func.attr) in methods
                )
            )
            if called and "use_certifi" not in {keyword.arg for keyword in node.keywords}:
                missing.append(f"{path.relative_to(root)}:{node.lineno}")
    assert missing == []
