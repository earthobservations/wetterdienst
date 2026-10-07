# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD derived station data."""

import datetime as dt
import subprocess
import sys
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from dirty_equals import IsDatetime, IsDict
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.provider.dwd.derived.api import DwdDerivedRequest
from wetterdienst.provider.dwd.derived.metadata import DwdDerivedMetadata
from wetterdienst.provider.dwd.derived.metaindex import (
    _generate_digit_combinations,
    _get_raw_station_data_from_plz_generator,
    _read_meta_df,
)
from wetterdienst.util.network import File


@pytest.fixture
def expected_data() -> list[dict]:
    """Provide expected DataFrame for station."""
    return [
        {
            "resolution": "monthly",
            "dataset": "heating_degreedays",
            "station_id": "00433",
            "start_timestamp": dt.datetime(1918, 4, 1, tzinfo=ZoneInfo("UTC")),
            "end_timestamp": IsDatetime,
            "latitude": 52.4676,
            "longitude": 13.4020,
            "elevation": 48.0,
            "name": "Berlin-Tempelhof",
            "region": "Berlin",
        },
    ]


@pytest.mark.remote
def test_dwd_derived_soil_stations_filter(default_settings: Settings) -> None:
    """Test to check station ID filter."""
    request = DwdDerivedRequest(
        parameters=["monthly", "soil"],
        start="2024-05-05",
        end="2026-03-05",
        settings=default_settings,
    )
    stations = request.filter_by_station_id(station_id=("01001", "00150"))
    expected_data = [
        {
            "resolution": "monthly",
            "dataset": "soil",
            "station_id": "00150",
            "start_timestamp": None,
            "end_timestamp": None,
            "latitude": 49.73,
            "longitude": 8.12,
            "elevation": 215.0,
            "name": "Alzey",
            "region": "Rheinland-Pfalz",
        },
        {
            "resolution": "monthly",
            "dataset": "soil",
            "station_id": "01001",
            "start_timestamp": None,
            "end_timestamp": None,
            "latitude": 51.65,
            "longitude": 13.57,
            "elevation": 97.0,
            "name": "Doberlug-Kirchhain",
            "region": "Brandenburg",
        },
    ]
    assert stations.df.to_dicts() == expected_data


@pytest.mark.remote
def test_dwd_derived_radiation_stations_filter(default_settings: Settings) -> None:
    """Test to check station ID filter."""
    request = DwdDerivedRequest(
        parameters=["hourly", "radiation_global"],
        start="2024-05-05",
        end="2025-03-05",
        settings=default_settings,
    )
    stations = request.filter_by_station_id(station_id=("18000", "18575"))
    expected_data = [
        {
            "resolution": "hourly",
            "dataset": "radiation_global",
            "station_id": "18000",
            "start_timestamp": dt.datetime(2024, 4, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "end_timestamp": IsDatetime,
            "latitude": 47.9736,
            "longitude": 8.5205,
            "elevation": 680.0,
            "name": "Donaueschingen (Landeplatz)_DUETT",
            "region": "Baden-Württemberg",
        },
        {
            "resolution": "hourly",
            "dataset": "radiation_global",
            "station_id": "18575",
            "start_timestamp": dt.datetime(2024, 4, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "end_timestamp": IsDatetime,
            "latitude": 54.0246,
            "longitude": 9.388,
            "elevation": 48.0,
            "name": "Wacken_DUETT",
            "region": "Schleswig-Holstein",
        },
    ]
    assert stations.df.to_dicts() == expected_data


@pytest.mark.remote
@pytest.mark.parametrize(
    "period",
    [
        "historical",
        "recent",
    ],
    ids=[
        "fetching_derived_soil_station_00433_with_period_historical",
        "fetching_derived_soil_station_00433_with_period_recent",
    ],
)
def test_dwd_derived_stations_filter(default_settings: Settings, expected_data: list[dict], period: str) -> None:
    """Test to check station ID filter."""
    request = DwdDerivedRequest(
        parameters=("monthly", "heating_degreedays"),
        periods=period,
        settings=default_settings,
    ).filter_by_station_id(station_id="00433")
    assert request.df.to_dicts() == expected_data


def test_dwd_derived_stations_filter_false_period(default_settings: Settings) -> None:
    """Test to check for error on unknown period."""
    period = "hadean"
    with pytest.raises(InvalidEnumerationError) as exception_info:
        DwdDerivedRequest(
            parameters=("monthly", "heating_degreedays"),
            periods=period,
            settings=default_settings,
        ).filter_by_station_id(station_id="00433")
    assert exception_info.match(f"{period} could not be parsed from Period.")


@pytest.mark.remote
def test_dwd_derived_stations_filter_name(default_settings: Settings, expected_data: list[dict]) -> None:
    """Test fetching of DWD derived stations with filter by name."""
    # Existing combination of parameters
    request = DwdDerivedRequest(
        parameters=[("monthly", "heating_degreedays")],
        periods="historical",
        settings=default_settings,
    ).filter_by_name(name="Berlin-Tempelhof")
    assert request.df.to_dicts() == expected_data


@pytest.mark.remote
def test_dwd_observations_stations_name_with_comma() -> None:
    """Test fetching of DWD observation stations."""
    request = DwdDerivedRequest(
        parameters=[("monthly", "heating_degreedays")],
        periods="recent",
    )
    stations = request.all()
    stations = stations.df.filter(pl.col("station_id").is_in(["00183", "03287", "04806", "19172"]))
    assert stations.to_dicts() == [
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "00183",
                "start_timestamp": dt.datetime(1936, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_timestamp": IsDatetime,
                "latitude": 54.6791,
                "longitude": 13.4344,
                "elevation": 42.0,
                "name": "Arkona",
                "region": "Mecklenburg-Vorpommern",
            },
        ),
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "03287",
                "start_timestamp": dt.datetime(1987, 10, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_timestamp": IsDatetime,
                "latitude": 49.7177,
                "longitude": 9.0997,
                "elevation": 453.0,
                "name": "Michelstadt-Vielbrunn",
                "region": "Hessen",
            },
        ),
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "04806",
                "start_timestamp": dt.datetime(1882, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_timestamp": dt.datetime(1983, 12, 31, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "latitude": 50.7832,
                "longitude": 11.0880,
                "elevation": 370.0,
                "name": "Stadtilm",
                "region": "Thüringen",
            },
        ),
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "19172",
                "start_timestamp": dt.datetime(2020, 9, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_timestamp": IsDatetime,
                "latitude": 54.0246,
                "longitude": 9.3880,
                "elevation": 48.0,
                "name": "Wacken",
                "region": "Schleswig-Holstein",
            },
        ),
    ]


@pytest.mark.remote
@pytest.mark.parametrize(
    (
        "station_id",
        "period",
    ),
    [
        (
            "ab123",
            "recent",
        ),
        (
            "ab123",
            "historical",
        ),
        (
            "",
            "recent",
        ),
        (
            "",
            "historical",
        ),
    ],
    ids=[
        "non_existent_dwd_derived_station_id_and_recent_period",
        "non_existent_dwd_derived_station_id_and_historical_period",
        "missing_dwd_derived_station_id_and_recent_period",
        "missing_dwd_derived_station_id_and_historical_period",
    ],
)
def test_dwd_derived_stations_filter_misentries(
    default_settings: Settings,
    station_id: str,
    period: str,
) -> None:
    """Test to check for handling of missing or incorrect parameter inputs."""
    request = DwdDerivedRequest(
        parameters=("monthly", "heating_degreedays"),
        periods=period,
        settings=default_settings,
    ).filter_by_station_id(station_id=station_id)
    assert request.df.is_empty()


def test_generate_digit_combinations() -> None:
    """Test to check digit combination generation."""
    generated_combinations = _generate_digit_combinations(
        number_of_digits=1,
    )
    assert list(generated_combinations) == ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]

    for number_of_digits in range(2, 6):
        generated_combinations = list(
            _generate_digit_combinations(
                number_of_digits=number_of_digits,
            )
        )
        assert len(generated_combinations) == 10**number_of_digits
        assert all(len(combination) == number_of_digits for combination in generated_combinations)


def test_get_raw_station_data_from_plz_generator() -> None:
    """Test to check dimensions of proxy PLZ station data."""
    raw_station_data = _get_raw_station_data_from_plz_generator().collect()
    assert raw_station_data.shape == (10**5, 8)


def test_read_meta_df_fixed_width_station_list() -> None:
    """The fixed-width station lists are read with polars, without pandas (GH-2213).

    The rows are copied from `KL_Monatswerte_Beschreibung_Stationen.txt` as DWD publishes it:
    latin-1, CRLF line ends, the trailing `Abgabe` column, padding after it and a final line
    break. The last row of that file is included, as are a name with an umlaut, one with a comma
    and a region with an umlaut. The expected frame is the one the former `pandas.read_fwf` reader
    built from the same rows.
    """
    lines = [
        "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe",
        (
            "----------- --------- --------- ------------- --------- --------- "
            "----------------------------------------- ---------- ------"
        ),
        (
            "00001 19310101 19860630            478     47.8413    8.8493 Aach                                     "
            "Baden-Württemberg                        Frei      "
        ),
        (
            "00044 19710301 20260831             44     52.9336    8.2370 Großenkneten                             "
            "Niedersachsen                            Frei      "
        ),
        (
            "20318 19370801 19601231            352     48.7726    8.7287 Liebenzell, Bad/ Nagold                  "
            "Baden-Württemberg                        Frei      "
        ),
        (
            "20327 19450101 19951231            870     47.9394    8.1933 Titisee-Neustadt-Neustadt                "
            "Baden-Württemberg                        Frei      "
        ),
    ]
    content = "".join(f"{line}\r\n" for line in lines).encode("latin-1")
    file = File(
        url="https://example.org/KL_Monatswerte_Beschreibung_Stationen.txt", content=BytesIO(content), status=200
    )
    df = _read_meta_df(DwdDerivedMetadata.monthly.heating_degreedays, file=file).collect()

    def date(year: int, month: int, day: int) -> dt.datetime:
        return dt.datetime(year, month, day, tzinfo=ZoneInfo("UTC"))

    expected = pl.DataFrame(
        {
            "station_id": ["00001", "00044", "20318", "20327"],
            "start_timestamp": [date(1931, 1, 1), date(1971, 3, 1), date(1937, 8, 1), date(1945, 1, 1)],
            "end_timestamp": [date(1986, 6, 30), date(2026, 8, 31), date(1960, 12, 31), date(1995, 12, 31)],
            "elevation": [478.0, 44.0, 352.0, 870.0],
            "latitude": [47.8413, 52.9336, 48.7726, 47.9394],
            "longitude": [8.8493, 8.2370, 8.7287, 8.1933],
            "name": ["Aach", "Großenkneten", "Liebenzell, Bad/ Nagold", "Titisee-Neustadt-Neustadt"],
            "region": ["Baden-Württemberg", "Niedersachsen", "Baden-Württemberg", "Baden-Württemberg"],
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    assert_frame_equal(df, expected)


def test_dwd_derived_imports_without_pandas() -> None:
    """`dwd/derived` resolves and reads a station list on a base install, which has no pandas (GH-2213).

    Run in a fresh interpreter with pandas made unimportable, since this one may have imported it
    already for another test.
    """
    code = """
import sys
from io import BytesIO

sys.modules["pandas"] = None

from wetterdienst import Wetterdienst
from wetterdienst.provider.dwd.derived.metadata import DwdDerivedMetadata
from wetterdienst.provider.dwd.derived.metaindex import _read_meta_df
from wetterdienst.util.network import File

print(Wetterdienst("dwd", "derived").__name__)
row = "00001 19310101 19860630            478     47.8413    8.8493 Aach"
content = BytesIO(f"header\\r\\nrule\\r\\n{row}\\r\\n".encode("latin-1"))
file = File(url="https://example.org/stations.txt", content=content, status=200)
print(_read_meta_df(DwdDerivedMetadata.monthly.heating_degreedays, file=file).collect()["name"].item())
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["DwdDerivedRequest", "Aach"]


def test_read_meta_df_breaks_rows_only_at_line_ends() -> None:
    """A byte 0x85 in a station name stays in the name rather than splitting the row (GH-2213).

    Decoded as latin-1 it is U+0085, which `str.splitlines` takes for a line break, as pandas did not.
    """
    # the name field is 41 characters wide, the space after it included
    row = "00001 19310101 19860630            478     47.8413    8.8493 " + "Bad\x85Aach".ljust(41) + "Bayern"
    content = BytesIO(f"header\r\nrule\r\n{row}\r\n".encode("latin-1"))
    file = File(url="https://example.org/stations.txt", content=content, status=200)
    df = _read_meta_df(DwdDerivedMetadata.monthly.heating_degreedays, file=file).collect()
    assert df.select("station_id", "name", "region").rows() == [("00001", "Bad\x85Aach", "Bayern")]


def test_read_meta_df_four_digit_elevation() -> None:
    """A station at 1000 m or higher keeps its elevation and its end date (GH-2234).

    The rows are copied from `KL_Monatswerte_Beschreibung_Stationen.txt` as DWD publishes it, up to
    the `Abgabe` column, leaving out the padding after it. The elevation is right-aligned to end at
    character 37, so a fourth digit sits at character 34; the station between them shows the
    three-digit case still reads.
    """
    rows = [
        (
            "00722 18810601 20260831           1135     51.7986   10.6183 Brocken                                  "
            "Sachsen-Anhalt                           Frei"
        ),
        (
            "04878 19060101 20260831            505     51.6647   10.8810 Oberharz am Brocken-Stiege               "
            "Sachsen-Anhalt                           Frei"
        ),
        (
            "05792 19000801 20260831           2956     47.4210   10.9848 Zugspitze                                "
            "Bayern                                   Frei"
        ),
    ]
    content = BytesIO("".join(f"{line}\r\n" for line in ["header", "rule", *rows]).encode("latin-1"))
    file = File(url="https://example.org/KL_Monatswerte_Beschreibung_Stationen.txt", content=content, status=200)
    df = _read_meta_df(DwdDerivedMetadata.monthly.heating_degreedays, file=file).collect()

    def date(year: int, month: int, day: int) -> dt.datetime:
        return dt.datetime(year, month, day, tzinfo=ZoneInfo("UTC"))

    end_date = date(2026, 8, 31)
    assert df.rows() == [
        ("00722", date(1881, 6, 1), end_date, 1135.0, 51.7986, 10.6183, "Brocken", "Sachsen-Anhalt"),
        (
            "04878",
            date(1906, 1, 1),
            end_date,
            505.0,
            51.6647,
            10.8810,
            "Oberharz am Brocken-Stiege",
            "Sachsen-Anhalt",
        ),
        ("05792", date(1900, 8, 1), end_date, 2956.0, 47.4210, 10.9848, "Zugspitze", "Bayern"),
    ]
