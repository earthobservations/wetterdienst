# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations of KNMI are those of its catalogue that have data at the resolution, and each has its WSI (GH-4008).

The stations were read from the latest file of each resolution, which holds the stations that reported in its
interval: Valkenburg (06210) and Soesterberg (06265) have history and were no station, the latest 10-minute file held
57 stations where 76 of the 77 have data, and the 10-minute `wigos_id` was the bare number of the file's key. The rows
of the catalogue are real ones (`catalogue.py`, read from the Open Data API on 2026-11-11).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl
import pytest

from tests.provider.knmi.observation.catalogue import CATALOGUE_ROWS, catalogue_csv
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.knmi.observation import api
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.settings import Settings

CATALOGUE_DATASET = "waarneemstations_csv"
ALL = tuple(CATALOGUE_ROWS)
#: What the catalogue holds that a resolution has no data of: the fog station is held by the 10-minute files only, and
#: Soesterberg closed in 2008, before they start
NOT_IN = {
    "10_minutes": {"06265"},
    "hourly": {"06233"},
    "daily": {"06233"},
    "monthly": {"06233"},
    "annual": {"06233"},
}


def _wsi(station_id: str) -> str:
    return CATALOGUE_ROWS[station_id].split(",")[1]


@dataclass
class Served:
    """What KNMI was asked for while the stations were listed."""

    listings: list[tuple[str, CacheExpiry]] = field(default_factory=list)
    files: list[tuple[str, str, CacheExpiry | None]] = field(default_factory=list)
    forgotten: list[str] = field(default_factory=list)


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    *,
    catalogue: bytes | Exception | None = None,
    netcdf: bytes | None = None,
) -> Served:
    """Serve the listings and the files of KNMI: the catalogue (the rows of `catalogue.py`) and a NetCDF."""
    served = Served()
    body = catalogue_csv() if catalogue is None else catalogue

    def latest(dataset: str, _version: str, _settings: Settings, ttl: CacheExpiry = CacheExpiry.ONE_HOUR) -> str:
        served.listings.append((dataset, ttl))
        return "csv_knmi_nl_20260615.csv" if dataset == CATALOGUE_DATASET else "latest.nc"

    def fetch(
        dataset: str, _version: str, filename: str, _settings: Settings, expiry: CacheExpiry | None = None
    ) -> bytes | Exception:
        served.files.append((dataset, filename, expiry))
        if dataset == CATALOGUE_DATASET:
            return body
        if netcdf is None:
            return FileNotFoundError(filename)
        return netcdf

    monkeypatch.setattr(api, "_latest_filename", latest)
    monkeypatch.setattr(api, "_fetch_netcdf", fetch)
    monkeypatch.setattr(
        api, "_forget_file", lambda _dataset, _version, filename, _settings: served.forgotten.append(filename)
    )
    return served


def _stations(*resolutions: str) -> pl.DataFrame:
    request = KnmiObservationRequest(
        parameters=[(resolution, "data") for resolution in resolutions],
        settings=Settings(cache_disable=True, auth={"knmi": "stub"}),
    )
    return request.all().df


@pytest.mark.parametrize("resolution", NOT_IN)
def test_the_stations_of_a_resolution_are_those_of_the_catalogue_that_have_data(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    """A station is listed for a resolution unless its dataset cannot hold it: fog stations, closed before it began."""
    _serve(monkeypatch)
    listed = _stations(resolution).get_column("station_id").to_list()
    assert listed == [station_id for station_id in ALL if station_id not in NOT_IN[resolution]]


@pytest.mark.parametrize("resolution", ["hourly", "daily", "monthly", "annual"])
def test_a_station_that_only_older_files_hold_is_listed(monkeypatch: pytest.MonkeyPatch, resolution: str) -> None:
    """Valkenburg (closed 2016) and Soesterberg (2008) have history, and no latest file lists them (GH-4008).

    The latest file, which is not read for the list, holds De Bilt alone here.
    """
    served = _serve(monkeypatch, netcdf=b"the latest file, which is not read")
    df = _stations(resolution)
    assert {"06210", "06265"} <= set(df.get_column("station_id"))
    assert [dataset for dataset, *_ in served.files] == [CATALOGUE_DATASET]


def test_a_station_closed_before_the_10_minute_files_began_is_not_one_of_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 10-minute files start in 2012: Valkenburg (closed 2016) is in them, Soesterberg (2008) cannot be."""
    _serve(monkeypatch)
    listed = set(_stations("10_minutes").get_column("station_id"))
    assert "06210" in listed
    assert "06265" not in listed


@pytest.mark.parametrize("resolution", NOT_IN)
def test_every_station_has_its_wigos_station_identifier(monkeypatch: pytest.MonkeyPatch, resolution: str) -> None:
    """`wigos_id` is the WSI at every resolution, 10 minutes too, and `station_id` its trailing WMO number (GH-4008)."""
    _serve(monkeypatch)
    df = _stations(resolution)
    for station_id, wigos_id in df.select("station_id", "wigos_id").iter_rows():
        assert wigos_id == _wsi(station_id)
        assert wigos_id.endswith(f"-{station_id}")
    by_id = dict(df.select("station_id", "wigos_id").iter_rows())
    assert by_id["06260"] == "0-20000-0-06260"
    assert by_id["06392"] == "0-528-0-06392"  # another issuer than 20000
    assert by_id["78990"] == "0-20000-0-78990"  # block 78: the number is not the legacy 990


def test_a_station_that_was_moved_is_listed_where_it_is_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """The newest catalogue says where a station is and what it is called: the older files say it as it was.

    Eindhoven (06370) was at 51.4497, 5.3769 and Deelen (06275) at 52.0547, 5.8722 in the files until June 2026, and
    De Bilt was "DE BILT AWS" in them until late 2024.
    """
    _serve(monkeypatch)
    by_id = {row["station_id"]: row for row in _stations("hourly").iter_rows(named=True)}
    assert (by_id["06370"]["latitude"], by_id["06370"]["longitude"]) == (51.4631, 5.3856)
    assert (by_id["06275"]["latitude"], by_id["06275"]["longitude"], by_id["06275"]["elevation"]) == (
        52.0589,
        5.8731,
        44.92,
    )
    assert by_id["06260"]["name"] == "De Bilt"
    assert by_id["06210"]["name"] == "VALKENBURG VK"  # the name of the catalogue as it is, of a station that closed


def test_a_station_has_a_position_and_a_height_with_its_sign(monkeypatch: pytest.MonkeyPatch) -> None:
    """The height of Valkenburg is -0.2 m, a position is that of the catalogue's `POS_NB` and `POS_OL`."""
    _serve(monkeypatch)
    by_id = {row["station_id"]: row for row in _stations("daily").iter_rows(named=True)}
    assert (by_id["06210"]["latitude"], by_id["06210"]["longitude"], by_id["06210"]["elevation"]) == (
        52.1703,
        4.4294,
        -0.2,
    )
    assert (by_id["78871"]["latitude"], by_id["78871"]["longitude"]) == (17.6461, -63.2208)


def test_no_station_is_given_the_dates_of_the_catalogue_as_its_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """`STARTT` and `STOPT` are not the first and the last day of the data, so no station carries them as its window.

    Schiphol's `STARTT` is 1990-07-01 and its data begins in 1951: read as the start of its record, a request for the
    1950s would be told it has none. A null date says nothing either way (the station may have data in the window).
    """
    _serve(monkeypatch)
    df = _stations("hourly")
    assert df.get_column("start_timestamp").null_count() == df.height
    assert df.get_column("end_timestamp").null_count() == df.height
    assert "1990-07-01" in CATALOGUE_ROWS["06240"]


def test_the_catalogue_is_one_listing_and_one_file_for_every_resolution_and_kept_for_a_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five resolutions cost the two requests of one catalogue (listing and link), not two each, and it is held long."""
    served = _serve(monkeypatch)
    df = _stations("10_minutes", "hourly", "daily", "monthly", "annual")
    assert df.get_column("resolution").n_unique() == 5
    assert served.listings == [(CATALOGUE_DATASET, CacheExpiry.ONE_WEEK)]
    assert served.files == [(CATALOGUE_DATASET, "csv_knmi_nl_20260615.csv", CacheExpiry.ONE_WEEK)]


@pytest.mark.parametrize(
    "catalogue",
    [
        pytest.param(b"STN,WSI\n260,0-20000-0-06260\n", id="a column is missing"),
        pytest.param(b"", id="empty"),
        pytest.param(b"\x89HDF\r\n\x1a\n\x00\x00\x01\x02\x03", id="not a CSV"),
    ],
)
def test_a_catalogue_that_cannot_be_read_is_dropped_and_the_files_list_the_stations(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path, catalogue: bytes
) -> None:
    """KNMI changing the catalogue must not take the station list with it: the latest file of the resolution is read."""
    h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
    h5py = pytest.importorskip("h5py", reason="h5py not installed")
    path = tmp_path / "latest.nc"
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": 1}
        for name, value in {"station": "0-20000-0-06260", "stationname": "De Bilt"}.items():
            variable = file.create_variable(name, ("station",), dtype=h5py.string_dtype())
            variable[:] = [value]
        for name, value in {"lat": 52.1, "lon": 5.18, "height": 1.9}.items():
            variable = file.create_variable(name, ("station",), dtype="f8")
            variable[:] = [value]
    served = _serve(monkeypatch, catalogue=catalogue, netcdf=path.read_bytes())
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        df = _stations("daily")
    assert df.select("station_id", "wigos_id").rows() == [("06260", "0-20000-0-06260")]
    assert served.forgotten == ["csv_knmi_nl_20260615.csv"]  # not served again until it expires
    assert any("catalogue of the stations" in record.getMessage() for record in caplog.records)


def _netcdf_of_stations(path: Path, keys: list[str], wsis: list[str] | None) -> bytes:
    h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
    h5py = pytest.importorskip("h5py", reason="h5py not installed")
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": len(keys)}
        columns = {"station": keys, "stationname": ["De Bilt", "Bonaire"][: len(keys)]}
        if wsis is not None:
            columns["wsi"] = wsis
        for name, values in columns.items():
            variable = file.create_variable(name, ("station",), dtype=h5py.string_dtype())
            variable[:] = values
        for name, values in {"lat": [52.1, 12.13], "lon": [5.18, -68.27], "height": [1.9, 2.1]}.items():
            variable = file.create_variable(name, ("station",), dtype="f8")
            variable[:] = values[: len(keys)]
    return path.read_bytes()


def test_the_wigos_id_of_a_file_without_a_catalogue_is_its_wsi_variable_where_it_has_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The 10-minute files key a station by its bare number and carry the WSI in `wsi` (read 2026-11-11, GH-4008)."""
    payload = _netcdf_of_stations(tmp_path / "10m.nc", ["06260", "78990"], ["0-20000-0-06260", "0-20000-0-78990"])
    _serve(monkeypatch, catalogue=b"gone", netcdf=payload)
    df = _stations("10_minutes")
    assert df.select("station_id", "wigos_id").rows() == [
        ("06260", "0-20000-0-06260"),
        ("78990", "0-20000-0-78990"),
    ]


def test_the_wigos_id_of_a_file_without_a_catalogue_or_a_wsi_variable_is_its_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The hourly, daily, monthly and annual files key a station by its WSI, which is what is read where no `wsi` is."""
    payload = _netcdf_of_stations(tmp_path / "hourly.nc", ["0-20000-0-06260", "0-20000-0-78990"], None)
    _serve(monkeypatch, catalogue=b"gone", netcdf=payload)
    df = _stations("hourly")
    assert df.select("station_id", "wigos_id").rows() == [
        ("06260", "0-20000-0-06260"),
        ("78990", "0-20000-0-78990"),
    ]
