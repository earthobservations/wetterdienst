# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A request made without a network connection raises `NoInternetError`, for every provider (GH-2640).

The network layer is replaced, not the providers: the aiohttp error a refused or unresolvable
connection raises is served from where `download_file` and the listings reach for the network, so each
test goes the whole way through the provider's own code. Nothing here opens a connection.
"""

import socket
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import polars as pl
import pytest
import stamina
from aiohttp import ClientConnectorError, ClientResponseError

from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.provider.dwd.catalogue import read_mosmix_station_catalogue
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.download import download_climate_observations_data
from wetterdienst.provider.fmi.observation import FmiObservationRequest
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.util import network
from wetterdienst.util.network import list_remote_files_fsspec

_DNS_FAILURE = socket.gaierror(8, "nodename nor servname provided, or not known")


def _connector_error() -> ClientConnectorError:
    return ClientConnectorError(Mock(ssl=None, host="example.invalid", port=443), _DNS_FAILURE)


def _serve_listings(monkeypatch: pytest.MonkeyPatch, filesystem: SimpleNamespace) -> None:
    """Hand the listings a stand-in filesystem.

    Replaced where the listings build it rather than on its class: fsspec caches an instance per set of
    arguments and gives it its sync methods when it is built, so one built by an earlier test in the
    process would not see a method patched on the class afterwards.
    """
    monkeypatch.setattr(network, "HTTPFileSystem", lambda **_kwargs: filesystem)


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make every download and every listing meet the error aiohttp raises when no connection can be made."""
    filesystem = MagicMock()
    filesystem.cat_file.side_effect = _connector_error()

    def fail(*_args: object, **_kwargs: object) -> None:
        raise _connector_error()

    _serve_listings(monkeypatch, SimpleNamespace(find=fail, ls=fail))
    # one attempt where the network layer would ask three times, to keep the tests from waiting
    with (
        stamina.set_testing(True, attempts=1),
        patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=filesystem),
    ):
        yield


@pytest.mark.usefixtures("offline")
@pytest.mark.parametrize(
    ("request_class", "kwargs", "host"),
    [
        pytest.param(
            DwdObservationRequest,
            {"parameters": [("daily", "climate_summary")], "periods": "recent"},
            "opendata.dwd.de",
            id="dwd/observation",
        ),
        pytest.param(DwdMosmixRequest, {"parameters": [("hourly", "large")]}, "www.dwd.de", id="dwd/mosmix"),
        pytest.param(FmiObservationRequest, {"parameters": [("hourly", "data")]}, "opendata.fmi.fi", id="fmi"),
        pytest.param(ImgwHydrologyRequest, {"parameters": [("daily", "hydrology")]}, "imgw.pl", id="imgw"),
    ],
)
def test_the_station_catalogue_of_an_offline_provider_raises(request_class: type, kwargs: dict, host: str) -> None:
    """No stations are not an answer a provider gives for a connection that could not be made.

    One of each way a catalogue is read: a file listing (DWD observation, IMGW) and a download
    (MOSMIX, FMI).
    """
    with pytest.raises(NoInternetError) as raised:
        request_class(**kwargs).all()

    assert host in str(raised.value)
    # the cause is the error underneath, which is not the aiohttp error holding the connection key
    assert raised.value.__cause__ is _DNS_FAILURE
    assert raised.value.__context__ is None


@pytest.mark.usefixtures("offline")
def test_the_dwd_observation_files_of_an_offline_request_raise() -> None:
    """The values path raises as the catalogue does, at the first file, naming it."""
    url = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/x.zip"

    with pytest.raises(NoInternetError, match=r"x\.zip"):
        download_climate_observations_data(pl.Series([url]), Settings(cache_disable=True))


@pytest.mark.usefixtures("offline")
def test_a_catalogue_reader_of_an_offline_library_raises() -> None:
    """The MOSMIX catalogue was an empty frame offline, which made every point forecast a network without stations."""
    with pytest.raises(NoInternetError, match=r"www\.dwd\.de"):
        read_mosmix_station_catalogue(Settings(cache_disable=True))


@pytest.mark.usefixtures("offline")
def test_a_caller_who_wants_an_empty_frame_offline_catches_the_error() -> None:
    """The opt-in is the documented `except NoInternetError`, nothing the library has to be told."""
    try:
        df = DwdMosmixRequest(parameters=[("hourly", "large")]).all().df
    except NoInternetError:
        df = pl.DataFrame()

    assert df.is_empty()


def test_a_provider_that_answered_badly_is_not_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 5xx is a `DownloadError`, and a listing that is not there is empty: neither is `NoInternetError`."""
    failing = ClientResponseError(request_info=MagicMock(), history=(), status=503, message="Service Unavailable")
    filesystem = MagicMock()
    filesystem.cat_file.side_effect = failing
    with (
        stamina.set_testing(True, attempts=1),
        patch("wetterdienst.util.network.NetworkFilesystemManager.get", return_value=filesystem),
        pytest.raises(DownloadError) as raised,
    ):
        read_mosmix_station_catalogue(Settings(cache_disable=True))

    assert not isinstance(raised.value, NoInternetError)
    assert raised.value.__cause__ is failing

    def missing(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError

    _serve_listings(monkeypatch, SimpleNamespace(find=missing))

    assert list_remote_files_fsspec("https://example.invalid/gone/", Settings(cache_disable=True)) == []


# The providers below read the failure off the `File` themselves, so each is held to the rule where it reads it.


def test_smhi_values_offline_raise_where_a_404_is_a_station_without_the_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 404 is a station that does not measure the parameter, routine; no connection is not (GH-2640)."""
    from wetterdienst.provider.smhi.observation import api as smhi_api  # noqa: PLC0415
    from wetterdienst.provider.smhi.observation.metadata import SmhiObservationMetadata  # noqa: PLC0415

    parameter = SmhiObservationMetadata["daily"].datasets[0].parameters[0]
    values = object.__new__(smhi_api.SmhiObservationValues)

    monkeypatch.setattr(smhi_api, "_fetch", lambda *_args, **_kwargs: FileNotFoundError("404"))
    assert values._collect_parameter("1", parameter, Settings()).is_empty()  # noqa: SLF001

    monkeypatch.setattr(smhi_api, "_fetch", lambda *_args, **_kwargs: NoInternetError("offline"))
    with pytest.raises(NoInternetError):
        values._collect_parameter("1", parameter, Settings())  # noqa: SLF001


def test_frost_offline_raises_before_a_status_that_would_drop_the_file() -> None:
    """The statuses Frost answers `no data` with are no answer for a download that never connected (GH-2640)."""
    from wetterdienst.provider.metno.frost.api import _raise_if_offline  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    error = NoInternetError("offline")
    with pytest.raises(NoInternetError) as raised:
        _raise_if_offline(File(url="https://frost.met.no/x", content=error, status=503))
    assert raised.value is error

    # a 412 or a 404 is what Frost answers when there is nothing: left to the caller
    _raise_if_offline(File(url="https://frost.met.no/x", content=FileNotFoundError("404"), status=404))


def test_hubeau_elevations_are_not_left_out_for_want_of_a_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sites referential only adds elevations, so a failure to read it is warned about, offline is not (GH-2640)."""
    from wetterdienst.provider.eaufrance.hubeau import api as hubeau_api  # noqa: PLC0415

    request = object.__new__(hubeau_api.HubeauRequest)
    request.settings = Settings(cache_disable=True)

    url = "https://hubeau.eaufrance.fr/sites"

    def failing(*_args: object, **_kwargs: object) -> list[dict]:
        raise DownloadError(url, "503")

    monkeypatch.setattr(hubeau_api, "_paged_rows", failing)
    assert request._site_elevations().is_empty()  # noqa: SLF001

    def offline(*_args: object, **_kwargs: object) -> list[dict]:
        msg = "offline"
        raise NoInternetError(msg)

    monkeypatch.setattr(hubeau_api, "_paged_rows", offline)
    with pytest.raises(NoInternetError):
        request._site_elevations()  # noqa: SLF001


def test_the_kml_reader_of_an_offline_library_raises_no_internet() -> None:
    """The MOSMIX and DMO runs are read through fsspec, not `download_file`: no raw aiohttp error either (GH-2640)."""
    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415

    def fail(*_args: object, **_kwargs: object) -> None:
        raise _connector_error()

    reader = KMLReader(station_ids=["01001"], settings=Settings(cache_disable=True))
    reader._filesystem_for = lambda _url: SimpleNamespace(open=fail, size=fail)  # type: ignore[method-assign]  # noqa: SLF001

    with pytest.raises(NoInternetError, match=r"MOSMIX_L_LATEST_01001\.kmz") as raised:
        reader.download(
            "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/01001/kml/MOSMIX_L_LATEST_01001.kmz"
        )

    assert raised.value.__cause__ is _DNS_FAILURE
    assert raised.value.__context__ is None


def test_the_kml_reader_keeps_a_tls_failure_apart_from_being_offline() -> None:
    """A certificate that does not verify is the host answering: the bare `ssl.SSLError`, not `NoInternetError`."""
    import ssl  # noqa: PLC0415

    from aiohttp import ClientConnectorCertificateError  # noqa: PLC0415

    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415

    failure = ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED")

    def fail(*_args: object, **_kwargs: object) -> None:
        raise ClientConnectorCertificateError(Mock(ssl=None, host="example.invalid", port=443), failure)

    reader = KMLReader(station_ids=["01001"], settings=Settings(cache_disable=True))
    reader._filesystem_for = lambda _url: SimpleNamespace(open=fail)  # type: ignore[method-assign]  # noqa: SLF001

    with pytest.raises(ssl.SSLError) as raised:
        reader.download("https://example.invalid/run.kmz")

    assert not isinstance(raised.value, NoInternetError)


def test_the_kml_reader_serves_a_cached_run_whose_size_cannot_be_asked_for() -> None:
    """The size only sizes the progress bar, and is a request even for a run the cache holds."""
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415

    def size(*_args: object, **_kwargs: object) -> int:
        raise _connector_error()

    reader = KMLReader(station_ids=["01001"], settings=Settings(cache_disable=True))
    reader._filesystem_for = lambda _url: SimpleNamespace(open=lambda *_a, **_k: BytesIO(b"kmz"), size=size)  # type: ignore[method-assign]  # noqa: SLF001

    assert reader.download("https://example.invalid/run.kmz").getvalue() == b"kmz"
