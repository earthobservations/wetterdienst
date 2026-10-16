# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the NOAA Global Historical Climatology Network (GHCN) API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Options, Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata, NoaaGhcnRequest


@pytest.mark.remote
@pytest.mark.slow
@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (dt.datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (dt.datetime(2015, 1, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (dt.datetime(2015, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (
            dt.datetime(2015, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2022, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
        ),
    ],
)
def test_api_amsterdam(start_date: dt.datetime, end_date: dt.datetime, default_settings: Settings) -> None:
    """Test fetching of Amsterdam weather data."""
    request = NoaaGhcnRequest(
        parameters=[NoaaGhcnMetadata.daily.data.temperature_air_mean_2m],
        start=start_date,
        end=end_date,
        settings=default_settings,
    ).filter_by_name("DE BILT")
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "NLM00006260",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")),
                "value": 3.7,
                # Global Summary of the Day (source S), a daily mean made of hourly values (measurement H): the
                # readme.txt's "H = for TMAX/TMIN/TAVG represents highest or lowest hourly temperature (TMAX or
                # TMIN) or the average of hourly values (TAVG)" and "S = Global Summary of the Day"; no check failed
                "quality_flags": "measurement:H,source:S",
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(
        given_df.filter(pl.col("timestamp").eq(dt.datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")))),
        expected_df,
    )


@pytest.mark.remote
@pytest.mark.slow
def test_api_hourly_neustrelitz(default_settings: Settings) -> None:
    """Hourly (GHCNh) values parse with correct timestamps from the ISO date column."""
    request = NoaaGhcnRequest(
        parameters=[NoaaGhcnMetadata.hourly.data.temperature_air_2m],
        start=dt.datetime(1977, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1977, 2, 1, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id("GMA00092791")  # Neustrelitz, Germany -- non-US, immutable historical data
    given_df = request.values().all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "GMA00092791",
                "resolution": "hourly",
                "dataset": "data",
                "parameter": "temperature_air_2m",
                "timestamp": dt.datetime(1977, 1, 10, 2, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                # `temperature_Quality_Code` and `temperature_Source_Code` (221) of the file's row (GH-2754, GH-2925)
                "quality_flags": "1,source:221",
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(
        given_df.filter(pl.col("timestamp").eq(dt.datetime(1977, 1, 10, 2, tzinfo=ZoneInfo("UTC")))),
        expected_df,
    )


def test_api_hourly_wind_direction_999_is_no_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    """GHCNh writes 999 where no wind direction was given; it is no direction, while 999 hPa is a pressure (GH-2672).

    Rows of GHCNh_ACM00078861_por.psv (Antigua): 1942-01-17 02:00 reads 999 with code C (calm) and a wind speed of 0.0,
    1942-01-28 14:00 reads 999 with no code and a wind speed of 4.1. The documentation words the missing precipitation
    as -9999.
    """
    from tests.provider.value_stubs import ghcnh_psv, serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD ANTIGUA,,,78861,,AG\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]]
    rows = {
        2: {"wind_direction": "999", "wind_speed": "0.0", "sea_level_pressure": "999.0", "precipitation": "-9999"},
        3: {"wind_direction": "0", "wind_speed": "0.0", "sea_level_pressure": "1001.5", "precipitation": "0.0"},
        4: {"wind_direction": "90", "wind_speed": "4.1", "sea_level_pressure": "1001.0", "precipitation": "0.2"},
        5: {"wind_direction": "999", "wind_speed": "4.1", "sea_level_pressure": "1000.0", "precipitation": "-9999.0"},
    }
    body = ghcnh_psv("ACM00078861", columns, [(f"1942-01-17T{hour:02d}:00:00", row) for hour, row in rows.items()])
    serve(monkeypatch, api, {"ghcnh-station-list": stations, "GHCNh_ACM00078861": body})
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(1942, 1, 17, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1942, 1, 18, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    ).filter_by_station_id("ACM00078861")
    df = request.values().all().df

    def column(parameter: str) -> list[tuple[int, float]]:
        frame = df.filter(pl.col("parameter").eq(parameter)).sort("timestamp")
        return list(
            zip(frame.get_column("timestamp").dt.hour().to_list(), frame.get_column("value").to_list(), strict=True)
        )

    # the hours without a direction have no row, as with every missing value; hour 3 is a calm, "000" in the
    # documentation and 0 in the file, and no direction either (GH-2794)
    assert column("wind_direction") == [(4, 90.0)]
    assert column("wind_speed") == [(2, 0.0), (3, 0.0), (4, 4.1), (5, 4.1)]
    assert column("pressure_air_sea_level") == [(2, 999.0), (3, 1001.5), (4, 1001.0), (5, 1000.0)]
    assert column("precipitation_amount") == [(3, 0.0), (4, 0.2)]


def test_api_hourly_wind_direction_000_of_a_calm_is_null_with_the_text_the_file_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GHCNh writes 0 for a calm wind: "A direction of "000" is given for calm winds" (GH-2794).

    The documentation (ghcnh_DOCUMENTATION.pdf) gives 360 as true north. Rows of the files read on 2026-10-12, put into
    one: USW00023174 (Los Angeles) 2019-03-11 08:53 reads 360 beside 2.1 m/s and 2026-10-06 11:53 reads 0 beside 0.0;
    ASN00086282 1985-07-06 17:00 reads 0 beside 1.5 m/s, the one of 11,347 zeros of that file with a speed above 0.
    The 0 is null, with `raw:0` after the flags, and the speed of 0.0 is a reading.
    """
    from tests.provider.value_stubs import ghcnh_psv, serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"USW00023174,33.938,-118.3866,29.6,CA,LOS ANGELES INTL AP,,,72295,KLAX,US\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]]
    rows = [
        ("2019-03-11T08:53:00", {"wind_direction": "360", "wind_speed": "2.1"}),
        ("2019-03-11T09:53:00", {"wind_direction": "0", "wind_speed": "1.5"}),
        ("2019-03-11T10:53:00", {"wind_direction": "0", "wind_speed": "0.0"}),
    ]
    serve(
        monkeypatch,
        api,
        {"ghcnh-station-list": stations, "GHCNh_USW00023174": ghcnh_psv("USW00023174", columns, rows)},
    )
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data", "wind_direction"), ("hourly", "data", "wind_speed")],
        start=dt.datetime(2019, 3, 11, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2019, 3, 12, tzinfo=ZoneInfo("UTC")),
        settings=settings,
        options=Options(drop_nulls=False),
    ).filter_by_station_id("USW00023174")
    df = request.values().all().df.sort("parameter", "timestamp")
    assert df.select("parameter", "value", "quality_flags").rows() == [
        ("wind_direction", 360.0, None),
        ("wind_direction", None, "raw:0"),
        ("wind_direction", None, "raw:0"),
        ("wind_speed", 2.1, None),
        ("wind_speed", 1.5, None),
        ("wind_speed", 0.0, None),
    ]


def test_api_hourly_snow_depth_is_millimeters(monkeypatch: pytest.MonkeyPatch) -> None:
    """GHCNh writes the snow depth in millimeters: "depth of snowpack on the ground (millimeters)" (GH-2848).

    Rows of the by-year file GHCNh_USW00026451_2023.psv (Anchorage), read on 2026-10-13: 2023-02-13 reads 910 as the
    day's highest hourly depth, which the GHCN-daily SNWD (mm) of the station gives as 910 too. The reader hands the
    number on, so the declared unit is what says what it is: millimeters, which the default unit target
    (centimeters) turns into 91.0.
    """
    from tests.provider.value_stubs import ghcnh_psv, serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"USW00026451,61.169,-150.0278,38.0,AK,ANCHORAGE TED STEVENS INTL AP,,,70273,PANC,US\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data", "snow_depth")], settings=settings).metadata
    parameters = {parameter.name: parameter for parameter in metadata["hourly"]["data"]}
    assert parameters["snow_depth"].unit == "millimeter"
    columns = [parameter.name_original for parameter in parameters.values()]
    rows = [("2023-02-13T12:53:00", {"snow_depth": "910"}), ("2023-02-13T13:53:00", {"snow_depth": "-None"})]
    serve(
        monkeypatch,
        api,
        {"ghcnh-station-list": stations, "GHCNh_USW00026451": ghcnh_psv("USW00026451", columns, rows)},
    )

    def values(options: Options) -> list[float]:
        request = NoaaGhcnRequest(
            parameters=[("hourly", "data", "snow_depth")],
            start=dt.datetime(2023, 2, 13, tzinfo=ZoneInfo("UTC")),
            end=dt.datetime(2023, 2, 14, tzinfo=ZoneInfo("UTC")),
            settings=settings,
            options=options,
        ).filter_by_station_id("USW00026451")
        return request.values().all().df.get_column("value").to_list()

    assert values(Options(convert_units=False)) == [910.0]
    assert values(Options()) == [91.0]


def test_api_hourly_quality_code_is_the_plain_flag_and_the_value_stays(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `<element>_Quality_Code` of an hourly file is the quality flag as the file writes it (GH-2754).

    Rows of the files read on 2026-10-14, the codes of Table 3 of ghcnh_DOCUMENTATION.pdf. Antigua
    (GHCNh_ACM00078861_por.psv): 1988-01-27 11:00 reads a temperature of 50.0 with code 2, "Suspect", and a relative
    humidity of 16 with the letter f, a derived value with a suspect input; the file keeps both as values.
    1942-01-17 02:00 reads a wind direction of 999 with code 1: the sentinel is no direction, and the text of it
    follows the code. Anchorage (GHCNh_USW00026451_por.psv): 2016-09-04 06:53 reads a wind speed of 4.4 and a direction
    of 160, both with the letter U, and 2006-05-08 08:53 a speed of 4.0 with P, all of the legacy source 343. The stub
    leaves out the code 1 that the Antigua file gives the wind speeds of 1988-01-27 11:00 and 1942-01-17 02:00, to have
    values without a code, which have no flag.
    """
    from tests.provider.value_stubs import ghcnh_psv, serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD ANTIGUA,,,78861,,AG\n"
        b"USW00026451,61.169,-150.0278,38.0,AK,ANCHORAGE TED STEVENS INTL AP,,,70273,PANC,US\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]]
    antigua = [
        (
            "1988-01-27T11:00:00",
            {
                "temperature": "50.0",
                "temperature_Quality_Code": "2",
                "relative_humidity": "16",
                "relative_humidity_Quality_Code": "f",
                "wind_speed": "4.1",
            },
        ),
        ("1942-01-17T02:00:00", {"wind_direction": "999", "wind_direction_Quality_Code": "1", "wind_speed": "0.0"}),
    ]
    anchorage = [
        (
            "2016-09-04T06:53:00",
            {
                "wind_speed": "4.4",
                "wind_speed_Quality_Code": "U",
                "wind_direction": "160",
                "wind_direction_Quality_Code": "U",
            },
        ),
        ("2006-05-08T08:53:00", {"wind_speed": "4.0", "wind_speed_Quality_Code": "P"}),
    ]
    serve(
        monkeypatch,
        api,
        {
            "ghcnh-station-list": stations,
            "GHCNh_ACM00078861": ghcnh_psv("ACM00078861", columns, antigua),
            "GHCNh_USW00026451": ghcnh_psv("USW00026451", columns, anchorage),
        },
    )
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(1942, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2017, 1, 1, tzinfo=ZoneInfo("UTC")),
        settings=settings,
        options=Options(drop_nulls=False, convert_units=False),
    ).filter_by_station_id(["ACM00078861", "USW00026451"])
    df = request.values().all().df
    got = {
        (station, parameter, timestamp.strftime("%Y-%m-%d %H:%M")): (value, flags)
        for station, parameter, timestamp, value, flags in df.select(
            "station_id", "parameter", "timestamp", "value", "quality_flags"
        ).iter_rows()
    }
    # the suspect values are values, flagged as the file flags them, case included
    assert got["ACM00078861", "temperature_air_2m", "1988-01-27 11:00"] == (50.0, "2")
    assert got["ACM00078861", "humidity_relative", "1988-01-27 11:00"] == (16.0, "f")
    # a reading the file gave no code for has no flag
    assert got["ACM00078861", "wind_speed", "1988-01-27 11:00"] == (4.1, None)
    # the sentinel keeps its text after the code, as the last token
    assert got["ACM00078861", "wind_direction", "1942-01-17 02:00"] == (None, "1,raw:999")
    assert got["USW00026451", "wind_speed", "2016-09-04 06:53"] == (4.4, "U")
    assert got["USW00026451", "wind_direction", "2016-09-04 06:53"] == (160.0, "U")
    assert got["USW00026451", "wind_speed", "2006-05-08 08:53"] == (4.0, "P")


def test_api_hourly_measurement_and_source_codes_follow_the_quality_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """The measurement and source codes are the tokens `measurement:` and `source:` after the quality code (GH-2925).

    Rows of the files read on 2026-10-15 (the report type is `SAO` throughout, which nothing reads). The same quality
    code reads differently by source (Table 3 of ghcnh_DOCUMENTATION.pdf): Anchorage (GHCNh_USW00026451_por.psv)
    writes `4` for
    "Passed gross limits check, NCEI" of a temperature of source 335 (1953-11-01 10:00) and "Calculated" of source 223
    (1997-01-31 11:50), and ASN00086282 is source 401 with a `0` that Table 3 does not list (1970-06-30 23:00). The
    measurement code is a trace of precipitation `T` (Anchorage 1996-07-08 19:00, with the quality code `5` of source
    335) and the tendency `7` of the 3-hour pressure change, "a decrease" (Antigua 1942-09-01 06:00, -1.4 hPa). Antigua
    1942-01-17 02:00 reads a wind direction of 999 and a speed of 0.0, both with the measurement code C, the quality
    code 1 and source 220: the text of the sentinel stays the last token. CAMU0019904 writes the text `Null` for a code
    it has none of (source 245), which is no code.
    """
    from tests.provider.value_stubs import ghcnh_psv, serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD ANTIGUA,,,78861,,AG\n"
        b"USW00026451,61.169,-150.0278,38.0,AK,ANCHORAGE TED STEVENS INTL AP,,,70273,PANC,US\n"
        b"ASN00086282,-37.6733,144.8433,113.4,,MELBOURNE AIRPORT,,,94866,YMML,AS\n"
        b"CAMU0019904,45.5,-73.5,30.0,,MONTREAL,,,,,CA\n"
    )

    def attributes(element: str, measurement: str | None, quality: str, source: str) -> dict[str, str]:
        row = {f"{element}_Quality_Code": quality, f"{element}_Source_Code": source, f"{element}_Report_Type": "SAO"}
        if measurement is not None:
            row[f"{element}_Measurement_Code"] = measurement
        return row

    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]]
    files = {
        "ACM00078861": [
            (
                "1942-01-17T02:00:00",
                {
                    "wind_direction": "999",
                    **attributes("wind_direction", "C", "1", "220"),
                    "wind_speed": "0.0",
                    **attributes("wind_speed", "C", "1", "220"),
                },
            ),
            (
                "1942-09-01T06:00:00",
                {"pressure_3hr_change": "-1.4", **attributes("pressure_3hr_change", "7", "1", "220")},
            ),
        ],
        "USW00026451": [
            ("1953-11-01T10:00:00", {"temperature": "-12.2", **attributes("temperature", None, "4", "335")}),
            ("1996-07-08T19:00:00", {"precipitation": "0.0", **attributes("precipitation", "T", "5", "335")}),
            ("1997-01-31T11:50:00", {"temperature": "0.4", **attributes("temperature", None, "4", "223")}),
        ],
        "ASN00086282": [
            ("1970-06-30T23:00:00", {"temperature": "10.4", **attributes("temperature", None, "0", "401")})
        ],
        "CAMU0019904": [
            ("1940-01-01T12:00:00", {"temperature": "-28.9", **attributes("temperature", "Null", "Null", "245")}),
        ],
    }
    serve(
        monkeypatch,
        api,
        {"ghcnh-station-list": stations}
        | {f"GHCNh_{station}": ghcnh_psv(station, columns, rows) for station, rows in files.items()},
    )
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(1940, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
        settings=settings,
        options=Options(drop_nulls=False, convert_units=False),
    ).filter_by_station_id(list(files))
    df = request.values().all().df
    got = {
        (station, parameter, timestamp.strftime("%Y-%m-%d %H:%M")): (value, flags)
        for station, parameter, timestamp, value, flags in df.select(
            "station_id", "parameter", "timestamp", "value", "quality_flags"
        ).iter_rows()
        if value is not None or flags is not None
    }
    # the quality code means "passed gross limits" for source 335 and "calculated" for source 223: the source says which
    assert got["USW00026451", "temperature_air_2m", "1953-11-01 10:00"] == (-12.2, "4,source:335")
    assert got["USW00026451", "temperature_air_2m", "1997-01-31 11:50"] == (0.4, "4,source:223")
    assert got["ASN00086282", "temperature_air_2m", "1970-06-30 23:00"] == (10.4, "0,source:401")
    # the measurement code is the trace of a precipitation of 0.0 and the tendency of a pressure change
    assert got["USW00026451", "precipitation_amount", "1996-07-08 19:00"] == (0.0, "5,measurement:T,source:335")
    assert got["ACM00078861", "pressure_air_site_delta_last_3h", "1942-09-01 06:00"] == (
        -1.4,
        "1,measurement:7,source:220",
    )
    # a calm is the measurement code C; the text of the sentinel is still the last token
    assert got["ACM00078861", "wind_speed", "1942-01-17 02:00"] == (0.0, "1,measurement:C,source:220")
    assert got["ACM00078861", "wind_direction", "1942-01-17 02:00"] == (None, "1,measurement:C,source:220,raw:999")
    # `Null` is the source's way of writing no code: the reading has no flag but the source
    assert got["CAMU0019904", "temperature_air_2m", "1940-01-01 12:00"] == (-28.9, "source:245")
