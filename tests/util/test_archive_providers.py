# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every reader that unpacks an archive holds it to its ceiling: a bomb of a few kilobytes is a `DownloadError`.

Each reader is given a bomb of a few hundred bytes that unpacks to 200 kB, and a ceiling of one kilobyte.
"""

from __future__ import annotations

import bz2
import gzip
import tarfile
import zipfile
from io import BytesIO
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, MetaFileFormatError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.alerts import api as alerts_api
from wetterdienst.provider.dwd.derived.download import _unpack_climate_derived_data
from wetterdienst.provider.dwd.mosmix import access as mosmix_access
from wetterdienst.provider.dwd.observation.download import _unpack_climate_observations_data
from wetterdienst.provider.dwd.observation.metaindex import _parse_geo_metadata
from wetterdienst.provider.dwd.radar import api as radar_api
from wetterdienst.provider.dwd.swsmos import api as swsmos_api
from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyValues
from wetterdienst.provider.imgw.meteorology.api import ImgwMeteorologyValues
from wetterdienst.util import archive, network
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

BASE = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/daily/recent/"
LIMIT = 1000
BOMB = bytes(200_000)


@pytest.fixture(autouse=True)
def _low_ceilings(monkeypatch: pytest.MonkeyPatch) -> None:
    for module, name in [
        (archive, "MAX_UNPACKED_BYTES"),
        (swsmos_api, "_MAX_UNPACKED_BYTES"),
        (alerts_api, "_MAX_UNPACKED_BYTES"),
        (radar_api, "_MAX_UNPACKED_BYTES"),
        (mosmix_access, "MAX_KML_BYTES"),
    ]:
        monkeypatch.setattr(module, name, LIMIT)


def _zip(name: str = "produkt_a.txt") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive_:
        archive_.writestr(name, BOMB)
    return buffer.getvalue()


def _tar(name: str = "member.bin") -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive_:
        info = tarfile.TarInfo(name)
        info.size = len(BOMB)
        archive_.addfile(info, BytesIO(BOMB))
    return buffer.getvalue()


def _file(name: str, content: bytes) -> File:
    return File(url=f"{BASE}{name}", content=BytesIO(content), status=200)


def test_swsmos_does_not_answer_a_bomb_with_an_empty_frame() -> None:
    """A run file that is not bz2 is reported and answered with no frame; one that is too large is an error."""
    with pytest.raises(DownloadError, match="unpacks to more than"):
        swsmos_api._read_run(bz2.compress(BOMB), f"{BASE}run.csv.bz2")  # noqa: SLF001


def test_dwd_alerts_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """A snapshot is refused as the `DownloadError` it is, not as a layout the parser does not expect."""
    request = alerts_api.DwdWeatherAlertRequest()
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.alerts.api.download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(_zip("alert.xml")), status=200),
    )
    with pytest.raises(DownloadError, match="unpacks to more than") as raised:
        request.query()
    assert not isinstance(raised.value, MetaFileFormatError)


def test_dwd_derived_gzip_and_zip() -> None:
    """Both layouts of the derived files."""
    with pytest.raises(DownloadError, match="unpacks to more than"):
        _unpack_climate_derived_data(_file("soil_1.txt.gz", gzip.compress(BOMB)))
    with pytest.raises(DownloadError, match="unpacks to more than"):
        _unpack_climate_derived_data(_file("soil_1.zip", _zip()))


def test_dwd_observation_zip() -> None:
    """A station's zip, and the zip of its metadata."""
    with pytest.raises(DownloadError, match="unpacks to more than"):
        _unpack_climate_observations_data(_file("stundenwerte_TU_00044.zip", _zip()))
    with pytest.raises(DownloadError, match="unpacks to more than"):
        _parse_geo_metadata(_file("Metadaten_Geographie_00044.zip", _zip()), "00044")


@pytest.mark.parametrize("values", [ImgwMeteorologyValues, ImgwHydrologyValues])
def test_imgw_zip(values: type) -> None:
    """The zips of both networks."""
    with pytest.raises(DownloadError, match="unpacks to more than"):
        values._parse_file(None, _file("2023_01_k.zip", _zip()), "249", Resolution.DAILY, {})  # noqa: SLF001


@pytest.mark.parametrize(
    ("name", "content"),
    [("composite.bz2", bz2.compress(BOMB)), ("composite.gz", gzip.compress(BOMB)), ("members.tar", _tar())],
)
def test_dwd_radar_files(monkeypatch: pytest.MonkeyPatch, name: str, content: bytes) -> None:
    """The three layouts of a radar file: a bz2, a gzip and a tar of members."""
    monkeypatch.setattr(
        radar_api, "download_file", lambda **kwargs: File(url=kwargs["url"], content=BytesIO(content), status=200)
    )
    reader = SimpleNamespace(settings=Settings(cache_disable=True), _should_cache_download=lambda _url: True)
    with pytest.raises(DownloadError, match="unpacks to more than"):
        list(radar_api.DwdRadarValues._download_generic_data(reader, f"{BASE}{name}"))  # noqa: SLF001


def test_dwd_radolan_archives() -> None:
    """The historical tar.gz of members, and the recent gzip of one file (zeros would read as an empty tar)."""
    with pytest.raises(DownloadError, match="unpacks to more than"):
        list(
            radar_api.DwdRadarValues._extract_radolan_data(  # noqa: SLF001
                BytesIO(gzip.compress(_tar("RW_2310010000.bin"))), f"{BASE}a.tar.gz"
            )
        )
    with pytest.raises(DownloadError, match="unpacks to more than"):
        list(radar_api.DwdRadarValues._extract_radolan_data(BytesIO(gzip.compress(b"x" * len(BOMB))), f"{BASE}a.gz"))  # noqa: SLF001


def test_mosmix_kml_is_refused_before_it_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The KML of a run is parsed from a stream, so it is the claim of the archive that is held to the ceiling."""
    reader = mosmix_access.KMLReader([], Settings(cache_disable=True))
    monkeypatch.setattr(reader, "download", lambda _url: BytesIO(_zip("run.kml")))
    with pytest.raises(DownloadError, match="unpacks to more than"):
        reader.fetch(f"{BASE}MOSMIX_S_LATEST_240.kmz")


class _Stream:
    """What the plain HTTP filesystem opens: a stream of unknown size, as `read_in_chunks` reads it."""

    def __init__(self, body: bytes) -> None:
        self._body = BytesIO(body)

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def fileno(self) -> int:
        raise AttributeError


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("MAX_DOWNLOAD_BYTES", 1000, "larger than a download is held to"),
        ("MAX_DOWNLOAD_SECONDS", -1, "took longer than a download is held to"),
    ],
)
def test_mosmix_stream_that_is_not_cached(
    monkeypatch: pytest.MonkeyPatch, setting: str, value: float, message: str
) -> None:
    """The stream of an uncached filesystem is held to the size and the time of a download as the cache is."""
    monkeypatch.setattr(network, setting, value)
    filesystem = SimpleNamespace(open=lambda _url, **_: _Stream(BOMB), size=lambda _url: len(BOMB))
    reader: Callable[..., BytesIO] = mosmix_access.KMLReader._read  # noqa: SLF001
    with pytest.raises(network.DownloadRefusedError, match=message):
        reader(filesystem, f"{BASE}MOSMIX_S_LATEST_240.kmz")
