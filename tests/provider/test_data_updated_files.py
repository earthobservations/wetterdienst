# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`data_updated_at` of the networks that date a file: when the source last wrote what the answer was read from.

The date is the `Last-Modified` the download kept (`File.last_modified`), the newest of the files that gave the station
readings; for a forecast it is the model run. A file that failed, or that gave no reading, adds none (GH-2567).
"""

from __future__ import annotations

import bz2
import datetime as dt
import gzip
import zipfile
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl

from tests.provider.dwd.mosmix.test_api_data import _stub_mosmix_stations
from tests.provider.value_stubs import stations_result
from wetterdienst import Options, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation import download as dwd_observation_download
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest, DwdObservationValues
from wetterdienst.provider.dwd.observation.download import (
    _unpack_climate_observations_data,
    download_climate_observations_data,
)
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos import api as swsmos_api
from wetterdienst.provider.ipma.observation import IpmaObservationRequest
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest
from wetterdienst.provider.meteofrance.synop import api as synop_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from datetime import datetime

    import pytest

UTC = ZoneInfo("UTC")

OLD = dt.datetime(2026, 10, 20, 9, 0, 7, tzinfo=UTC)
NEW = dt.datetime(2026, 10, 25, 6, 30, 0, tzinfo=UTC)
NEWER = dt.datetime(2026, 10, 26, 6, 0, 0, tzinfo=UTC)

# the two files of the seam of the year 2000 of one station, as DWD writes them
_BEFORE = (
    "STATIONS_ID;MESS_DATUM;QN;PP_10;TT_10;TM5_10;RF_10;TD_10\n"
    "       1048;199912312330;    1;  996.2;  -0.6;  -2.3;  92.0;  -1.8\n"
    "       1048;199912312340;    1;  996.3;  -0.6;  -2.2;  92.0;  -1.8\n"
)
_AFTER = (
    "STATIONS_ID;MESS_DATUM;  QN;PP_10;TT_10;TM5_10;RF_10;TD_10;eor\n"
    "       1048;200001010000;    1;  996.4;  -1.0;  -1.4;  94.0;  -1.7;eor\n"
)


def _dwd_10_minute_values(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    files: dict[str, tuple[str, datetime | None]],
) -> object:
    """Read the values of station 01048 from the product files served, each with the date DWD wrote it."""
    monkeypatch.setattr(DwdObservationValues, "_get_historical_date_ranges", lambda *_, **__: None)
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *_, **__: pl.Series([f"https://example.invalid/{name}" for name in files]),
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda *_, **__: [
            File(
                url=f"https://example.invalid/{name}",
                content=BytesIO(product.encode("latin-1")),
                status=200,
                last_modified=written,
            )
            for name, (product, written) in files.items()
        ],
    )
    request = DwdObservationRequest(
        parameters=[("10_minutes", "air_temperature", "temperature_air_2m")],
        periods={Period.HISTORICAL},
        start=dt.datetime(1999, 12, 31, 20, tzinfo=UTC),
        end=dt.datetime(2000, 1, 1, 2, tzinfo=UTC),
        settings=settings,
        options=Options(drop_nulls=False),
    )
    return stations_result(request, "10_minutes", "air_temperature", "01048").values().all()


def test_dwd_observation_is_dated_by_the_newest_of_the_files_it_read(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Two archives, written on two days: the answer says the later, in whichever order they were read."""
    for files in (
        {"before.zip": (_BEFORE, OLD), "after.zip": (_AFTER, NEW)},
        {"after.zip": (_AFTER, NEW), "before.zip": (_BEFORE, OLD)},
    ):
        result = _dwd_10_minute_values(monkeypatch, default_settings, files)

        assert not result.df.is_empty()
        assert result.data_updated_at == NEW


def test_dwd_observation_a_file_without_a_date_adds_none_and_none_at_all_is_null(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """The date of the file that has one is the answer's; no file with one is no date, never a made-up one."""
    one = _dwd_10_minute_values(
        monkeypatch, default_settings, {"before.zip": (_BEFORE, None), "after.zip": (_AFTER, OLD)}
    )
    none = _dwd_10_minute_values(
        monkeypatch, default_settings, {"before.zip": (_BEFORE, None), "after.zip": (_AFTER, None)}
    )

    assert one.data_updated_at == OLD
    assert none.data_updated_at is None
    assert not none.df.is_empty()


def _archive(content: str, written: datetime | None, name: str = "a.zip") -> File:
    """Give an archive of one product file, as a download of it that DWD wrote on the given day."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("produkt_zehn_min_tu_19911119_19991231_01048.txt", content)
    return File(
        url=f"https://example.invalid/{name}", content=BytesIO(buffer.getvalue()), status=200, last_modified=written
    )


def test_dwd_observation_a_file_that_is_not_there_is_not_counted(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """A 404 is dropped before the readings are made, so the date of what is left is the answer's."""
    missing = File(url="https://example.invalid/missing.zip", content=FileNotFoundError("404"), status=404)
    monkeypatch.setattr(
        dwd_observation_download,
        "download_files",
        lambda **_kwargs: [_archive(_BEFORE, OLD), missing],
    )

    files = download_climate_observations_data(pl.Series(["unused", "unused"]), default_settings)

    assert [file.last_modified for file in files] == [OLD]


def test_dwd_observation_unpacking_an_archive_keeps_its_date() -> None:
    """The product file taken out of the archive has the date of the archive, which the answer is dated by."""
    unpacked = _unpack_climate_observations_data(_archive(_BEFORE, OLD))

    assert unpacked.last_modified == OLD


def test_swsmos_is_dated_by_its_run_and_not_by_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A forecast is dated by the run it is of, which its file name states, whenever the file was written."""
    body = "".join(f"A006;54.889156;8.908735;20261026{hour:02d}00;1{hour}.0\n" for hour in (8, 9))
    content = bz2.compress(b"ID;Lat;Lon;YYYYMMDDHHmm;TL\n202610260700\n" + body.encode("latin-1"))
    name = "swsmos_20261026070000_opendata.csv.bz2"
    monkeypatch.setattr(swsmos_api, "list_remote_files_fsspec", lambda *_a, **_k: [f"{swsmos_api._BASE_URL}/{name}"])  # noqa: SLF001
    monkeypatch.setattr(
        swsmos_api,
        "download_file",
        # written two days after the run it holds
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(content), status=200, last_modified=NEWER),
    )
    request = DwdSwsmosRequest(
        parameters=[("hourly", "data", "temperature_air")], settings=Settings(cache_disable=True)
    )

    result = stations_result(request, "hourly", "data", "A006").values().all()

    assert not result.df.is_empty()
    assert result.data_updated_at == dt.datetime(2026, 10, 26, 7, tzinfo=UTC)


def test_mosmix_is_dated_by_the_run_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A MOSMIX forecast says when its run was issued, the `IssueTime` of the file that was read."""
    values = _stub_mosmix_stations().values()
    monkeypatch.setattr(values, "get_url_for_date", lambda *_a, **_k: "https://example.invalid/MOSMIX_L_2026102606.kmz")
    monkeypatch.setattr(values.kml, "read", lambda _url: None)
    values.kml.metadata = {"issue_time": dt.datetime(2026, 10, 26, 6, tzinfo=UTC)}
    monkeypatch.setattr(
        values.kml,
        "get_station_forecast",
        lambda _station: pl.DataFrame({"timestamp": ["2026-10-26T07:00:00.000Z"], "ttt": [280.1]}),
    )

    result = values.all()

    assert not result.df.is_empty()
    assert result.data_updated_at == dt.datetime(2026, 10, 26, 6, tzinfo=UTC)


_IPMA_STATIONS = (
    b'[{"geometry": {"type": "Point", "coordinates": [-9.1, 38.7]}, "type": "Feature", '
    b'"properties": {"idEstacao": 1200579, "localEstacao": "Lisboa"}}]'
)
_IPMA_FEED = b'{"2026-10-10T12:00": {"1200579": {"temperatura": 20.0}}}'


def _ipma_values(monkeypatch: pytest.MonkeyPatch, *, feed_written: datetime | None) -> object:
    """Read a station of the feed, whose file and whose catalogue were written on different days."""

    def download_file(url: str, **_: object) -> File:
        if url.endswith("observations.json"):
            return File(url=url, content=BytesIO(_IPMA_FEED), status=200, last_modified=feed_written)
        return File(url=url, content=BytesIO(_IPMA_STATIONS), status=200, last_modified=NEWER)

    monkeypatch.setattr(ipma_api, "download_file", download_file)
    return (
        IpmaObservationRequest(
            parameters=[("hourly", "data")],
            start=dt.datetime(2026, 10, 10, 11, tzinfo=UTC),
            end=dt.datetime(2026, 10, 10, 14, tzinfo=UTC),
            settings=Settings(cache_disable=True),
        )
        .filter_by_station_id("1200579")
        .values()
        .all()
    )


def test_ipma_is_dated_by_the_feed_and_not_by_the_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """The station list is written on another day than the feed, and the readings are the feed's."""
    result = _ipma_values(monkeypatch, feed_written=OLD)

    assert not result.df.is_empty()
    assert result.data_updated_at == OLD


def test_ipma_without_a_date_for_the_feed_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """A feed that states no date is dated by nothing, whatever the catalogue says."""
    assert _ipma_values(monkeypatch, feed_written=None).data_updated_at is None


def _synop_file(*rows: tuple[str, str]) -> bytes:
    """Write the file of a year: a row of the given station and time each, in the columns of the source."""
    schema = list(synop_api._SYNOP_CSV_SCHEMA)  # noqa: SLF001
    lines = [";".join(schema)]
    lines += [
        ";".join({"geo_id_wmo": station, "validity_time": stamp, "t": "280.0"}.get(column, "") for column in schema)
        for station, stamp in rows
    ]
    return gzip.compress("\n".join(lines).encode("utf8"))


def test_meteofrance_synop_is_dated_by_the_newest_of_the_year_files_that_gave_readings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Licence Ouverte asks for the date of the update: the newest of the files read that held the station."""
    files = {
        "synop_2023": (_synop_file(("07005", "2023-12-31T18:00:00Z")), OLD),
        "synop_2024": (_synop_file(("07005", "2024-01-01T18:00:00Z")), NEW),
        # another station only, written last of all
        "synop_2025": (_synop_file(("07015", "2025-01-01T18:00:00Z")), NEWER),
    }

    def download_file(*, url: str, **_: object) -> File:
        content, written = next(entry for part, entry in files.items() if part in url)
        return File(url=url, content=BytesIO(content), status=200, last_modified=written)

    monkeypatch.setattr(synop_api, "download_file", download_file)
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
        start=dt.datetime(2023, 12, 31, tzinfo=UTC),
        end=dt.datetime(2025, 1, 2, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )

    result = stations_result(request, "subdaily", "data", "07005").values().all()

    assert not result.df.is_empty()
    assert result.data_updated_at == NEW
