# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for CHMI observation provider."""

import datetime as dt
import logging
from collections.abc import Callable, Iterator
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.schema import LONG_SCHEMA, STATIONS_SCHEMA
from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.chmi.observation.api import _RESOLUTION_CONFIG, ChmiObservationValues
from wetterdienst.provider.chmi.observation.metadata import LAST_YEAR, ChmiObservationMetadata
from wetterdienst.provider.chmi.observation.parser import (
    parse_chmi_values_aggregate,
    parse_chmi_values_daily,
    parse_chmi_values_subdaily,
)
from wetterdienst.settings import Settings
from wetterdienst.util.network import File, list_remote_directory_fsspec, list_remote_files_fsspec
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

CHEB = "0-20000-0-11406"
UTC = ZoneInfo("UTC")


@pytest.fixture(autouse=True)
def _a_clean_record() -> Iterator[None]:
    """Start each test without the warnings an earlier one recorded in this thread, and leave none behind."""
    begin_response()
    yield
    begin_response()


def _read(df: pl.DataFrame) -> pl.DataFrame:
    """Read the `value` of a parser's frame as the number the core makes of its text (`shape_provider_frame`)."""
    return df.with_columns(pl.col("value").cast(pl.Float64, strict=False))


def _list_files(directories: dict[str, list[str]]) -> Callable[..., list[str]]:
    """Serve the listing of a directory of the portal by the tail of its url, a directory it does not know as empty."""

    def list_files(url: str, *_args: object, **_kwargs: object) -> list[str]:
        for tail, names in directories.items():
            if url.endswith(tail):
                return [f"{url}{name}" for name in names]
        return []

    return list_files


def _serve_catalogue(monkeypatch: pytest.MonkeyPatch, catalogue: bytes, directories: dict[str, list[str]]) -> None:
    monkeypatch.setattr(
        chmi_api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(catalogue), status=200),
    )
    monkeypatch.setattr(chmi_api, "list_remote_files_fsspec", _list_files(directories))


def _stations_of(
    monkeypatch: pytest.MonkeyPatch,
    catalogue: bytes,
    directories: dict[str, list[str]] | None = None,
    parameters: list[tuple[str, ...]] | None = None,
) -> pl.DataFrame:
    """Give the stations the core hands out for a catalogue `meta1.csv` of this content and these directories.

    The directories default to a daily temperature file of each station the catalogue lists.
    """
    if directories is None:
        ids = pl.read_csv(BytesIO(catalogue), infer_schema_length=0)["WSI"].unique().to_list()
        directories = {"/daily/temperature/": [f"dly-{station}-T.csv" for station in ids]}
    _serve_catalogue(monkeypatch, catalogue, directories)
    request = ChmiObservationRequest(parameters=parameters or [("daily", "data", "temperature_air_mean_2m")])
    return request.all().df


def test_chmi_observation_stations_collapse_a_relocated_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """A relocated station is one row: latest position, full extent, an active end as null (GH-2627)."""
    df = _stations_of(
        monkeypatch,
        b"WSI,GH_ID,BEGIN_DATE,END_DATE,FULL_NAME,GEOGR1,GEOGR2,ELEVATION,\n"
        b"0-X,GA,1961-01-01T00:00Z,2000-12-31T23:59Z,Cheb,12.30,50.00,458,\n"
        b"0-X,GA,2001-01-01T00:00Z,3999-12-31T23:59Z,Cheb,12.391389,50.068333,483,\n"
        b"0-Y,GA,1970-01-01T00:00Z,1999-06-30T23:59Z,Closed ,13.0,49.5,300,\n",
    )
    assert df.schema == STATIONS_SCHEMA
    assert df.sort("station_id").to_dicts() == [
        {
            "resolution": "daily",
            "dataset": "data",
            "station_id": "0-X",
            "start_timestamp": dt.datetime(1961, 1, 1, tzinfo=UTC),  # earliest BEGIN_DATE
            "end_timestamp": None,  # END_DATE year 3999 -> active -> null
            "latitude": 50.068333,  # GEOGR2 of the most recent (active) period
            "longitude": 12.391389,  # GEOGR1 of the most recent period
            "elevation": 483.0,
            "name": "Cheb",
            "region": None,
        },
        {
            "resolution": "daily",
            "dataset": "data",
            "station_id": "0-Y",
            "start_timestamp": dt.datetime(1970, 1, 1, tzinfo=UTC),
            "end_timestamp": dt.datetime(1999, 6, 30, 23, 59, tzinfo=UTC),
            "latitude": 49.5,
            "longitude": 13.0,
            "elevation": 300.0,
            "name": "Closed",  # the trailing blank of the name is gone
            "region": None,
        },
    ]


def test_chmi_observation_stations_of_a_catalogue_without_a_row_are_the_empty_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A catalogue with its header and no station is a network without stations, typed as the stations frame is."""
    df = _stations_of(monkeypatch, b"WSI,GH_ID,BEGIN_DATE,END_DATE,FULL_NAME,GEOGR1,GEOGR2,ELEVATION,\n")
    assert df.is_empty()
    assert df.schema == STATIONS_SCHEMA


_CATALOGUE = (
    b"WSI,GH_ID,BEGIN_DATE,END_DATE,FULL_NAME,GEOGR1,GEOGR2,ELEVATION,\n"
    b"0-A,GA,1961-01-01T00:00Z,3999-12-31T23:59Z,Open,12.3,50.0,458,\n"
    b"0-B,GB,1925-01-01T00:00Z,1926-12-31T23:59Z,Closed,13.0,49.5,300,\n"
    b"0-C,GC,1990-01-01T00:00Z,3999-12-31T23:59Z,Rain only,14.0,49.0,200,\n"
    b"0-D,GD,2002-01-01T00:00Z,2003-12-31T23:59Z,Probe,15.0,49.2,250,\n"
)


def _ids(df: pl.DataFrame, resolution: str) -> list[str]:
    return sorted(df.filter(pl.col("resolution").eq(resolution))["station_id"])


def test_chmi_observation_stations_are_those_with_a_file_in_the_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one list `meta1.csv` is narrowed to the stations a daily, monthly or annual file is listed for (GH-3259).

    A station that has files of an element the provider does not read (`TPM`, `API30`) has none, and a file of a
    station the list does not carry (`0-X`, as the monthly files of ids `meta1.csv` lacks) adds no station.
    """
    df = _stations_of(
        monkeypatch,
        _CATALOGUE,
        {
            "/daily/temperature/": ["dly-0-A-T.csv", "dly-0-A-TMA.csv", "dly-0-D-TPM.csv"],
            "/daily/precipitation/": ["dly-0-A-SRA.csv", "dly-0-C-SRA.csv", "dly-0-C-API30.csv"],
            "/monthly/temperature/": ["mly-0-A-T.csv", "mly-0-X-T.csv"],
            "/yearly/precipitation/": ["yrs-0-C-SRA.csv"],
        },
        parameters=[("daily", "data"), ("monthly", "data"), ("annual", "data")],
    )
    assert _ids(df, "daily") == ["0-A", "0-C"]
    assert _ids(df, "monthly") == ["0-A"]
    assert _ids(df, "annual") == ["0-C"]
    assert df.schema == STATIONS_SCHEMA
    assert df.filter(pl.col("station_id").eq("0-C"))["name"].to_list() == ["Rain only"] * 2


def test_chmi_observation_stations_are_those_with_a_file_of_the_requested_elements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parameter lists the stations with a file of its element, a dataset those with a file of any (GH-3295)."""
    directories = {
        "/daily/temperature/": ["dly-0-A-T.csv", "dly-0-B-TMA.csv", "dly-0-D-TPM.csv"],
        "/daily/precipitation/": ["dly-0-A-SRA.csv", "dly-0-C-SRA.csv"],
        "/daily/sunshine/": ["dly-0-C-SSV.csv"],
    }
    for parameters, expected in (
        ([("daily", "data", "temperature_air_mean_2m")], ["0-A"]),
        ([("daily", "data", "temperature_air_max_2m")], ["0-B"]),
        ([("daily", "data", "precipitation_amount")], ["0-A", "0-C"]),
        ([("daily", "data", "sunshine_duration")], ["0-C"]),
        ([("daily", "data", "temperature_air_mean_2m"), ("daily", "data", "sunshine_duration")], ["0-A", "0-C"]),
        ([("daily", "data")], ["0-A", "0-B", "0-C"]),
    ):
        df = _stations_of(monkeypatch, _CATALOGUE, directories, parameters)
        assert _ids(df, "daily") == expected, parameters


@pytest.mark.parametrize("resolution", [Resolution.DAILY, Resolution.MONTHLY, Resolution.ANNUAL])
def test_chmi_observation_every_parameter_of_a_narrowed_resolution_is_an_element_that_is_read(
    resolution: Resolution,
) -> None:
    """A parameter whose `name_original` the config lacks would be left out of the narrowing, silently (GH-3295)."""
    elements = _RESOLUTION_CONFIG[resolution]["elements"]
    parameters = ChmiObservationMetadata[resolution.value].datasets[0].parameters
    assert {parameter.name_original for parameter in parameters} <= set(elements)


def test_chmi_observation_stations_list_only_the_directories_of_the_requested_elements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The directory of an element that was not asked for is not read, and one holding two elements is read once."""
    asked: list[str] = []

    def list_files(url: str, *_args: object, **_kwargs: object) -> list[str]:
        asked.append(url.rsplit("/daily/", 1)[-1])
        return [f"{url}dly-0-A-T.csv", f"{url}dly-0-A-TMA.csv", f"{url}dly-0-C-SRA.csv"]

    _serve_catalogue(monkeypatch, _CATALOGUE, {})
    monkeypatch.setattr(chmi_api, "list_remote_files_fsspec", list_files)
    parameters = [("daily", "data", "temperature_air_mean_2m"), ("daily", "data", "temperature_air_max_2m")]
    df = ChmiObservationRequest(parameters=parameters).all().df
    assert asked == ["temperature/"]
    assert _ids(df, "daily") == ["0-A"]


def test_chmi_observation_stations_of_abroad_are_left_out(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The stations `meta1.csv` lists with a `Z` GH_ID have no file on the portal and are no stations (GH-3589)."""
    catalogue = (
        b"WSI,GH_ID,BEGIN_DATE,END_DATE,FULL_NAME,GEOGR1,GEOGR2,ELEVATION,\n"
        b"0-20000-0-11406,L3CHEB01,2001-01-01T00:00Z,3999-12-31T23:59Z,Cheb,12.391389,50.068333,483,\n"
        b"0-20000-0-04030,ZIS04030,2015-01-01T00:00Z,3999-12-31T23:59Z,Reykjavik,-21.903905,64.127653,51,\n"
        b"0-20000-0-89055,ZAR89055,2010-01-01T00:00Z,2020-01-31T23:59Z,Marambio  Base,56.623056,64.233056,196,\n"
        b"0-203-0-20303032003,O1JAVR01,2025-04-03T16:00Z,3999-12-31T23:59Z,Javorovy,18.627222,49.628333,930,\n"
    )
    # a daily file of each, the Z stations included, so that the reader is what leaves them out of the sub-daily lists
    ids = pl.read_csv(BytesIO(catalogue), infer_schema_length=0)["WSI"].to_list()
    _serve_catalogue(monkeypatch, catalogue, {"/daily/temperature/": [f"dly-{station}-T.csv" for station in ids]})
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.provider.chmi.observation.parser"):
        df = ChmiObservationRequest(parameters=[("10_minutes", "data"), ("hourly", "data")]).all().df
    for resolution in ("10_minutes", "hourly"):
        assert _ids(df, resolution) == ["0-20000-0-11406", "0-203-0-20303032003"]
    assert "0-20000-0-04030, 0-20000-0-89055" in caplog.text


_SUB_DAILY_CATALOGUE = (
    b"WSI,GH_ID,BEGIN_DATE,END_DATE,FULL_NAME,GEOGR1,GEOGR2,ELEVATION,\n"
    b"0-A,GA,1961-01-01T00:00Z,3999-12-31T23:59Z,Open with a file,12.3,50.0,458,\n"
    b"0-B,GB,1925-01-01T00:00Z,1926-12-31T23:59Z,Closed with a file,13.0,49.5,300,\n"
    b"0-C,GC,2009-09-01T00:00Z,3999-12-31T23:59Z,Open and monthly only,14.0,49.0,200,\n"
    b"0-D,GD,2002-01-01T00:00Z,2018-03-01T00:00Z,Closed in 2018,15.0,49.2,250,\n"
    b"0-E,GE,2002-01-01T00:00Z,2017-12-31T23:59Z,Closed in 2017,15.5,49.3,260,\n"
    b"0-F,GF,1990-01-01T00:00Z,3999-12-31T23:59Z,Open with a file not read,16.0,49.4,270,\n"
)
_SUB_DAILY_DIRECTORIES = {
    "/daily/temperature/": ["dly-0-A-T.csv", "dly-0-B-T.csv", "dly-0-E-TMA.csv", "dly-0-F-TPM.csv"],
    "/daily/precipitation/": ["dly-0-D-SRA.csv", "dly-0-F-API30.csv"],
    "/monthly/temperature/": ["mly-0-C-T.csv"],
}


@pytest.mark.parametrize("parameters", [[("10_minutes", "data")], [("hourly", "data")]])
def test_chmi_observation_sub_daily_stations_can_have_files(
    monkeypatch: pytest.MonkeyPatch, parameters: list[tuple[str, ...]]
) -> None:
    """The 10 minute and hourly lists hold the stations whose period ends in 2018 or later and that have a daily file.

    Their files begin with 2018 and every station that has one has a daily file (GH-3623). Out go a station that
    closed before 2018 (`0-B`, `0-E`, which have a daily file), one with no daily file of an element that is read
    (`0-C`, monthly only; `0-F`, a file of `TPM` and `API30`), and the stations of both kinds stay out of the
    others; one that ended in 2018 stays (`0-D`).
    """
    df = _stations_of(monkeypatch, _SUB_DAILY_CATALOGUE, _SUB_DAILY_DIRECTORIES, parameters)
    assert _ids(df, parameters[0][0]) == ["0-A", "0-D"]
    assert df.schema == STATIONS_SCHEMA


def test_chmi_observation_sub_daily_stations_read_the_daily_directories_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The year directories of the sub-daily files are not listed (1.6 MB each); the daily ones are, for any element."""
    asked: list[str] = []

    def list_files(url: str, *_args: object, **_kwargs: object) -> list[str]:
        asked.append(url.removeprefix(chmi_api._BASE_URL))  # noqa: SLF001
        return [f"{url}dly-0-A-T.csv"]

    _serve_catalogue(monkeypatch, _SUB_DAILY_CATALOGUE, {})
    monkeypatch.setattr(chmi_api, "list_remote_files_fsspec", list_files)
    df = ChmiObservationRequest(parameters=[("10_minutes", "data"), ("hourly", "data")]).all().df
    assert _ids(df, "10_minutes") == _ids(df, "hourly") == ["0-A"]
    daily = _RESOLUTION_CONFIG[Resolution.DAILY]["elements"]
    assert set(asked) == {f"/data/daily/{category}/" for category in {element[0] for element in daily.values()}}


def test_chmi_observation_stations_raise_when_a_directory_cannot_be_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A listing that fails is raised, not read as a resolution whose stations all have no file."""

    def list_files(url: str, *_args: object, **_kwargs: object) -> list[str]:
        raise NoInternetError(url)

    _serve_catalogue(monkeypatch, _CATALOGUE, {})
    monkeypatch.setattr(chmi_api, "list_remote_files_fsspec", list_files)
    with pytest.raises(NoInternetError, match="/daily/"):
        ChmiObservationRequest(parameters=[("daily", "data")]).all()


def test_chmi_observation_stations_raise_when_no_directory_lists_a_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Directories that list no file of a requested element are a portal that changed, not no stations."""
    _serve_catalogue(
        monkeypatch,
        _CATALOGUE,
        {"/monthly/temperature/": ["mly-0-A-TPM.csv", "mly-0-A-TMA.csv", "readme.txt"]},
    )
    with pytest.raises(DownloadError, match=r"/monthly/.*for T"):
        ChmiObservationRequest(parameters=[("monthly", "data", "temperature_air_mean_2m")]).all()


def test_parse_chmi_values_daily_selects_timefunc_and_truncates() -> None:
    """Daily parsing keeps only the requested TIMEFUNC and normalises the timestamp to the day."""
    content = (
        b"STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
        b"0-X,T,AVG,2020-01-01T00:00Z,-3.0,,0.0,\n"
        b"0-X,T,20:00,2020-01-01T20:00Z,-1.0,,0.0,\n"  # different TIMEFUNC -> excluded
        b"0-X,T,AVG,2020-01-02T00:00Z,-2.0,,0.0,\n"
    )
    df = _read(parse_chmi_values_daily(content, element="T", timefunc="AVG"))
    assert df.to_dicts() == [
        {"timestamp": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "T", "value": -3.0, "quality_flags": "0"},
        {"timestamp": dt.datetime(2020, 1, 2, tzinfo=UTC), "parameter": "T", "value": -2.0, "quality_flags": "0"},
    ]
    # a 20:00-term reading is truncated back to the calendar day (not kept at 20:00)
    df_max = _read(parse_chmi_values_daily(content, element="T", timefunc="20:00"))
    assert df_max.to_dicts() == [
        {"timestamp": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "T", "value": -1.0, "quality_flags": "0"}
    ]


def test_parse_chmi_values_subdaily_keeps_native_timestamp() -> None:
    """Sub-daily parsing keeps the native timestamp (no TIMEFUNC, no truncation)."""
    content = (
        b"STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
        b"0-X,T,2020-01-01T00:00Z,-2.8,,0.0,\n"
        b"0-X,T,2020-01-01T00:10Z,-2.7,,0.0,\n"
    )
    df = _read(parse_chmi_values_subdaily(content, element="T"))
    assert df.to_dicts() == [
        {"timestamp": dt.datetime(2020, 1, 1, 0, 0, tzinfo=UTC), "parameter": "T", "value": -2.8, "quality_flags": "0"},
        {
            "timestamp": dt.datetime(2020, 1, 1, 0, 10, tzinfo=UTC),
            "parameter": "T",
            "value": -2.7,
            "quality_flags": "0",
        },
    ]


def test_parse_chmi_values_aggregate_pins_both_functions() -> None:
    """Monthly/annual parsing must pin TIMEFUNCTION *and* MDFUNCTION to select a single series."""
    monthly = (
        b"STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,T,2020,1,AVG,AVG,1.1,,,\n"
        b"0-X,T,2020,1,AVG,MAX,8.0,,,\n"  # same TIMEFUNCTION, different MDFUNCTION -> excluded
        b"0-X,T,2020,1,AVG,MIN,-9.0,,,\n"
    )
    df = _read(parse_chmi_values_aggregate(monthly, element="T", timefunc="AVG", mdfunc="AVG", has_month=True))
    assert df.to_dicts() == [
        {"timestamp": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "T", "value": 1.1, "quality_flags": None}
    ]

    # precipitation must select the SUM (monthly total), not another MDFUNCTION
    precip = (
        b"STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,SRA,2020,1,06:00,SUM,21.3,,,\n"
        b"0-X,SRA,2020,1,06:00,MAX,7.0,,,\n"
    )
    df_precip = _read(
        parse_chmi_values_aggregate(precip, element="SRA", timefunc="06:00", mdfunc="SUM", has_month=True)
    )
    assert df_precip.to_dicts() == [
        {"timestamp": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "SRA", "value": 21.3, "quality_flags": None}
    ]


def test_parse_chmi_values_aggregate_annual_has_no_month() -> None:
    """Annual files carry no MONTH column; the date is the year start."""
    annual = (
        b"STATION,ELEMENT,YEAR,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n0-X,T,2018,AVG,AVG,9.7,,,\n"
    )
    df = _read(parse_chmi_values_aggregate(annual, element="T", timefunc="AVG", mdfunc="AVG", has_month=False))
    assert df.to_dicts() == [
        {"timestamp": dt.datetime(2018, 1, 1, tzinfo=UTC), "parameter": "T", "value": 9.7, "quality_flags": None}
    ]


def test_parse_chmi_values_aggregate_carries_repeat_and_interrupted() -> None:
    """The `*` of FLAG_REPEAT and the `I` of FLAG_INTERRUPTED are `repeat:*` and `interrupted:I` (GH-2763).

    The API reads no `MAX`/`MIN` series, so `repeat:*` is pinned on the parser alone.

    The rows are the shapes of `mly-0-20000-0-11406-T.csv` (a repeated extreme, `*`) and
    `mly-0-20000-0-11406-Fmax.csv` (a value from a period with missing daily values, `I`).
    """
    monthly = (
        b"STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,T,1863,10,20:00,MAX,13.3,*,,\n"  # repeat only
        b"0-X,T,1863,11,20:00,MAX,9.0,,I,\n"  # interrupted only
        b"0-X,T,1863,12,20:00,MAX,4.0,*,I,\n"  # both
        b"0-X,T,1864,1,20:00,MAX,2.0,,,\n"  # neither
        b"0-X,T,1864,2,20:00,MAX,3.0, , ,\n"  # blank, not set
    )
    df = _read(parse_chmi_values_aggregate(monthly, element="T", timefunc="20:00", mdfunc="MAX", has_month=True))
    assert df.get_column("quality_flags").to_list() == [
        "repeat:*",
        "interrupted:I",
        "repeat:*,interrupted:I",
        None,
        None,
    ]
    assert df.get_column("value").to_list() == [13.3, 9.0, 4.0, 2.0, 3.0]

    annual = (
        b"STATION,ELEMENT,YEAR,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,T,1864,AVG,MIN,-16.1,*,I,\n"
    )
    df_annual = parse_chmi_values_aggregate(annual, element="T", timefunc="AVG", mdfunc="MIN", has_month=False)
    assert df_annual.get_column("quality_flags").to_list() == ["repeat:*,interrupted:I"]


def test_parse_chmi_values_aggregate_interrupted_on_the_series_the_api_reads() -> None:
    """`I` shows as `interrupted:I` on the selections the API makes: T AVG/AVG and SRA 06:00/SUM (GH-2763)."""
    mean = (
        b"STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,T,2005,1,AVG,AVG,-1.2,,I,\n"
        b"0-X,T,2005,2,AVG,AVG,0.4,,,\n"
        b"0-X,T,2005,3,AVG,MAX,9.0,*,I,\n"  # another MDFUNCTION: not selected
    )
    df = _read(parse_chmi_values_aggregate(mean, element="T", timefunc="AVG", mdfunc="AVG", has_month=True))
    assert df.get_column("value").to_list() == [-1.2, 0.4]
    assert df.get_column("quality_flags").to_list() == ["interrupted:I", None]

    total = (
        b"STATION,ELEMENT,YEAR,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,SRA,2005,06:00,SUM,512.0,,I,\n"
    )
    df_total = parse_chmi_values_aggregate(total, element="SRA", timefunc="06:00", mdfunc="SUM", has_month=False)
    assert df_total.get_column("quality_flags").to_list() == ["interrupted:I"]


def test_parse_chmi_values_daily_has_no_aggregate_flag_tokens() -> None:
    """The daily files have no FLAG_REPEAT or FLAG_INTERRUPTED column: `quality_flags` is the same as before."""
    content = (
        b"STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
        b"0-X,SRA,06:00,2020-01-01T06:00Z,0.0,T,0.0,\n"
        b"0-X,SRA,06:00,2020-01-02T06:00Z,1.2,,3.0,\n"
    )
    df = parse_chmi_values_daily(content, element="SRA", timefunc="06:00")
    assert df.get_column("quality_flags").to_list() == ["0,element:T", "3"]


def _values(resolution: str, start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    return (
        ChmiObservationRequest(
            parameters=[(resolution, "data")],
            start=start,
            end=end,
        )
        .filter_by_station_id(CHEB)
        .values()
        .all()
        .df
    )


def _value_of(df: pl.DataFrame, parameter: str, date: dt.datetime) -> float:
    return df.filter(pl.col("parameter").eq(parameter), pl.col("timestamp").eq(date)).get_column("value").item()


@pytest.mark.remote
def test_chmi_observation_stations() -> None:
    """Station metadata for Cheb matches the CHMI catalogue."""
    request = ChmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id(CHEB)
    df = request.df
    assert df.select(
        pl.exclude("latitude", "longitude", "start_timestamp", "end_timestamp", "elevation")
    ).to_dicts() == [
        {
            "resolution": "daily",
            "dataset": "data",
            "station_id": CHEB,
            "name": "Cheb",
            "region": None,
        },
    ]
    assert df["latitude"].item() == pytest.approx(50.068333)
    assert df["longitude"].item() == pytest.approx(12.391389)
    assert df["elevation"].item() == pytest.approx(483.0)
    assert df["start_timestamp"].item() == dt.datetime(1863, 10, 1, tzinfo=UTC)
    assert df["end_timestamp"].item() is None


@pytest.mark.remote
def test_chmi_observation_values_10_minutes() -> None:
    """10-minute values at Cheb for 2020-01-01 00:00 match the CHMI reference values."""
    df = _values("10_minutes", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 1, 0, 10, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_air_2m", when) == pytest.approx(-2.8)
    assert _value_of(df, "humidity_relative", when) == pytest.approx(0.92)
    assert _value_of(df, "pressure_air_site", when) == pytest.approx(975.8)
    assert _value_of(df, "wind_speed", when) == pytest.approx(1.3)


@pytest.mark.remote
def test_chmi_observation_values_hourly() -> None:
    """Hourly values at Cheb for 2020-01-01 00:00 match the CHMI reference values."""
    df = _values("hourly", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 1, 1, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_dew_point_2m", when) == pytest.approx(-3.9)
    assert _value_of(df, "pressure_air_site", when) == pytest.approx(975.8)
    assert _value_of(df, "precipitation_amount", when) == pytest.approx(0.0)
    assert _value_of(df, "pressure_air_sea_level", when) == pytest.approx(1037.7)


@pytest.mark.remote
def test_chmi_observation_values_hourly_after_2024_have_the_sea_level_pressure_only() -> None:
    """CHMI publishes `P_hm` for 2025 and the answer says that `P` is not (GH-3413)."""
    df = _values("hourly", dt.datetime(2025, 1, 1, tzinfo=UTC), dt.datetime(2025, 1, 1, 1, tzinfo=UTC))
    when = dt.datetime(2025, 1, 1, tzinfo=UTC)
    assert _value_of(df, "pressure_air_sea_level", when) == pytest.approx(1028.6)
    assert "pressure_air_site" not in df["parameter"].unique().to_list()
    assert [warning["code"] for warning in recorded_warnings()] == ["parameter-ended"]


@pytest.mark.remote
def test_chmi_observation_hourly_station_pressure_has_no_file_after_2024() -> None:
    """The upstream fact `LAST_YEAR` rests on: the directories of 2025 and later list no `P` file (GH-3413).

    The reader no longer asks for those files, so only the listing can see CHMI publish them again; this test is red
    then, and the entry of `LAST_YEAR` is to go.
    """
    settings = Settings(cache_disable=True)
    last_year = LAST_YEAR["hourly"]["P"][0]
    url = f"{chmi_api._BASE_URL}/data/1hour/synop/"  # noqa: SLF001
    # a year directory that is not there (2026 is not, 2026-10-25) lists as no file
    for year in range(last_year + 1, dt.datetime.now(tz=UTC).year + 1):
        names = [
            name.rsplit("/", 1)[-1]
            for name in list_remote_files_fsspec(f"{url}{year}/", settings, CacheExpiry.METAINDEX)
        ]
        assert names or year > last_year + 1, f"CHMI lists no hourly file for {year}"
        assert not [name for name in names if "-P-" in name], f"CHMI publishes hourly P files for {year}"
        assert not names or any("-P_hm-" in name for name in names)


@pytest.mark.remote
@pytest.mark.parametrize(
    ("path", "category", "prefix", "resolution"),
    [("10min", "temperature", "10m", "10_minutes"), ("1hour", "precipitation", "1h", "hourly")],
)
def test_chmi_observation_sub_daily_stations_with_files_are_listed(
    path: str, category: str, prefix: str, resolution: str
) -> None:
    """The two facts the sub-daily station lists rest on (GH-3623), which the portal does not promise.

    The files begin with 2018 (no year directory of an earlier one), so a station whose period ended before it has
    none, and every station with a file in the latest year has a daily file of an element that is read. Both fail
    when CHMI publishes older years or sub-daily files for a station without daily ones; the list would then drop
    stations that have files, and this test is red.
    """
    settings = Settings(cache_disable=True)
    url = f"{chmi_api._BASE_URL}/data/{path}/{category}/"  # noqa: SLF001
    years = sorted(
        int(entry["name"].rstrip("/").rsplit("/", 1)[-1])
        for entry in list_remote_directory_fsspec(url, settings, CacheExpiry.METAINDEX)
        if entry["type"] == "directory"
    )
    assert years, f"CHMI lists no year directory under {url}"
    assert years[0] >= chmi_api.SUBDAILY_FIRST_YEAR, f"CHMI lists {resolution} files of {years[0]}, before 2018"
    names = [
        file.rsplit("/", 1)[-1]
        for file in list_remote_files_fsspec(f"{url}{years[-1]}/", settings, CacheExpiry.METAINDEX)
    ]
    with_file = {name.removeprefix(f"{prefix}-").rsplit("-", 2)[0] for name in names if name.startswith(f"{prefix}-")}
    assert with_file, f"CHMI lists no {resolution} file for {years[-1]}"
    daily = _RESOLUTION_CONFIG[Resolution.DAILY]
    assert with_file <= chmi_api._stations_with_file(daily, set(daily["elements"]), settings)  # noqa: SLF001
    listed = set(ChmiObservationRequest(parameters=[(resolution, "data")]).all().df["station_id"])
    assert with_file <= listed, f"{len(with_file - listed)} stations with a {resolution} file are not listed"


@pytest.mark.remote
def test_chmi_observation_values_daily() -> None:
    """Daily values at Cheb for 2020-01-01 match the CHMI reference values."""
    df = _values("daily", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 2, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert df["station_id"].unique().to_list() == [CHEB]
    assert _value_of(df, "temperature_air_mean_2m", when) == pytest.approx(-3.0)
    assert _value_of(df, "temperature_air_max_2m", when) == pytest.approx(1.5)
    assert _value_of(df, "temperature_air_min_2m", when) == pytest.approx(-6.9)
    assert _value_of(df, "precipitation_amount", when) == pytest.approx(0.0)
    assert _value_of(df, "wind_speed_mean", when) == pytest.approx(0.8)
    assert _value_of(df, "wind_speed_max", when) == pytest.approx(3.7)
    assert _value_of(df, "pressure_air_site_mean", when) == pytest.approx(974.9)
    assert _value_of(df, "snow_depth", when) == pytest.approx(0.0)
    # CHMI reports humidity in percent; wetterdienst stores it as a fraction
    assert _value_of(df, "humidity_relative_mean", when) == pytest.approx(0.92)
    # CHMI reports sunshine in hours; wetterdienst stores it in seconds (5.9 h -> 21240 s)
    assert _value_of(df, "sunshine_duration", when) == pytest.approx(21240.0)


@pytest.mark.remote
def test_chmi_observation_values_monthly() -> None:
    """Monthly values at Cheb for 2020-01 match the CHMI reference values (means and sum)."""
    df = _values("monthly", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 2, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_air_mean_2m", when) == pytest.approx(1.1)
    # the mean of the daily maxima and minima, not the month's extremes (12.9 and -9.6 at Cheb)
    assert _value_of(df, "temperature_air_max_2m_mean", when) == pytest.approx(3.7)
    assert _value_of(df, "temperature_air_min_2m_mean", when) == pytest.approx(-1.5)
    # precipitation is the monthly total (MDFUNCTION SUM), not an average
    assert _value_of(df, "precipitation_amount", when) == pytest.approx(21.3)


@pytest.mark.remote
def test_chmi_observation_values_annual() -> None:
    """Annual values at Cheb for 2018 match the CHMI reference values (means and sum)."""
    df = _values("annual", dt.datetime(2018, 1, 1, tzinfo=UTC), dt.datetime(2018, 1, 2, tzinfo=UTC))
    when = dt.datetime(2018, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_air_mean_2m", when) == pytest.approx(9.7)
    assert _value_of(df, "temperature_air_max_2m_mean", when) == pytest.approx(14.9)
    assert _value_of(df, "temperature_air_min_2m_mean", when) == pytest.approx(5.0)
    assert _value_of(df, "precipitation_amount", when) == pytest.approx(465.6)


@pytest.mark.parametrize("resolution", ["monthly", "annual"])
@pytest.mark.parametrize(("element", "extreme"), [("TMA", "max"), ("TMI", "min")])
def test_chmi_observation_period_extremes_are_named_for_the_function_they_are_read_with(
    resolution: str,
    element: str,
    extreme: str,
) -> None:
    """A monthly or annual TMA/TMI is the mean of the daily extremes, so it must not carry the extreme's name.

    The daily files hold the day's extreme, read at 20:00. The monthly and annual files hold that
    daily value combined over the period, and the series this provider reads is MDFUNCTION `AVG`, so
    the number is the mean of the daily maxima (3.7 for Cheb in January 2020, whose warmest day
    reached 12.9) -- `temperature_air_max_2m_mean`, not `temperature_air_max_2m`. The name follows
    the function the series is pinned to, so pinning `MAX` instead would have to rename it back.
    """
    mdfunc = _RESOLUTION_CONFIG[Resolution(resolution)]["elements"][element][2]
    name = f"temperature_air_{extreme}_2m" + ("_mean" if mdfunc == "AVG" else "")
    names = {parameter.name_original: parameter.name for parameter in ChmiObservationMetadata[resolution]["data"]}
    assert names[element] == name
    # the daily files carry the extreme itself, whatever the period files do
    daily = {parameter.name_original: parameter.name for parameter in ChmiObservationMetadata["daily"]["data"]}
    assert daily[element] == f"temperature_air_{extreme}_2m"


def test_chmi_daily_mean_temperature_weighs_the_20_00_observation_twice() -> None:
    """The daily mean temperature is (T06 + T13 + 2 T20) / 4, not the average of the three observations (GH-3136).

    The first two days of the daily file of Cheb (1863-10-01 and 1863-10-02) as CHMI writes them: the weighted mean
    gives its "AVG" (10.05 is 10.1, 9.75 is 9.8), the plain average (10.23 and 9.73) does not. It held for all 75,261
    days of five stations on 2026-10-21, while for the humidity, pressure and wind speed the plain average does. The
    description says which it is.
    """
    content = (
        b"STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
        b"0-20000-0-11406,T,06:00,1863-10-01T06:00Z,7.4,,0.0,\n"
        b"0-20000-0-11406,T,13:00,1863-10-01T13:00Z,13.8,,0.0,\n"
        b"0-20000-0-11406,T,20:00,1863-10-01T20:00Z,9.5,,0.0,\n"
        b"0-20000-0-11406,T,AVG,1863-10-01T00:00Z,10.1,,0.0,\n"
        b"0-20000-0-11406,T,06:00,1863-10-02T06:00Z,7.0,,0.0,\n"
        b"0-20000-0-11406,T,13:00,1863-10-02T13:00Z,12.4,,0.0,\n"
        b"0-20000-0-11406,T,20:00,1863-10-02T20:00Z,9.8,,0.0,\n"
        b"0-20000-0-11406,T,AVG,1863-10-02T00:00Z,9.8,,0.0,\n"
    )
    terms = {
        timefunc: _read(parse_chmi_values_daily(content, element="T", timefunc=timefunc)).get_column("value").to_list()
        for timefunc in ("06:00", "13:00", "20:00", "AVG")
    }
    for day, mean in enumerate(terms["AVG"]):
        t06, t13, t20 = terms["06:00"][day], terms["13:00"][day], terms["20:00"][day]
        assert round((t06 + t13 + 2 * t20) / 4 + 1e-9, 1) == mean
        assert round((t06 + t13 + t20) / 3, 1) != mean
    descriptions = {p.name_original: p.description for p in ChmiObservationMetadata["daily"]["data"]}
    assert "(T06 + T13 + 2 T20) / 4" in descriptions["T"]
    assert "not their plain average" in descriptions["T"]
    for element in ("H", "P", "F"):
        assert "plain average" in descriptions[element]
        assert "2 T20" not in descriptions[element]
    for resolution in ("monthly", "annual"):
        by_element = {p.name_original: p.description for p in ChmiObservationMetadata[resolution]["data"]}
        assert "(T06 + T13 + 2 T20) / 4" in by_element["T"]


def test_parse_chmi_values_returns_the_quality_code_as_the_whole_number_meta4_lists() -> None:
    """The QUALITY code of a daily or sub-daily row is returned as "0" to "5", the keys of metadata/meta4.csv (GH-2018).

    meta4.csv (checked 2026-10-11): "0 Good", "1 Suspect", "2 Poor", "3 Estimated", "4 Missing", "5 Unknown" -- the
    codes "assigned to each value in the data file". The files write them as "0.0", "3.0", "4.0" (all three seen in
    dly-0-20000-0-11406-TMA.csv). The FLAG letter beside it is the element's own (meta3.csv: "SRA,T,Neměřitelné
    množství", an amount too small to measure) and follows as `element:T`.
    """
    content = (
        b"STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
        b"0-X,SRA,06:00,2020-01-01T06:00Z,0.0,T,0.0,\n"
        b"0-X,SRA,06:00,2020-01-02T06:00Z,1.5,,3.0,\n"
        b"0-X,SRA,06:00,2020-01-03T06:00Z,,,4.0,\n"
    )
    df = parse_chmi_values_daily(content, element="SRA", timefunc="06:00")
    assert df.get_column("quality_flags").to_list() == ["0,element:T", "3", "4"]


@pytest.mark.parametrize(
    ("start", "end", "months"),
    [
        # 2020-02-01 00:30 and 2020-03-01 00:30 in Prague (UTC+1) are 23:30 UTC of the last day of the month before
        (
            dt.datetime(2020, 2, 1, 0, 30, tzinfo=ZoneInfo("Europe/Prague")),
            dt.datetime(2020, 3, 1, 0, 30, tzinfo=ZoneInfo("Europe/Prague")),
            ["202001", "202002"],
        ),
        ("2020-02-01T00:30:00+01:00", "2020-03-01T00:30:00+01:00", ["202001", "202002"]),
        # the same instants written in UTC
        (
            dt.datetime(2020, 1, 31, 23, 30, tzinfo=UTC),
            dt.datetime(2020, 2, 29, 23, 30, tzinfo=UTC),
            ["202001", "202002"],
        ),
    ],
    ids=["named zone", "fixed offset", "utc"],
)
def test_chmi_observation_month_files_follow_the_utc_month_of_the_bounds(
    monkeypatch: pytest.MonkeyPatch,
    start: str | dt.datetime,
    end: str | dt.datetime,
    months: list[str],
) -> None:
    """Test that the month files of the sub-daily layouts are named by the UTC month of the bounds (GH-2682).

    The files hold UTC time stamps, so a bound in Prague time just past midnight on the first of a month still
    belongs to the month before in UTC, and that month's file is the one to read.
    """
    asked: list[str] = []

    def download(_self: object, url: str, _settings: object, _station_id: str) -> None:
        # the dataset is collected whole: the months of the one element asked for are the ones counted
        if f"-{CHEB}-T-" in url:
            asked.append(url.rsplit("-", 1)[-1].removesuffix(".csv"))

    monkeypatch.setattr(ChmiObservationValues, "_download", download)
    request = ChmiObservationRequest(parameters=[("10_minutes", "data", "temperature_air_2m")], start=start, end=end)
    values = ChmiObservationValues(sr=stations_result(request, "10_minutes", "data", CHEB))

    df = values.all().df
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
    assert asked == months


def test_chmi_observation_debug_line_of_a_missing_file_names_the_url_without_its_query(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The DEBUG line of a file the portal lacks shows the URL as every provider does, with no query (GH-3394)."""
    url = "https://opendata.chmi.cz/meteorology/climate/historical_csv/data/daily/temperature/dly-X-T.csv"
    monkeypatch.setattr(
        chmi_api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=OSError("404"), status=404),
    )
    values = object.__new__(ChmiObservationValues)
    with caplog.at_level("DEBUG", logger="wetterdienst"):
        assert values._download(f"{url}?sig=SECRET#frag", Settings(cache_disable=True), "X") is None  # noqa: SLF001

    (message,) = [record.getMessage() for record in caplog.records if "No CHMI file" in record.getMessage()]
    assert message.startswith(f"No CHMI file {url} for station X")
    assert "SECRET" not in message
