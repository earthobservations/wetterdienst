# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD road weather API."""

import datetime as dt
import logging
import re
from io import BytesIO
from zoneinfo import ZoneInfo

import pandas as pd
import polars as pl
import pytest

from tests.conftest import BUFR_AVAILABLE, IS_CI, IS_WINDOWS
from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.road.api import DwdRoadRequest, DwdRoadStationGroup
from wetterdienst.util.network import File, download_files, list_remote_files_fsspec

_PARSED_SCHEMA_FOR_TEST = {
    "station_id": pl.String,
    "date": pl.Datetime(time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
    "quality": pl.Float64,
}


@pytest.mark.skipif(IS_CI and IS_WINDOWS, reason="permission with storage in CI on Windows")
@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.remote
def test_dwd_road_weather() -> None:
    """Test fetching of DWD road weather data."""
    request = DwdRoadRequest(parameters=[("15_minutes", "data", "temperature_air_mean_2m")]).filter_by_station_id(
        "A006",
    )
    item = request.to_dict()["stations"][0]
    assert item == {
        "resolution": "15_minutes",
        "dataset": "data",
        "station_id": "A006",
        "start_date": None,
        "end_date": None,
        "latitude": 54.8892,
        "longitude": 8.9087,
        "height": 2.0,
        "name": "Boeglum",
        "state": "SH",
        "road_name": "L5S",
        "road_sector": "2",
        "road_surface_type": 1,
        "road_surroundings_type": 2,
        "road_type": 1,
        "station_group": "KK",
    }
    values = request.values.all().df.drop_nulls(subset="value")
    if values.is_empty():
        # this station, or its whole group, published nothing for the window -- ordinary for a
        # network where groups go quiet, and not something this test can tell from a regression
        # without asking the network what it ought to have sent. That question belongs to
        # `test_dwd_road_weather_keeps_the_station_that_was_asked_for`, which asks it of data it
        # knows: four rewrites of a guard here each traded one wrong answer for another
        pytest.skip("no reading published for the requested window")
    assert -40 <= values.get_column("value").min() <= 40  # approx. -+40 K


@pytest.mark.xfail(reason="number of station groups may change")
def test_dwd_road_weather_station_groups() -> None:
    """Test fetching of DWD road weather station groups."""
    url = "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/"
    files = list_remote_files_fsspec(
        url=url,
        settings=Settings(),
        cache_expiry=CacheExpiry.METAINDEX,
    )
    files = {file[len(url) :].split("/")[0] for file in files}
    if "quality-assured" in files:
        files.remove("quality-assured")
    assert files == {group.value for group in DwdRoadStationGroup}


def _stub_stations(station_ids: tuple[str, ...] = ("A006",)) -> StationsResult:
    """Stand a road station up rather than look one up.

    Asked of the real index, a test about frame handling would find no station the day A006 leaves
    the network, walk no stations, and pass on an empty frame having exercised nothing.
    """
    request = DwdRoadRequest(parameters=[("15_minutes", "data", "temperature_air_mean_2m")])
    df_stations = pl.DataFrame(
        [
            {
                "resolution": "15_minutes",
                "dataset": "data",
                "station_id": station_id,
                "start_date": None,
                "end_date": None,
                "latitude": 54.8892,
                "longitude": 8.9087,
                "height": 2.0,
                "name": "Boeglum",
                "state": "SH",
                "station_group": "DD",
            }
            for station_id in station_ids
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
            "station_group": pl.String,
        },
        orient="row",
    )
    return StationsResult(
        stations=request,
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.BY_STATION_ID,
    )


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_group_with_nothing_published(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station group with no usable file is an empty result, not a broken frame.

    The road stations report in fifteen-minute batches and four of the groups are already known to
    go quiet, so a window with no file behind it -- or one holding only the 142-byte empty files of
    GH-1526 -- is an ordinary outcome. It used to raise `ColumnNotFoundError: unable to find column
    "station_id"; valid columns: []` out of the middle of the collection walk, because the frame
    standing for "nothing here" was filtered before anyone asked whether it held anything.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    # the group publishes nothing for the window, which is the whole of what upstream has to say
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])
    df = _stub_stations().values.all().df
    assert df.is_empty()
    # and it is an answer rather than a hole: the columns a caller asks the result for are there
    assert set(df.columns) == {"station_id", "resolution", "dataset", "parameter", "date", "value", "quality"}


def _listing(*names: str) -> list[str]:
    return [f"https://example.com/road/DD/{name}" for name in names]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.parametrize(
    ("listed", "expected_files", "expected_warning"),
    [
        # a group that publishes nothing lists nothing, or lists itself and nothing else -- named
        # for the group, or not named at all, depending on the trailing slash of the URL asked for
        ([], 0, False),
        (_listing(""), 0, False),
        (_listing("DD"), 0, False),
        # the alias of each family a group publishes under duplicates that family's newest file,
        # and is no file of its own. FN publishes two
        (_listing("swis2-ISXD70_DWDD_LATEST-DD---bin"), 0, False),
        (
            _listing(
                "swis2-ISXD70_DWFN_LATEST-BY---bin",
                "swis2-ISXD70_DWNB_LATEST-NB---bin",
                "swis2-ISXD70_DWFN_141915-2609141915-BY---bin",
            ),
            1,
            False,
        ),
        # a name that is neither, whether or not files were found beside it
        (_listing("swis2-ISXD70_DWDD_renamed-DD---bin"), 0, True),
        (
            _listing(
                "swis2-ISXD70_DWDD_LATEST-DD---bin",
                "swis2-ISXD70_DWDD_141915-2609141915-DD---bin",
                "swis2-ISXD70_DWNB_renamed-NB---bin",
            ),
            1,
            True,
        ),
    ],
)
def test_dwd_road_weather_tells_a_quiet_group_from_a_rename(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    listed: list[str],
    expected_files: int,
    *,
    expected_warning: bool,
) -> None:
    """A name the index cannot read is worth saying; the ones it drops every time are not.

    Two entries are dropped as a matter of course -- the group listing itself, and the `LATEST`
    alias each family keeps -- and warning about those would be a false alarm on every poll. A name
    that is neither is one the index cannot read, and it is asked of every listing rather than only
    of one that came back empty: a group publishing under two families, as FN does, loses half its
    readings when one is renamed, and that drop is otherwise as quiet as the alias's.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: listed)
    values = _stub_stations().values
    with caplog.at_level(logging.INFO):
        df = values._create_file_index_for_dwd_road_weather_station(DwdRoadStationGroup.DD)  # noqa: SLF001

    assert df.height == expected_files
    warnings = [record for record in caplog.records if "the file names may have changed" in record.message]
    assert bool(warnings) is expected_warning, caplog.text
    if expected_warning:
        assert warnings[0].levelno == logging.WARNING
    # and the quiet group still says what is actually the case
    quiet = [record for record in caplog.records if record.message == "No files found for DD."]
    assert bool(quiet) is (expected_files == 0)


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_file_that_decodes_to_nothing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A file that survives the size filter and decodes to nothing is nothing, not a broken frame.

    The size filter turns the empty files away by their exact length, which is a guess at a shape
    rather than a reading of one. A file holding no subsets at some other length reaches the parse,
    where an empty read took the select into a column that was not there.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: pd.DataFrame())
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    file = File(url="a-file-of-no-readings", content=BytesIO(b"not a real bufr message"), status=200)
    parse = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data  # noqa: SLF001
    with caplog.at_level(logging.INFO):
        df = parse(file, parameters)
    assert df.is_empty()
    # in the shape the files that do hold something come back in, so the two concatenate
    assert set(df.columns) == {"station_id", "date", "parameter", "value", "quality"}
    assert df.schema["date"] == pl.Datetime(time_zone="UTC")
    # once for the file: the whole of it is one read now, so there is one thing to say
    assert [record.message for record in caplog.records] == ["a-file-of-no-readings holds no readings"]


def _flat(*subsets: dict[str, object]) -> pd.DataFrame:
    """One subset per row, every key named by its rank, as a flat read returns them.

    A road file holds one subset per station, and the station's road sensors sit inside it as a
    replication -- so a second sensor is `#2#roadSurfaceTemperature` beside `#1#`, and not a second
    row.
    """
    keys = {"#1#year": 2026, "#1#month": 9, "#1#day": 13, "#1#hour": 12, "#1#minute": 0}
    return pd.DataFrame([{**keys, **subset} for subset in subsets])


def _parse(monkeypatch: pytest.MonkeyPatch, df: pd.DataFrame) -> pl.DataFrame:
    """Parse a stubbed flat read, as a published file would be parsed."""
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: df)
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    file = File(url="a-file", content=BytesIO(b"not a real bufr message"), status=200)
    return api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data(file, parameters)  # noqa: SLF001


def _readings(df: pl.DataFrame, station_id: str) -> dict[str, float]:
    return dict(
        df.filter(pl.col("station_id").eq(station_id)).drop_nulls("value").select("parameter", "value").iter_rows(),
    )


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_keeps_sensors_that_report_different_quantities(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Two road sensors reporting different quantities are one installation, and both are kept.

    This is the whole of the DD group: for 24 of its 25 stations the first sensor carries the
    surface temperature and the second the surface condition, and neither carries the other. There
    is nothing contested to choose between, so answering the row from one sensor alone would throw
    away the condition of every station in the group for no gain.
    """
    with caplog.at_level(logging.DEBUG):
        df = _parse(
            monkeypatch,
            _flat(
                {
                    "#1#shortStationName": "O452",
                    "#1#airTemperature": 286.65,
                    "#1#roadSurfaceTemperature": 287.85,
                    "#1#roadSurfaceCondition": None,
                    "#2#roadSurfaceTemperature": None,
                    "#2#roadSurfaceCondition": 0.0,
                },
            ),
        )
    assert _readings(df, "O452") == {
        "airTemperature": 286.65,
        "roadSurfaceTemperature": 287.85,
        "roadSurfaceCondition": 0.0,
    }
    # and nothing was dropped, so nothing is said about dropping any
    assert "GH-1908" not in caplog.text


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_answers_a_contested_reading_from_one_sensor(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Where two road sensors report one quantity, everything contested comes from one of them.

    Two sensors on one road measure it at two points and mostly agree -- of the 75 stations whose
    sensors both reported a surface temperature the median disagreement was 0.3 K -- but two of
    those 75 were 22 K and 18 K apart, one sensor of each being broken. Taken per descriptor
    instead, the row holds the first sensor's temperature beside the second's condition: a state of
    a road that neither sensor measured.
    """
    with caplog.at_level(logging.DEBUG):
        df = _parse(
            monkeypatch,
            _flat(
                {
                    "#1#shortStationName": "E723",
                    "#1#airTemperature": 286.34,
                    "#1#roadSurfaceTemperature": 286.02,
                    "#1#roadSurfaceCondition": 2.0,
                    "#2#roadSurfaceTemperature": 287.31,
                    "#2#roadSurfaceCondition": 0.0,
                },
            ),
        )
    readings = _readings(df, "E723")
    # both from the first sensor, which is the one the tie goes to -- and not 286.02 beside 0.0
    assert readings["roadSurfaceTemperature"] == 286.02
    assert readings["roadSurfaceCondition"] == 2.0
    # the air temperature is outside the sensor replication, so it is the station's either way
    assert readings["airTemperature"] == 286.34
    # and what went is named, at debug: it is per file and routine, where the CLI logs at info
    dropped = [record for record in caplog.records if "GH-1908" in record.message]
    assert [record.levelname for record in dropped] == ["DEBUG"]
    assert "E723" in dropped[0].message
    assert "a-file" in dropped[0].message


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_answers_from_the_sensor_carrying_most_of_the_contest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sensor chosen is the one reporting most of what is contested, not the first to report.

    Counted over what this row has twice rather than over everything a sensor carries, so that a
    sensor holding nothing contested cannot win a contest on the strength of what nobody disputes.
    """
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "K677",
                # the first sensor contests only the temperature, and carries a film besides
                "#1#roadSurfaceTemperature": 273.15,
                "#1#roadSurfaceCondition": None,
                "#1#waterFilmThickness": 0.0,
                # the second contests both of the quantities it reports
                "#2#roadSurfaceTemperature": 291.55,
                "#2#roadSurfaceCondition": 1.0,
                "#3#roadSurfaceCondition": 2.0,
            },
        ),
    )
    readings = _readings(df, "K677")
    assert readings["roadSurfaceTemperature"] == 291.55
    assert readings["roadSurfaceCondition"] == 1.0
    # uncontested, so it is kept as it came rather than dropped for sitting on another sensor
    assert readings["waterFilmThickness"] == 0.0


def _quality(df: pl.DataFrame, station_id: str) -> dict[str, float | None]:
    return dict(
        df.filter(pl.col("station_id").eq(station_id)).select("parameter", "quality").iter_rows(),
    )


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_carries_the_stations_verdict_on_its_own_sensors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The quality flag the station publishes reaches the reading it speaks for.

    Every road subset ends with `0 33 005`, a 30-bit flag table naming which of the station's
    quantities are suspect, and the frame has a `quality` column that used to be null on every road
    reading while upstream was saying which not to trust. Bit 7, "ground temperature data suspect",
    is the one this was verified against: the four stations carrying it in a network-wide file are
    exactly the four whose road surface temperature is impossible.
    """
    ground_suspect = 1 << (30 - 7)
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "P034",
                "#1#qualityInformationAwsData": ground_suspect,
                "#1#roadSurfaceTemperature": 338.75,
                "#1#airTemperature": 285.25,
                "#1#windSpeed": 2.0,
            },
        ),
    )
    quality = _quality(df, "P034")
    # the reading the flag names
    assert quality["roadSurfaceTemperature"] == 1.0
    # and the ones it does not, which the same station checked and did not complain about
    assert quality["airTemperature"] == 0.0
    assert quality["windSpeed"] == 0.0
    # the value itself is untouched: this says the road surface is suspect, it does not drop it
    values = _readings(df, "P034")
    assert values["roadSurfaceTemperature"] == 338.75


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_unchecked_is_unknown_rather_than_good(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station that ran no checks says so, and that is not a clean bill of health.

    Bit 1 is "no automated meteorological data checks performed", and it is the ordinary answer
    rather than an exception -- 817 of 1199 subsets measured. Reported as zero it would read as
    "checked, nothing wrong", which is the opposite of what the station said. It is also where the
    unflagged nonsense sits: 17 of the 21 stations more than 10 K from their own air temperature
    carry this and nothing else.
    """
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "L702",
                "#1#qualityInformationAwsData": 1 << (30 - 1),
                # 79.8 C at 23:00 local, and the station has nothing to say about it
                "#1#roadSurfaceTemperature": 352.95,
                "#1#airTemperature": 284.55,
            },
        ),
    )
    quality = _quality(df, "L702")
    assert quality["roadSurfaceTemperature"] is None
    assert quality["airTemperature"] is None
    assert _readings(df, "L702")["roadSurfaceTemperature"] == 352.95


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.parametrize(
    ("subset", "case"),
    [
        ({"#1#shortStationName": "A006", "#1#airTemperature": 285.15}, "the file carries no flag at all"),
        (
            {"#1#shortStationName": "A006", "#1#airTemperature": 285.15, "#1#qualityInformationAwsData": None},
            "the station left its flag empty",
        ),
    ],
)
def test_dwd_road_weather_no_flag_is_no_verdict(
    monkeypatch: pytest.MonkeyPatch,
    subset: dict[str, object],
    case: str,
) -> None:
    """Nothing said about a reading's quality is a null, not a zero."""
    df = _parse(monkeypatch, _flat(subset))
    assert _quality(df, "A006")["airTemperature"] is None, case


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_a_flag_of_nothing_is_not_a_clean_bill(monkeypatch: pytest.MonkeyPatch) -> None:
    """A flag carrying only its own missing marker says nothing, and nothing is not "nothing wrong".

    The top bit of a 30-bit flag table is how BUFR says it has nothing to report -- `0 20 021`
    spells it out as "ALL 30 MISSING VALUE", and this table's entries simply stop at 23, leaving
    the bit either that marker or undefined. Read as a verdict it says the station checked and was
    satisfied, which is the one thing it certainly does not mean, and it is the same false clean
    bill the bit-1 handling exists to prevent.
    """
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "A006",
                "#1#qualityInformationAwsData": 1,
                "#1#roadSurfaceTemperature": 285.15,
                "#1#airTemperature": 285.15,
            },
        ),
    )
    quality = _quality(df, "A006")
    assert quality["roadSurfaceTemperature"] is None
    assert quality["airTemperature"] is None


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_road_surface_condition_has_no_flag_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """A descriptor the flag table does not name gets a null rather than its nearest neighbour.

    The table is the WMO's generic one for an automatic weather station and has no entry for the
    state of a road. Its nearest neighbour, bit 19 "state of ground", is about bare earth, and
    reading one as the other would assert a correspondence DWD has not made -- on a bit that is set
    nowhere in the data.
    """
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "A006",
                # a station that checked everything and found nothing wrong
                "#1#qualityInformationAwsData": 0,
                "#1#roadSurfaceCondition": 2.0,
                "#1#roadSurfaceTemperature": 285.15,
            },
        ),
    )
    quality = _quality(df, "A006")
    assert quality["roadSurfaceCondition"] is None
    # where the reading beside it, which the table does name, is answered
    assert quality["roadSurfaceTemperature"] == 0.0


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_precipitation_type_is_flags_not_a_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """The road's precipitation type keeps its own name, because it keeps its own encoding.

    `precipitationType` is BUFR `0 20 021`, a 30-bit flag table with a bit per type, where
    `precipitation_form` everywhere else in this library is a single code from a table of its own --
    DWD observation's `wrtr`, whose 6 means liquid precipitation. Rain arrives here as 33554432,
    bit 5 of a 30-bit field. Reported under one name the two would be one quantity with two
    incomparable encodings, and a caller comparing the road network to the observation network
    would be comparing 33554432 against 6.
    """
    df = _parse(
        monkeypatch,
        _flat({"#1#shortStationName": "M521", "#1#precipitationType": float(1 << (30 - 5))}),
    )
    readings = _readings(df, "M521")
    assert readings["precipitationType"] == 33554432.0
    # under the name that says what the number is, and not under the one that promises a code
    parameters = {parameter.name for parameter in DwdRoadRequest.metadata["15_minutes"]["data"]}
    assert "precipitation_type_flags" in parameters
    assert "precipitation_form" not in parameters


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_one_subset_without_a_minute_does_not_take_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subset that names no minute costs its own reading and no one else's.

    The read is required of nothing but its own structure now, so a subset missing a time key
    arrives like any other -- and one null in the minute makes the whole of pandas' column a float,
    where 2026 becomes "2026.0" and the timestamp of every station in the file fails to parse with
    it. The keys go through `Int64` on the way to a string for that reason.
    """
    keys = {"#1#year": 2026, "#1#month": 9, "#1#day": 13, "#1#hour": 12, "#1#minute": 0}
    df = _parse(
        monkeypatch,
        pd.DataFrame(
            [
                {**keys, "#1#shortStationName": "A006", "#1#airTemperature": 285.15},
                # no minute, and so no reading -- but the file still has one
                {k: v for k, v in keys.items() if k != "#1#minute"} | {"#1#shortStationName": "B999"},
            ],
        ),
    )
    assert df.get_column("station_id").unique().to_list() == ["A006"]
    assert _readings(df, "A006")["airTemperature"] == 285.15


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_reads_a_key_at_whatever_rank_it_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rank 1 is where a key usually is, not where it must be.

    A descriptor absent from the first subset of a file and present in a later one comes back
    numbered from where it appears, so addressing `#1#` is a `KeyError` waiting for the first file
    that does that.
    """
    keys = {"#1#year": 2026, "#1#month": 9, "#1#day": 13, "#1#hour": 12, "#1#minute": 0}
    df = _parse(monkeypatch, pd.DataFrame([{**keys, "#2#shortStationName": "A006", "#1#airTemperature": 285.15}]))
    assert df.get_column("station_id").unique().to_list() == ["A006"]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_keeps_a_reading_the_chosen_sensor_never_took(monkeypatch: pytest.MonkeyPatch) -> None:
    """A quantity the chosen sensor does not report is taken from one that does, not dropped.

    With three sensors the one answering a row's contests need not carry every contested quantity.
    Insisting the reading come from it anyway loses a value that two sensors reported, and there is
    nothing of the chosen sensor's for it to have been paired against in the first place.
    """
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "K677",
                # the first sensor answers the temperature contest and reports no film at all
                "#1#roadSurfaceTemperature": 280.0,
                "#3#roadSurfaceTemperature": 281.0,
                "#1#roadSurfaceCondition": 1.0,
                "#2#roadSurfaceCondition": 2.0,
                "#2#waterFilmThickness": 0.5,
                "#3#waterFilmThickness": 0.7,
            },
        ),
    )
    readings = _readings(df, "K677")
    assert readings["roadSurfaceTemperature"] == 280.0
    assert readings["roadSurfaceCondition"] == 1.0
    # reported by two sensors, neither of them the chosen one, and kept rather than lost
    assert readings["waterFilmThickness"] == 0.5


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_says_nothing_about_a_reading_that_is_not_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station's clean bill of health covers what it reported, not what it did not.

    The flag is one verdict for the station, and a station that checked its sensors and found
    nothing wrong says nothing whatever about the twelve quantities it does not measure. Answering
    0 for those reads as "checked, not suspect" about a reading that does not exist.
    """
    df = _parse(
        monkeypatch,
        _flat({"#1#shortStationName": "A006", "#1#qualityInformationAwsData": 0, "#1#airTemperature": 285.15}),
    )
    quality = _quality(df, "A006")
    assert quality["airTemperature"] == 0.0
    assert quality["windSpeed"] is None


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_reads_an_identity_key_from_whichever_rank_carries_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subsets numbering their station differently are all read, not just the first numbering.

    The keys that say which station and which minute occur once per subset, and a file whose
    messages do not agree on their structure -- which is every road file, and what the read's own
    warning is about -- can carry one subset's station at `#1#` and the next one's at `#2#`. Read
    from the lowest rank alone, every subset numbered otherwise had no station and was dropped for
    having none, without a word anywhere.
    """
    keys = {"#1#year": 2026, "#1#month": 9, "#1#day": 13, "#1#hour": 12, "#1#minute": 0}
    df = _parse(
        monkeypatch,
        pd.DataFrame(
            [
                {**keys, "#1#shortStationName": "A001", "#1#airTemperature": 285.0},
                {**keys, "#2#shortStationName": "B002", "#1#airTemperature": 286.0},
            ],
        ),
    )
    assert sorted(df.get_column("station_id").unique().to_list()) == ["A001", "B002"]
    assert _readings(df, "B002")["airTemperature"] == 286.0


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_prefers_the_sensor_that_reported_more_on_a_tied_contest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where two sensors settle as many contests, the fuller one answers the row.

    Both here report the surface condition and disagree, so the contest alone cannot separate them
    and the tie went to the first -- which left the row holding the first sensor's condition beside
    the second's temperature, the first having taken no temperature at all. The second settles the
    contest just as well and took both readings, so answering from it makes the row wholly one
    sensor's instead of pairing two.
    """
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "S001",
                "#1#roadSurfaceCondition": 1.0,
                "#2#roadSurfaceCondition": 2.0,
                "#1#roadSurfaceTemperature": None,
                "#2#roadSurfaceTemperature": 290.0,
            },
        ),
    )
    readings = _readings(df, "S001")
    assert readings["roadSurfaceCondition"] == 2.0
    assert readings["roadSurfaceTemperature"] == 290.0


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_folds_a_station_minute_reported_twice(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A station and minute arriving twice keeps the reading, not the blank.

    No published file has done this -- 1199 subsets of fifteen groups, and not one station twice --
    but one row per subset would hand a caller both, and the deduplication every provider passes
    through afterwards keeps whichever came first. First being null, the reading went out with the
    duplicate and nothing said so.
    """
    keys = {"#1#year": 2026, "#1#month": 9, "#1#day": 13, "#1#hour": 12, "#1#minute": 0}
    with caplog.at_level(logging.WARNING):
        df = _parse(
            monkeypatch,
            pd.DataFrame(
                [
                    {**keys, "#1#shortStationName": "A001", "#1#airTemperature": None},
                    {**keys, "#1#shortStationName": "A001", "#1#airTemperature": 285.0},
                ],
            ),
        )
    assert _readings(df, "A001")["airTemperature"] == 285.0
    assert "more than once" in caplog.text


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_parses_a_group_once_for_all_its_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """A road file holds a whole group, so it is read for the group and not for each station.

    The collection above this asks for one station at a time, and a road file holds them all -- so
    every file of a group was decoded once per station of that group, with all but one station's
    rows thrown away each time. Three stations of one group over two hours parsed nine files
    twenty-seven times.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    reading = _flat(
        {"#1#shortStationName": "A006", "#1#airTemperature": 12.0},
        {"#1#shortStationName": "B999", "#1#airTemperature": 9.0},
        {"#1#shortStationName": "C111", "#1#airTemperature": 7.0},
    )
    parses = []
    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: parses.append(1) or reading)
    monkeypatch.setattr(
        api, "list_remote_files_fsspec", lambda *_args, **_kwargs: ["swis2-ISXD70_DWDD_131200-2609131200-DD---bin"]
    )
    monkeypatch.setattr(
        api,
        "download_files",
        lambda **_kwargs: [
            File(url="swis2-ISXD70_DWDD_131200-2609131200-DD---bin", content=BytesIO(b"x" * 500), status=200)
        ],
    )
    values = _stub_stations(("A006", "B999", "C111")).values
    dataset = DwdRoadRequest.metadata["15_minutes"]["data"]
    answers = [values._collect_station_parameter_or_dataset(sid, dataset) for sid in ("A006", "B999", "C111")]  # noqa: SLF001

    assert len(parses) == 1, "the group's one file should be decoded once, not once per station"
    # and each station still gets its own reading out of it
    assert [df.get_column("station_id").unique().to_list() for df in answers] == [["A006"], ["B999"], ["C111"]]
    assert [df.drop_nulls("value").get_column("value").to_list() for df in answers] == [[12.0], [9.0], [7.0]]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_keeps_one_group_rather_than_every_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """Moving to another group replaces what is kept, rather than adding to it.

    Stations arrive in group order -- 1653 of them across 19 groups change group 21 times -- so
    holding the last group is worth almost exactly what holding every one would be, and it bounds
    what this keeps to a single group's readings. A month of one group is some thirteen million
    rows, which is the whole of whether a wide request fits in memory.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    values = _stub_stations().values
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    seen = []

    def parse_group(self: object, group: DwdRoadStationGroup, params: list[object]) -> pl.DataFrame:  # noqa: ARG001
        seen.append(group.value)
        return pl.DataFrame(schema=_PARSED_SCHEMA_FOR_TEST)

    monkeypatch.setattr(api.DwdRoadValues, "_DwdRoadValues__collect_data_by_station_group", parse_group)
    for group in (DwdRoadStationGroup.DD, DwdRoadStationGroup.DD, DwdRoadStationGroup.HV, DwdRoadStationGroup.DD):
        values._collect_data_by_station_group(group, parameters)  # noqa: SLF001

    # the repeat is served from what is kept; moving away and back is a fresh read, one group
    # being all that is held
    assert seen == ["DD", "HV", "DD"]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_water_film_has_no_flag_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """The water film gets no verdict from a bit about the moisture in soil.

    `waterFilmThickness` is a road descriptor of DWD's own, and the flag table's nearest offer is
    "water content data suspect", which in a generic automatic weather station is the ground's. The
    road surface temperature is mapped to "ground temperature data suspect" because the data
    confirms that reading, and nothing confirms this one: the stations setting the bit reported the
    same film as everyone else. A wrong `0` would tell a caller filtering on quality that a suspect
    reading had been checked and found sound.
    """
    df = _parse(
        monkeypatch,
        _flat(
            {
                "#1#shortStationName": "S001",
                "#1#qualityInformationAwsData": 1 << (30 - 21),
                "#1#waterFilmThickness": 0.0,
                "#1#airTemperature": 285.15,
            },
        ),
    )
    quality = _quality(df, "S001")
    assert quality["waterFilmThickness"] is None
    # where the reading the table does name is still answered, the flag having been read
    assert quality["airTemperature"] == 0.0


def _series(station_id: str, parameter: str, values: list[float | None]) -> pl.DataFrame:
    """Build a station's readings at the quarter-hours, as the per-file parses concatenate to."""
    return pl.DataFrame(
        {
            "station_id": [station_id] * len(values),
            "date": [
                dt.datetime(2026, 9, 13, tzinfo=ZoneInfo("UTC")) + dt.timedelta(minutes=15 * i)
                for i in range(len(values))
            ],
            "parameter": [parameter] * len(values),
            "value": values,
            "quality": [None] * len(values),
        },
        schema={
            "station_id": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "parameter": pl.String,
            "value": pl.Float64,
            "quality": pl.Float64,
        },
    )


def test_dwd_road_weather_marks_a_sensor_that_has_stopped(caplog: pytest.LogCaptureFixture) -> None:
    """A temperature that has not moved for six hours is a sensor, not a road.

    DWD's own flag names 4 of the 21 stations in a network-wide file that sit more than 10 K from
    their own air temperature; the other 17 say "no automated checks performed". This is the one
    fault the data alone can settle without knowing the season -- and it is what the exact `-75.00`,
    `-30.00` and `-25.00` readings turn out to be: not values to recognise, but sensors that have
    stopped. Matching them by value would have been worse than useless, -25 and -30 both being
    reachable in a German winter.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    stuck = _series("H659", "roadSurfaceTemperature", [198.15] * 30)
    with caplog.at_level(logging.DEBUG):
        df = api._flag_stuck_sensors(stuck, "a-group")  # noqa: SLF001

    assert df.get_column("quality").to_list() == [1.0] * 30
    # at debug, not info: the road values are collected a station at a time and each of those
    # parses the whole group again, so at info this group-wide line is printed once per station
    assert [record.levelname for record in caplog.records if "GH-1917" in record.message] == ["DEBUG"]
    # marked, not removed: the reading is still exactly what DWD published
    assert df.get_column("value").to_list() == [198.15] * 30
    assert "H659/roadSurfaceTemperature" in caplog.text
    assert "kept as published" in caplog.text


@pytest.mark.parametrize(
    ("values", "expected", "case"),
    [
        ([280.0] * 23, False, "a run one short of the threshold is left alone"),
        ([280.0] * 24, True, "a run of exactly the threshold is marked"),
        # a working sensor's longest run of one value over a day was 14 readings for the air
        # temperature, 17 for the dew point and 9 for the road surface, across ~700 stations each
        ([280.0] * 17 + [280.1] * 17, False, "two long-ish runs of different values are a working sensor"),
        # a row saying null is the same dropout as a row that never arrived, and the gap rule
        # decides both: one missed reading in the middle does not make two runs out of one
        ([280.0] * 12 + [None] + [280.0] * 12, True, "a null is a missed reading, not a new run"),
    ],
)
def test_dwd_road_weather_stuck_threshold(
    values: list[float | None],
    expected: bool,  # noqa: FBT001
    case: str,
) -> None:
    """The run that counts as stopped sits between what a working sensor does and what a dead one does."""
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    df = api._flag_stuck_sensors(_series("A006", "roadSurfaceTemperature", values), "a-group")  # noqa: SLF001
    assert (df.get_column("quality").eq(1.0).any()) is expected, case


def test_dwd_road_weather_a_run_is_not_read_across_an_outage() -> None:
    """Readings either side of a hole are not one run, however alike they are.

    A gap here is almost always an absent row -- a station missing from a subset, a file too small
    to read, a file never published -- rather than a row saying null, which a comparison of values
    would never see. Two three-hour plateaus either side of three days of nothing are not a
    six-hour one, and three hours is well inside what a working sensor does.

    Measured as how full the run is rather than as a gap between readings, because no gap separates
    the two: 99.5% of this network's intervals are the quarter hour it publishes on, and the tail
    runs past six hours.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    plateau = _series("A006", "roadSurfaceTemperature", [285.0] * 12)
    later = plateau.with_columns(pl.col("date") + pl.duration(days=3))
    across = api._flag_stuck_sensors(pl.concat([plateau, later]), "a-group")  # noqa: SLF001
    assert not across.get_column("quality").eq(1.0).any()

    # and the hole ends the run rather than the marking: a sensor that has stopped either side of
    # one is still stopped, where scoring the whole span at once let a single gap clear the lot
    long_enough = _series("A006", "roadSurfaceTemperature", [285.0] * 34)
    beyond = long_enough.with_columns(pl.col("date") + pl.duration(hours=12))
    both = api._flag_stuck_sensors(pl.concat([long_enough, beyond]), "a-group")  # noqa: SLF001
    assert both.get_column("quality").eq(1.0).all()


def test_dwd_road_weather_a_missed_file_does_not_break_a_run() -> None:
    """A station that misses a file here and there is still a station that has stopped.

    Of 67134 intervals measured over five groups, 219 are half an hour and 36 three quarters --
    the ordinary missed file. FN/P367 holds one air temperature for 88 readings with seven such
    gaps among them, and is certainly broken.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    readings = _series("A006", "roadSurfaceTemperature", [285.0] * 30)
    # every seventh reading dropped, which is a good deal worse than the network manages
    sparse = readings.filter(pl.int_range(pl.len()).mod(7).ne(0))
    assert api._flag_stuck_sensors(sparse, "a-group").get_column("quality").eq(1.0).all()  # noqa: SLF001


@pytest.mark.parametrize("every", [5, 15, 20, 30])
def test_dwd_road_weather_stuck_run_counts_readings_whatever_the_cadence(every: int) -> None:
    """The run is counted in readings, so a station reporting on another interval is not exempt.

    Measured against a fixed quarter hour instead, a station publishing every twenty minutes could
    never be flagged however long it had been stopped, and one publishing every five tripped at two
    hours where the count is documented as six.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    readings = _series("A006", "roadSurfaceTemperature", [285.0] * 24)
    spaced = readings.with_columns(
        pl.col("date").first() + pl.duration(minutes=every) * pl.int_range(pl.len()),
    )
    assert api._flag_stuck_sensors(spaced, "a-group").get_column("quality").eq(1.0).all()  # noqa: SLF001


def test_dwd_road_weather_a_minute_arriving_twice_is_one_minute() -> None:
    """A station-minute in two files of one request neither multiplies the frame nor blinds the check.

    Both followed from asking the question of the rows rather than of the readings. The air joined
    on for the melting test multiplied every row of a doubled minute, and the frame that comes back
    is what the group cache holds -- a month of one group being some thirteen million rows. Worse,
    a duplicated minute puts a zero among the intervals and so a zero in their median, which ends
    a run at every reading: a sensor stuck for a whole day came back with nothing marked at all.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    stuck = _series("A006", "roadSurfaceTemperature", [285.0] * 30)
    air = _series("B999", "airTemperature", [280.0] * 30)
    doubled_air = pl.concat([stuck, _series("A006", "airTemperature", [280.0] * 30), air, air])
    assert api._flag_stuck_sensors(doubled_air, "a-group").height == doubled_air.height  # noqa: SLF001

    doubled_readings = pl.concat([stuck, stuck])
    marked = api._flag_stuck_sensors(doubled_readings, "a-group")  # noqa: SLF001
    assert marked.get_column("quality").eq(1.0).all()


def test_dwd_road_weather_a_verdict_stays_with_the_reading_it_was_reached_from() -> None:
    """A station-minute held twice is judged from one copy, and only that copy is answered.

    The run is read from the first copy of a minute. Joined back on the minute alone, the verdict
    landed on the second as well -- including one holding a value that had moved and belonged to no
    run at all, which came back marked as though the sensor had never budged.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    stuck = _series("A006", "roadSurfaceTemperature", [285.0] * 30)
    moved = stuck.tail(1).with_columns(value=pl.lit(286.4))
    marked = api._flag_stuck_sensors(pl.concat([stuck, moved]), "a-group")  # noqa: SLF001

    assert marked.filter(pl.col("value").eq(286.4)).get_column("quality").to_list() == [None]
    assert marked.filter(pl.col("value").eq(285.0)).get_column("quality").eq(1.0).all()


def test_dwd_road_weather_a_frost_is_not_a_thaw() -> None:
    """The air is bounded on both sides, brine being no more able to pin a road than ice is.

    Ice cannot hold a road at 0.00 C while the air stands at 26, and brine cannot hold one at -4
    while it stands at -20. Bounded above only, the second was exempted and never marked -- and the
    docs described the bound as "within 10 degrees of freezing", which reads as both sides and is
    what actually separates a thaw from a frost.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    melting_point = 273.15
    df = pl.concat(
        [
            _series("A006", "roadSurfaceTemperature", [melting_point - 4] * 30),
            _series("A006", "airTemperature", [melting_point - 20] * 30),
        ],
    )
    marked = api._flag_stuck_sensors(df, "a-group").filter(  # noqa: SLF001
        pl.col("parameter").eq("roadSurfaceTemperature"),
    )
    assert marked.get_column("quality").eq(1.0).all()


def test_dwd_road_weather_only_the_quantities_that_can_be_marked_are_examined() -> None:
    """The eleven parameters this cannot mark are not carried through the windows for nothing.

    The dedupe, the air join and four window passes over them are work whose result is discarded.
    On a month of one group -- the size the group cache is bounded to hold -- that was 4.96 GB of
    peak memory against 2.06, inside the one function the code around it was restructured to keep
    out of memory.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    stuck = _series("A006", "roadSurfaceTemperature", [285.0] * 30)
    others = pl.concat(
        [_series("A006", name, [0.0] * 30) for name in ("precipitationType", "waterFilmThickness", "windSpeed")],
    )
    marked = api._flag_stuck_sensors(pl.concat([stuck, others]), "a-group")  # noqa: SLF001

    # the ones that cannot be marked come back exactly as they went in, constant though they are
    assert marked.filter(pl.col("parameter").ne("roadSurfaceTemperature")).get_column("quality").is_null().all()
    assert marked.filter(pl.col("parameter").eq("roadSurfaceTemperature")).get_column("quality").eq(1.0).all()


def test_dwd_road_weather_a_null_reading_is_a_missed_one() -> None:
    """A row saying null and a row that never arrived are the same dropout, and answer alike.

    A station missing from a file leaves no row; one present and not reporting leaves a null. Read
    as a value, the null ended a run that the absent row was allowed to span, so a sensor dropping
    one reading in twenty was never flagged however long it had stopped.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    with_nulls = _series("A006", "roadSurfaceTemperature", [285.0 if i % 20 else None for i in range(96)])
    absent = with_nulls.drop_nulls("value")
    marked_nulls = api._flag_stuck_sensors(with_nulls, "a-group")  # noqa: SLF001
    marked_absent = api._flag_stuck_sensors(absent, "a-group")  # noqa: SLF001
    assert marked_nulls.get_column("quality").eq(1.0).sum() == marked_absent.get_column("quality").eq(1.0).sum()
    assert marked_absent.get_column("quality").eq(1.0).all()


def test_dwd_road_weather_stuck_marking_leaves_the_frame_as_it_found_it() -> None:
    """Marking changes a verdict and nothing else about the frame."""
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    df = _series("A006", "roadSurfaceTemperature", [285.0] * 30)
    marked = api._flag_stuck_sensors(df, "a-group")  # noqa: SLF001
    assert marked.get_column("value").to_list() == df.get_column("value").to_list()
    assert marked.select("station_id", "date", "parameter").equals(df.select("station_id", "date", "parameter"))
    # and running it again says the same thing, the column it writes being one it also reads
    assert api._flag_stuck_sensors(marked, "a-group").get_column("quality").to_list() == (  # noqa: SLF001
        marked.get_column("quality").to_list()
    )


def test_dwd_road_weather_melting_is_asked_of_the_reading_not_the_window() -> None:
    """Whether ice could be melting is a question about that minute, not about the request.

    Asked of the whole window -- or of a whole run -- one cold hour at the end of a fortnight
    excuses every plateau in it, and the same day then answers differently depending on how much of
    the year the caller asked for.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    df = pl.concat(
        [
            _series("A006", "roadSurfaceTemperature", [273.15] * 96),
            # 26 C for most of the day, then a cold hour and a half at the end
            _series("A006", "airTemperature", [299.15] * 90 + [277.05] * 6),
        ],
    )
    surface = api._flag_stuck_sensors(df, "a-group").filter(  # noqa: SLF001
        pl.col("parameter").eq("roadSurfaceTemperature"),
    )
    # the readings taken while nothing could have been melting, and not the six that could
    assert surface.get_column("quality").eq(1.0).sum() == 90


@pytest.mark.parametrize(
    ("surface", "air", "expected", "case"),
    [
        (273.15, 274.15, False, "an untreated road at 0.00 in a thaw"),
        (270.15, 274.15, False, "a salted road at -3.0, brine holding it below zero in the same thaw"),
        (265.15, 272.15, False, "heavily salted at -8.0, about where rock salt stops working"),
        (243.15, 271.15, True, "stopped at -30 in a frost, which no brine reaches"),
        (273.15, 299.15, True, "stopped at 0.00 while its own air is at 26 C, which is FN/P717"),
        (278.15, 279.15, True, "a road above freezing holds still for no physical reason"),
    ],
)
def test_dwd_road_weather_brine_holds_a_salted_road_below_zero(
    surface: float,
    air: float,
    expected: bool,  # noqa: FBT001
    case: str,
) -> None:
    """A salted road in a thaw is pinned below zero as an untreated one is pinned at zero.

    German roads are salted, and brine depresses the freezing point -- so the plateau the exemption
    exists to protect is not only the one at 0.00 C. Rock salt works to about -8 C in practice. The
    range is bounded below all the same, which is what keeps a sensor stopped at -30 C in a frost
    from being excused along with it.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    df = pl.concat(
        [
            _series("A006", "roadSurfaceTemperature", [surface] * 30),
            _series("A006", "airTemperature", [air] * 30),
        ],
    )
    marked = api._flag_stuck_sensors(df, "a-group").filter(  # noqa: SLF001
        pl.col("parameter").eq("roadSurfaceTemperature"),
    )
    assert marked.get_column("quality").eq(1.0).any() is expected, case


@pytest.mark.parametrize(
    ("every", "readings", "expected", "case"),
    [
        (5, 24, False, "24 readings five minutes apart is under two hours, not the six measured"),
        (5, 70, True, "the same station once it has covered the hours"),
        (15, 23, False, "one reading short at the cadence the count was measured on"),
        (15, 24, True, "the case the count was measured on"),
        (30, 24, True, "a station reporting less often still trips on the count"),
    ],
)
def test_dwd_road_weather_stuck_needs_the_hours_as_well_as_the_readings(
    every: int,
    readings: int,
    expected: bool,  # noqa: FBT001
    case: str,
) -> None:
    """The count was measured at a quarter hour, so it carries a floor on the time it covers.

    A station reporting more often would otherwise trip on less evidence than the measurement was
    taken from -- a working sensor held one value for 14 readings there, three and a half hours.
    A floor and not a divisor: measuring against a fixed cadence instead once made a station
    reporting every twenty minutes impossible to flag at all.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    series = _series("A006", "roadSurfaceTemperature", [285.0] * readings)
    spaced = series.with_columns(pl.col("date").first() + pl.duration(minutes=every) * pl.int_range(pl.len()))
    marked = api._flag_stuck_sensors(spaced, "a-group")  # noqa: SLF001
    assert marked.get_column("quality").eq(1.0).any() is expected, case


@pytest.mark.parametrize(
    ("air", "expected", "case"),
    [
        (271.0, False, "air below freezing, so the ice that holds the road there can exist"),
        (276.0, False, "air a few degrees above, where melting is still possible"),
        (284.75, True, "air at 11.6 C, which is FN/P717 -- nothing is melting on that road"),
    ],
)
def test_dwd_road_weather_a_melting_road_is_not_a_stopped_sensor(
    air: float,
    expected: bool,  # noqa: FBT001
    case: str,
) -> None:
    """Melting ice holds a road at its melting point for hours, and that is a reading.

    It is the condition this network exists to report, and it could not appear in the September day
    the threshold was measured over. It cannot be told from a sensor stopped at zero by the reading
    -- FN/P717 sits at 0.00 C all day and is broken -- so it is told by the air: ice does not melt
    on a road whose own station reports 26 C, which is what P717's does.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    df = pl.concat(
        [
            _series("A006", "roadSurfaceTemperature", [273.15] * 30),
            _series("A006", "airTemperature", [air + 0.01 * i for i in range(30)]),
        ],
    )
    marked = api._flag_stuck_sensors(df, "a-group")  # noqa: SLF001
    surface = marked.filter(pl.col("parameter").eq("roadSurfaceTemperature"))
    assert surface.get_column("quality").eq(1.0).any() is expected, case


@pytest.mark.parametrize(
    "parameter",
    ["roadSurfaceCondition", "waterFilmThickness", "precipitationType", "relativeHumidity", "windSpeed"],
)
def test_dwd_road_weather_does_not_call_a_quiet_day_a_fault(parameter: str) -> None:
    """Standing still is only a fault for the quantities it is a fault for.

    The road surface condition and the water film sit at 0 for the whole of a dry day, as does the
    precipitation type; the humidity saturates in fog and the wind falls calm. Measured over a day
    of five groups, a threshold applied to these would have called 547 of 571 stations' surface
    condition a fault, and 61 of 581 humidities -- a quiet day reported as a broken network.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    df = api._flag_stuck_sensors(_series("A006", parameter, [0.0] * 96), "a-group")  # noqa: SLF001
    assert df.get_column("quality").to_list() == [None] * 96


def test_dwd_road_weather_stuck_check_keeps_one_station_out_of_another(caplog: pytest.LogCaptureFixture) -> None:
    """One station standing still says nothing about the next one's readings."""
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    moving = [280.0 + 0.1 * i for i in range(30)]
    df = pl.concat(
        [
            _series("H659", "roadSurfaceTemperature", [198.15] * 30),
            _series("A006", "roadSurfaceTemperature", moving),
        ],
    )
    with caplog.at_level(logging.INFO):
        out = api._flag_stuck_sensors(df, "a-group")  # noqa: SLF001

    assert out.filter(pl.col("station_id").eq("H659")).get_column("quality").to_list() == [1.0] * 30
    assert out.filter(pl.col("station_id").eq("A006")).get_column("quality").to_list() == [None] * 30
    # and the frame comes back in the order it arrived, the check having sorted to find the runs
    assert out.get_column("station_id").to_list() == ["H659"] * 30 + ["A006"] * 30
    assert out.get_column("value").to_list() == [198.15] * 30 + moving


def test_dwd_road_weather_stuck_check_counts_minutes_not_rows() -> None:
    """A reading that arrives twice is one minute, not two.

    The check runs over every file of a request concatenated, before the deduplication each
    provider passes through afterwards. A station-minute arriving in two of those files -- a group
    publishing under two families, a file republished -- counted twice would halve the window, and
    a working sensor's measured 14-reading plateau would double into a fault.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    # thirteen minutes at one value, which is three and a quarter hours and no fault
    plateau = _series("A006", "airTemperature", [285.0] * 13)
    assert not api._flag_stuck_sensors(plateau, "a-group").get_column("quality").eq(1.0).any()  # noqa: SLF001
    doubled = pl.concat([plateau, plateau])
    assert doubled.get_column("date").n_unique() == 13
    assert not api._flag_stuck_sensors(doubled, "a-group").get_column("quality").eq(1.0).any()  # noqa: SLF001


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_two_sensors_that_agree_are_not_a_contest(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Two sensors reporting the same number decide nothing, and nothing is dropped.

    Of the 36 readings one populated group's file reports twice, 25 are identical to the one kept.
    Counted as contests they inflate what the log says went, and credit a sensor in the choice for
    settling a question nobody asked.
    """
    with caplog.at_level(logging.DEBUG):
        df = _parse(
            monkeypatch,
            _flat(
                {
                    "#1#shortStationName": "E719",
                    "#1#roadSurfaceTemperature": 287.24,
                    "#2#roadSurfaceTemperature": 287.24,
                    "#1#roadSurfaceCondition": 0.0,
                    "#2#roadSurfaceCondition": 0.0,
                },
            ),
        )
    assert _readings(df, "E719")["roadSurfaceTemperature"] == 287.24
    assert not [record for record in caplog.records if "GH-1908" in record.message], caplog.text
    # and where they do differ it is still reported
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        _parse(
            monkeypatch,
            _flat(
                {
                    "#1#shortStationName": "E723",
                    "#1#roadSurfaceTemperature": 286.02,
                    "#2#roadSurfaceTemperature": 287.31,
                },
            ),
        )
    assert [record for record in caplog.records if "GH-1908" in record.message], caplog.text


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_parameter_no_subset_carries(monkeypatch: pytest.MonkeyPatch) -> None:
    """A descriptor no subset carries is a null column, not a missing one.

    A descriptor nothing in the file reports is not a column of the read at all, and the select
    that follows asks for every parameter of the dataset by name.
    """
    df = _parse(monkeypatch, _flat({"#1#shortStationName": "A006", "#1#airTemperature": 12.0}))
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    assert df.get_column("parameter").n_unique() == len(parameters)
    assert df.drop_nulls("value").get_column("parameter").to_list() == ["airTemperature"]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.parametrize(
    ("files_upstream_has", "case"),
    [
        ([], "the group published no file"),
        (["swis2-ISXD70_DWDD_142045-2609142045-DD---bin"], "every file it published held nothing"),
    ],
)
def test_dwd_road_weather_empty_is_one_shape(
    monkeypatch: pytest.MonkeyPatch,
    files_upstream_has: list[str],
    case: str,
) -> None:
    """Nothing to answer with comes back in the shape something to answer with comes back in.

    There were three shapes for this: no columns where the group published no file, five where the
    files it published held nothing, and the seven columns a reading has. All three were handed to
    a caller that reads the first as "this station had nothing" and would meet either of the others
    with a width it did not expect or a column that is not there.
    """
    import pandas as pd  # noqa: PLC0415

    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    # big enough to clear the size filter, and holding nothing a reader can use
    file = File(url=files_upstream_has[0] if files_upstream_has else "", content=BytesIO(b"x" * 500), status=200)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: files_upstream_has)
    monkeypatch.setattr(api, "download_files", lambda **_kwargs: [file] if files_upstream_has else [])
    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: pd.DataFrame())

    df = _stub_stations().values._collect_station_parameter_or_dataset(  # noqa: SLF001
        station_id="A006",
        parameter_or_dataset=DwdRoadRequest.metadata["15_minutes"]["data"],
    )
    assert df.is_empty(), case
    assert df.columns == ["resolution", "dataset", "parameter", "station_id", "date", "value", "quality"], case


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_dwd_road_weather_keeps_the_station_that_was_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file holding the station's reading comes back holding it.

    This is the regression the remote test was straining to catch -- a parse that returns nothing
    for everyone, from a bad filter or a read that stopped returning what it used to -- and it
    belongs here, where the data is known. Asked of the network it cannot be told from an
    upstream outage without guessing, which is how that guard came to be rewritten four times.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    reading = _flat(
        {"#1#shortStationName": "A006", "#1#airTemperature": 12.0},
        {"#1#shortStationName": "B999", "#1#airTemperature": 9.0},
    )
    monkeypatch.setattr("pdbufr.read_bufr", lambda *_args, **_kwargs: reading)
    monkeypatch.setattr(
        api, "list_remote_files_fsspec", lambda *_args, **_kwargs: ["swis2-ISXD70_DWDD_131200-2609131200-DD---bin"]
    )
    monkeypatch.setattr(
        api,
        "download_files",
        lambda **_kwargs: [
            File(url="swis2-ISXD70_DWDD_131200-2609131200-DD---bin", content=BytesIO(b"x" * 500), status=200)
        ],
    )
    df = _stub_stations().values._collect_station_parameter_or_dataset(  # noqa: SLF001
        station_id="A006",
        parameter_or_dataset=DwdRoadRequest.metadata["15_minutes"]["data"],
    )
    readings = df.drop_nulls("value").select("station_id", "parameter", "value").rows()
    # the station asked for, and only it -- the other station's reading is in the same file
    assert readings == [("A006", "airTemperature", 12.0)]


@pytest.mark.skipif(IS_CI and IS_WINDOWS, reason="permission with storage in CI on Windows")
@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.remote
def test_dwd_road_weather_a_real_file_decodes() -> None:
    """A published file with bytes in it decodes to readings.

    The tests around this one stub `read_bufr`, so they cover the filtering and folding and cannot
    see pdbufr or eccodes changing under them -- a flat read that came to name its keys differently,
    or a descriptor renamed, would empty every road request upstream-wide with every stubbed test
    still green.

    This asks the one question about live data that does not need guessing at what upstream ought
    to have sent: here is a file it did send, with content in it. Does it decode? A file with bytes
    that yields no rows fails.

    A listing that comes back empty is not an answer: DD is a populated group that reports every
    quarter hour, so nothing listed means the request did not arrive, and the canary has no file to
    ask about. That skips. A listing that arrives and holds no file is a different thing -- the
    names moved -- and fails here rather than going quiet, because the skip is the one way this
    test can stop testing anything while the suite stays green, and the remote test above it now
    skips on an empty window too.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    settings = Settings()
    listed = list_remote_files_fsspec(
        "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/DD/",
        settings=settings,
    )
    if not listed:
        pytest.skip("the listing came back empty, so upstream was not reached")
    published = [url for url in listed if re.search(api.DATE_REGEX, url.rsplit("/", 1)[-1])]
    assert published, (
        f"{len(listed)} entries listed for DD and not one of them is a file the index reads: "
        f"{[url.rsplit('/', 1)[-1] for url in listed[:3]]}"
    )
    files = download_files(
        urls=published[-1:],
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.TWELVE_HOURS,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
    )
    # the size the collector itself uses to tell an empty file from one with readings in it
    with_content = [file for file in files if file.nbytes > 142]
    if not with_content:
        pytest.skip("the group published only empty files")
    parameters = list(DwdRoadRequest.metadata["15_minutes"]["data"])
    parse = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data  # noqa: SLF001
    df = parse(with_content[0], parameters)
    assert not df.drop_nulls("value").is_empty(), (
        f"{with_content[0].url} holds {with_content[0].nbytes} bytes and decoded to no readings"
    )


@pytest.mark.parametrize(
    ("celsius", "expected", "case"),
    [
        (-75.0, True, "the value KM's stopped sensors hold, colder than anywhere on earth has been"),
        (-61.0, True, "below the line"),
        (-59.0, False, "cold beyond anything Germany has recorded, but not impossible"),
        (-45.9, False, "Germany's record low, which the network may legitimately report"),
        (-30.0, False, "reachable on a German road in winter; the run rule judges this one"),
        (-25.0, False, "likewise"),
        (79.8, False, "implausible at 23:00 in September, but no line is drawn at the warm end"),
    ],
)
def test_dwd_road_weather_impossible_temperature_is_marked(
    celsius: float,
    expected: bool,  # noqa: FBT001
    case: str,
) -> None:
    """A temperature no reading can hold is marked suspect; a merely extreme one is not."""
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    readings = _series("A006", "roadSurfaceTemperature", [api._MELTING_POINT + celsius] * 3)  # noqa: SLF001

    df = api._flag_impossible_temperatures(readings, "a-group")  # noqa: SLF001

    marked = df.get_column("quality").eq(1.0).fill_null(value=False)
    # every reading or none of them: the three here hold the same value, so a rule that marked some
    # of them would be answering something other than what the value is
    assert marked.all() == expected, case
    assert marked.any() == expected, case


def test_dwd_road_weather_impossible_temperature_names_what_it_marked(caplog: pytest.LogCaptureFixture) -> None:
    """The line written for a caller who turns the log up names the sensors and the threshold.

    Written at `DEBUG`, which neither the CLI nor the REST API prints, and it says the readings are
    kept -- a caller reading it should not go looking for values that were removed.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    readings = _series("H659", "roadSurfaceTemperature", [api._MELTING_POINT - 75.0] * 3)  # noqa: SLF001

    with caplog.at_level(logging.DEBUG):
        api._flag_impossible_temperatures(readings, "a-group")  # noqa: SLF001

    assert "a-group: 1 sensors report a temperature below -60 C" in caplog.text
    assert "H659/roadSurfaceTemperature" in caplog.text
    assert "kept as published" in caplog.text


def test_dwd_road_weather_impossible_temperature_needs_no_window() -> None:
    """The mark does not wait for the six hours the run rule needs to see.

    Which is the whole of what it adds: asked for twelve hours, the run rule marks KM's stopped
    sensors; asked for one, it has five readings to judge from and marks nothing, while the station
    still reports -75 C.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    # five readings, as an hour of this network holds -- far short of the 24 the run rule wants
    an_hour = _series("A006", "roadSurfaceTemperature", [api._MELTING_POINT - 75.0] * 5)  # noqa: SLF001

    assert not api._flag_stuck_sensors(an_hour, "a-group").get_column("quality").eq(1.0).any()  # noqa: SLF001
    marked = api._flag_impossible_temperatures(an_hour, "a-group").get_column("quality")  # noqa: SLF001
    assert marked.eq(1.0).fill_null(value=False).all()


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("waterFilmThickness", -75.0),
        # a humidity and a wind speed are below any line drawn in kelvin by construction, which is
        # what a list shared with the stuck-sensor rule would have marked a whole network of
        ("relativeHumidity", 87.0),
        ("windSpeed", 3.4),
        ("horizontalVisibility", 12000.0),
    ],
)
def test_dwd_road_weather_impossible_temperature_leaves_other_quantities_alone(
    parameter: str,
    value: float,
) -> None:
    """Only what is measured on the temperature scale is judged against a temperature.

    A humidity of 87 % and a wind of 3.4 m/s are ordinary readings that happen to be small numbers;
    read as kelvin they are far below anything on earth, so the quantities this line applies to are
    named for being temperatures rather than borrowed from a rule that happens to name the same
    three for another reason.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    other = _series("A006", parameter, [value] * 3)

    assert api._flag_impossible_temperatures(other, "a-group").get_column("quality").is_null().all()  # noqa: SLF001


def test_dwd_road_weather_a_quantity_added_to_the_stuck_rule_is_not_judged_as_a_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deciding a stuck humidity is a fault does not make a humidity a temperature.

    The two lists name the same three quantities today for different reasons, and the stuck rule's
    own reasoning invites adding one to it. Answered from a single list, that edit would mark every
    humidity in the network suspect -- 87 % read as kelvin being 186 K below freezing -- from a
    change that looks unrelated to this rule.
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    monkeypatch.setattr(api, "_STUCK_PARAMETERS", (*api._STUCK_PARAMETERS, "relativeHumidity"))  # noqa: SLF001
    humidity = _series("A006", "relativeHumidity", [87.0] * 3)

    marked = api._flag_impossible_temperatures(humidity, "a-group").get_column("quality")  # noqa: SLF001
    assert marked.is_null().all()


def test_dwd_road_weather_impossible_temperature_keeps_the_reading() -> None:
    """The reading is left exactly as DWD published it; only the verdict on it is ours."""
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    published = api._MELTING_POINT - 75.0  # noqa: SLF001
    readings = _series("A006", "airTemperature", [published] * 3)

    df = api._flag_impossible_temperatures(readings, "a-group")  # noqa: SLF001

    assert df.get_column("value").eq(published).all()
