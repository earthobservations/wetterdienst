# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations of KNMI are those of its catalogue that have data at the resolution, and each has its WSI (GH-4008).

The stations were read from the latest file of each resolution, which holds the stations that reported in its
interval: Valkenburg (06210) and Soesterberg (06265) have history and were no station, the latest 10-minute file held
57 stations where 76 of the 77 have data, and the 10-minute `wigos_id` was the bare number of the file's key. The rows
of the catalogue are real ones (`catalogue.py`, read from the Open Data API on 2026-11-11).
"""

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from aiohttp import ClientResponseError

from tests.provider.knmi.observation.catalogue import CATALOGUE_ROWS, catalogue_csv
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.knmi.observation import api
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")

CATALOGUE_DATASET = "waarneemstations_csv"
ALL = tuple(CATALOGUE_ROWS)
#: What the catalogue holds that a resolution has no data of: the fog station is held by the 10-minute files only,
#: Soesterberg closed in 2008, before they start, and no annual file holds the Caribbean stations of block 78
NOT_IN = {
    "10_minutes": {"06265"},
    "hourly": {"06233"},
    "daily": {"06233"},
    "monthly": {"06233"},
    "annual": {"06233", "78871", "78990"},
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
    listing: Exception | None = None,
) -> Served:
    """Serve the listings and the files of KNMI: the catalogue (the rows of `catalogue.py`) and a NetCDF."""
    served = Served()
    body = catalogue_csv() if catalogue is None else catalogue

    def latest(dataset: str, _version: str, _settings: Settings, ttl: CacheExpiry = CacheExpiry.ONE_HOUR) -> str:
        served.listings.append((dataset, ttl))
        if listing is not None and dataset == CATALOGUE_DATASET:
            return listing
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
    if "78990" in by_id:  # block 78 (not at annual): the number is not the legacy 990
        assert by_id["78990"] == "0-20000-0-78990"


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


def test_a_closed_station_ends_at_its_stop_date_and_margin_and_no_station_has_a_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`end_timestamp` is `STOPT` and 62 days for a closed station, null for an open one; `start_timestamp` is null.

    `STARTT` is not the first day of the data (Schiphol's is 1990-07-01 and its data begins in 1951): read as the start
    of its record, a request for the 1950s would be told it has none. `STOPT` is no exact end either (Soesterberg's
    data is in the monthly file of 2008-12, `STOPT` 2008-11-15), hence the margin.
    """
    _serve(monkeypatch)
    df = _stations("hourly")
    assert df.get_column("start_timestamp").null_count() == df.height
    assert "1990-07-01" in CATALOGUE_ROWS["06240"]
    ends = dict(df.select("station_id", "end_timestamp").iter_rows())
    assert ends["06210"] == dt.datetime(2016, 7, 4, tzinfo=UTC)  # 2016-05-03
    assert ends["06265"] == dt.datetime(2009, 1, 16, tzinfo=UTC)  # 2008-11-15
    assert ends["06206"] == dt.datetime(2020, 11, 2, tzinfo=UTC)  # 2020-09-01
    assert [station for station, end in ends.items() if end is None] == [
        station for station in ALL if station not in {"06206", "06210", "06265", "06233"}
    ]
    assert df.schema["end_timestamp"] == pl.Datetime("us", "UTC")


def test_a_listing_for_a_window_in_2026_leaves_out_the_stations_closed_long_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The nearest three to De Bilt for January 2026 do not include Soesterberg (closed 2008) or Valkenburg (2016).

    The rank listing is cut to the window as the stations route is (`limit_stations_to_window`, GH-3026): without an
    end a closed station was kept, and was the nearest after De Bilt.
    """
    from wetterdienst.ui.core import limit_stations_to_rank, limit_stations_to_window  # noqa: PLC0415

    _serve(monkeypatch)
    request = KnmiObservationRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(2026, 1, 1, tzinfo=UTC),
        end=dt.datetime(2026, 1, 31, tzinfo=UTC),
        settings=Settings(cache_disable=True, auth={"knmi": "stub"}),
    )
    ranked = request.filter_by_rank(latlon=(52.0989, 5.1797), rank=3)
    assert ranked.df.get_column("station_id").to_list()[:2] == ["06260", "06265"]  # nearest, with no window
    cut = limit_stations_to_rank(limit_stations_to_window(ranked)).df.get_column("station_id").to_list()
    assert len(cut) == 3
    assert not {"06265", "06210", "06206"} & set(cut)
    assert cut[0] == "06260"


def test_a_listing_for_a_window_a_closed_station_has_data_in_keeps_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Soesterberg is listed for December 2008, a month after its `STOPT`, where its data still is."""
    from wetterdienst.ui.core import limit_stations_to_window  # noqa: PLC0415

    _serve(monkeypatch)
    request = KnmiObservationRequest(
        parameters=[("daily", "data")],
        start=dt.datetime(2008, 12, 1, tzinfo=UTC),
        end=dt.datetime(2008, 12, 31, tzinfo=UTC),
        settings=Settings(cache_disable=True, auth={"knmi": "stub"}),
    )
    kept = limit_stations_to_window(request.all()).df.get_column("station_id").to_list()
    assert "06265" in kept


def test_the_fog_type_is_compared_stripped_and_in_lower_case(monkeypatch: pytest.MonkeyPatch) -> None:
    """A change of the label's case or padding does not bring the fog stations into the validated datasets."""
    catalogue = catalogue_csv("06233", "06260").replace(b",Fog station,", b", FOG Station ,")
    assert b"FOG Station" in catalogue
    _serve(monkeypatch, catalogue=catalogue)
    assert _stations("hourly").get_column("station_id").to_list() == ["06260"]
    assert _stations("10_minutes").get_column("station_id").to_list() == ["06233", "06260"]


def test_the_caribbean_stations_are_no_stations_of_the_annual_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    """No annual file holds block 78 (read 2026-11-11), the monthly files of 2026 do.

    A rank listing near Bonaire at annual answered with three stations that have no data.
    """
    _serve(monkeypatch)
    annual = set(_stations("annual").get_column("station_id"))
    monthly = set(_stations("monthly").get_column("station_id"))
    assert not {"78871", "78990"} & annual
    assert {"78871", "78990"} <= monthly


def test_the_catalogue_is_one_listing_and_one_file_for_every_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Five resolutions cost the two requests of one catalogue (listing and link), not two each.

    The file is held a week, the listing that names the newest one for 12 hours: KNMI makes the file weeks after the
    date in its name, and a new station must not wait a week more.
    """
    served = _serve(monkeypatch)
    df = _stations("10_minutes", "hourly", "daily", "monthly", "annual")
    assert df.get_column("resolution").n_unique() == 5
    assert served.listings == [(CATALOGUE_DATASET, CacheExpiry.TWELVE_HOURS)]
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


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


@pytest.mark.parametrize("where", ["listing", "file"])
def test_a_catalogue_that_is_gone_is_replaced_by_the_latest_files(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path, where: str
) -> None:
    """A 404 of the catalogue's listing or file reads the stations from the latest file of each resolution."""
    payload = _netcdf_of_stations(tmp_path / "latest.nc", ["0-20000-0-06260", "0-20000-0-78990"], None)
    gone = FileNotFoundError("not published")
    served = _serve(
        monkeypatch,
        netcdf=payload,
        listing=gone if where == "listing" else None,
        catalogue=gone if where == "file" else None,
    )
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        df = _stations("daily")
    assert df.get_column("station_id").to_list() == ["06260", "78990"]
    assert "latest.nc" in [name for _dataset, name, _expiry in served.files]
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


@pytest.mark.parametrize("where", ["listing", "file"])
@pytest.mark.parametrize("status", [429, 400])
def test_a_catalogue_that_knmi_refuses_is_no_stations_and_asks_for_no_more(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, where: str, status: int
) -> None:
    """A 429 or another 4xx is the empty list with one warning, not 2 more requests per resolution of a refusing API."""
    refused = _response_error(status)
    served = _serve(
        monkeypatch,
        netcdf=b"never asked for",
        listing=refused if where == "listing" else None,
        catalogue=refused if where == "file" else None,
    )
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        df = _stations("10_minutes", "hourly", "daily")
    assert df.is_empty()
    assert [dataset for dataset, *_ in served.listings] == [CATALOGUE_DATASET]
    assert {dataset for dataset, *_ in served.files} <= {CATALOGUE_DATASET}
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def _listing(monkeypatch: pytest.MonkeyPatch, body: bytes) -> list[tuple[str, CacheExpiry]]:
    """Serve `body` as a 200 answer for every listing, and record the copies that are dropped (url and ttl)."""
    dropped: list[tuple[str, CacheExpiry]] = []

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(body), status=200)

    def drop(url: str, _cache_dir: object, ttl: CacheExpiry, *_args: object, **_kwargs: object) -> None:
        dropped.append((url, ttl))

    monkeypatch.setattr(api, "_download_with_retry", download)
    monkeypatch.setattr(api, "drop_cached_file", drop)
    return dropped


@pytest.mark.parametrize(
    ("body", "kept"),
    [
        pytest.param(b"<html><body>Service unavailable</body></html>", False, id="html"),
        pytest.param(b"", False, id="empty"),
        pytest.param(b'["not", "an", "object"]', False, id="a list"),
        pytest.param(json.dumps({"files": [{"name": "x"}]}).encode(), False, id="no filename"),
        pytest.param(json.dumps({"files": ["csv.csv"]}).encode(), False, id="a file that is a string"),
        pytest.param(json.dumps({"files": [{"filename": 5}]}).encode(), True, id="a filename that is a number"),
        pytest.param(json.dumps({"files": []}).encode(), True, id="no file"),
    ],
)
def test_a_listing_that_is_no_listing_is_dropped_from_the_cache_and_is_the_catalogue_gone(
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    kept: bool,  # noqa: FBT001
) -> None:
    """A 200 that cannot be read as a list of files is not kept for the `ttl` of its listing: dropped, and an error.

    A well-formed listing that names no usable file (`kept`) is an answer of KNMI and is not dropped.
    """
    dropped = _listing(monkeypatch, body)
    dataset, version = api._STATIONS_DATASET  # noqa: SLF001
    answer = api._latest_filename(  # noqa: SLF001
        dataset, version, Settings(auth={"knmi": "stub"}), CacheExpiry.TWELVE_HOURS
    )
    assert isinstance(answer, Exception)
    assert api._without_catalogue(answer, "x") is None  # noqa: SLF001  # the stations are read from the files
    if kept:
        assert dropped == []
    else:
        assert len(dropped) == 1
        assert dropped[0][0].endswith(
            "/datasets/waarneemstations_csv/versions/1.0/files?maxKeys=1&orderBy=filename&sorting=desc"
        )
        assert dropped[0][1] == CacheExpiry.TWELVE_HOURS


def test_a_html_listing_of_the_catalogue_falls_back_to_the_latest_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The station list does not break for the life of a cached listing that is a page of HTML."""
    payload = _netcdf_of_stations(tmp_path / "latest.nc", ["0-20000-0-06260", "0-20000-0-78990"], None)
    html = b"<html><body>Service unavailable</body></html>"
    dropped: list[str] = []

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        if "waarneemstations_csv" in url:
            return File(url=url, content=BytesIO(html), status=200)
        return File(url=url, content=BytesIO(b'{"files": [{"filename": "latest.nc"}]}'), status=200)

    monkeypatch.setattr(api, "_download_with_retry", download)
    monkeypatch.setattr(api, "drop_cached_file", lambda url, *_a, **_k: dropped.append(url))
    monkeypatch.setattr(api, "_fetch_netcdf", lambda *_args: payload)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        df = _stations("daily")
    assert df.select("station_id", "wigos_id").rows() == [
        ("06260", "0-20000-0-06260"),
        ("78990", "0-20000-0-78990"),
    ]
    assert len(dropped) == 1
    assert any("is no list of files" in record.getMessage() for record in caplog.records)
