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
    assert column("precipitation_amount_since_last_routine_report") == [(3, 0.0), (4, 0.2)]


def test_api_hourly_precipitation_is_the_total_of_the_report_that_closes_the_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The METAR amount is a running total, so an hour keeps the report at the routine minute (GH-2841).

    The documentation (section IX): "When multiple observations are transmitted within the hour, the precipitation
    totals represent a running total for that hour. To extract the total precipitation for a particular hour, the last
    report should be used", the P group being "since the last routine METAR". Rows of GHCNh_USW00023174_2022.psv (Los
    Angeles, read 2026-10-16), in UTC: 2022-03-28 18:15 to 18:53 holds the SPECI 2.5, 3.3 and 3.5 mm and the routine
    METAR 2.8 mm, of the source 343; 17:37 holds a SPECI of 9.3 mm, the METAR of 17:53 12.4 mm and a SPECI of 17:57
    0.2 mm, which is what fell since that METAR and which the METAR of 18:53 holds again; 2022-11-02 07:53 holds
    a METAR of 0.8 mm and 07:58 a SPECI of 0.0 mm. Of the 98 hours of 2022 with several reports four end in such a
    SPECI. Denver 2026-09-18 (GHCNh_USW00003017_2026.psv, read 2026-10-16): 23:34 holds a SPECI of 21.6 mm, the METAR
    of 23:53 the same 21.6 mm and an `FM15` of source 413 at 23:59 0.0 mm, which is what fell since, as at 22:59 (2.3
    mm after 0.0 at 22:53); 21:53 is added to make :53 the routine minute of the month. LAX 1996-10-30 12:00 holds a
    `SYMT` row of 11.4 mm, the METAR of 12:53 5.6 mm: the routine minute is that of the month, as LAX reports at :00
    until June 1996 and at :50 to :54 after. 2022-03-29 is made up: 01:20
    and 01:40 hold SPECI only (the last one is the hour's), 02:53 a METAR with the missing value -9999, which is the
    hour's, and 02:10 a SPECI of 1.0 mm whose amount does not stand in for it. The other elements keep one reading for
    each full hour (GH-3000), the 22 rows of the temperature being 11.
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

    def report(time: str, amount: str, report_type: str) -> tuple[str, dict[str, str]]:
        return (
            f"{time}:00",
            {
                "temperature": "14.4",
                "precipitation": amount,
                "precipitation_Report_Type": report_type,
                "precipitation_Source_Code": "343" if report_type == "FM15" else "223",
            },
        )

    rows = [
        # LAX 1996 (GHCNh_USW00023174_1996.psv): the METARs of the autumn come at :53, the `SYMT` row of 12:00 holds
        # the amount of the hour before; 11:53 is made up, to make :53 the routine minute of the month
        report("1996-10-30T11:53", "0.0", "FM15"),
        report("1996-10-30T12:00", "11.4", "SYMT"),
        report("1996-10-30T12:53", "5.6", "FM15"),
        report("2022-03-28T17:37", "9.3", "FM16"),
        report("2022-03-28T17:53", "12.4", "FM15"),
        report("2022-03-28T17:57", "0.2", "FM16"),
        report("2022-03-28T18:15", "2.5", "FM16"),
        report("2022-03-28T18:30", "3.3", "FM16"),
        report("2022-03-28T18:41", "3.5", "FM16"),
        report("2022-03-28T18:53", "2.8", "FM15"),
        report("2022-11-02T07:53", "0.8", "FM15"),
        report("2022-11-02T07:58", "0.0", "FM16"),
        report("2022-03-29T01:20", "0.2", "FM16"),
        report("2022-03-29T01:40", "0.5", "FM16"),
        report("2022-03-29T02:10", "1.0", "FM16"),
        report("2022-03-29T02:53", "-9999", "FM15"),
        # Denver (GHCNh_USW00003017_2026.psv): source 413 files `FM15` reports at other minutes after the METAR
        report("2026-09-18T21:53", "0.0", "FM15"),
        report("2026-09-18T22:53", "0.0", "FM15"),
        report("2026-09-18T22:59", "2.3", "FM15"),
        report("2026-09-18T23:34", "21.6", "FM16"),
        report("2026-09-18T23:53", "21.6", "FM15"),
        report("2026-09-18T23:59", "0.0", "FM15"),
    ]
    serve(
        monkeypatch,
        api,
        {"ghcnh-station-list": stations, "GHCNh_USW00023174": ghcnh_psv("USW00023174", columns, rows)},
    )
    request = NoaaGhcnRequest(
        parameters=[
            ("hourly", "data", "precipitation_amount_since_last_routine_report"),
            ("hourly", "data", "temperature_air_2m"),
        ],
        start=dt.datetime(1996, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2027, 1, 1, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    ).filter_by_station_id("USW00023174")
    df = request.values().all().df.sort("timestamp")
    precipitation = df.filter(pl.col("parameter").eq("precipitation_amount_since_last_routine_report"))
    # one report an hour: the METAR, no SPECI after it, and the last SPECI of an hour without a METAR; the -9999 of
    # the METAR closing 02:00 is no value and the SPECI before it is not the hour's. The reading is stamped with the
    # full hour its report is nearest to (GH-3000): the METAR of 17:53 closes the hour 17 and is stamped 18:00
    assert [
        (f"{ts:%y-%m-%dT%H:%M}", value) for ts, value in precipitation.select("timestamp", "value").iter_rows()
    ] == [
        ("96-10-30T12:00", 0.0),
        ("96-10-30T13:00", 5.6),
        ("22-03-28T18:00", 12.4),
        ("22-03-28T19:00", 2.8),
        ("22-03-29T02:00", 0.5),
        ("22-11-02T08:00", 0.8),
        # the routine minute of the month is :53, whatever is filed after it, the 21.6 mm of 23:00 included
        ("26-09-18T22:00", 0.0),
        ("26-09-18T23:00", 0.0),
        ("26-09-19T00:00", 21.6),
    ]
    # the other elements keep one reading for each full hour too, the nearest to it (the SPECI of 17:57, not the METAR)
    temperature = df.filter(pl.col("parameter").eq("temperature_air_2m"))
    assert temperature.height == temperature.get_column("timestamp").n_unique() == 11
    assert temperature.get_column("timestamp").dt.minute().unique().to_list() == [0]


def test_api_hourly_has_one_reading_for_each_parameter_and_full_hour_stamped_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The file holds every report of a station, `hourly` one reading for each full hour, stamped with it (GH-3000).

    Rows of GHCNh_USW00003017_2026.psv (Denver, by-year file, read 2026-10-17), 2026-09-18 20:53 to 2026-09-19 00:05.
    The routine METAR is at :53 (source 413), and at the synoptic hour 21:00 a SYNOP (`FM12`, source 412) beside it.
    The SPECI and the further `FM15` reports of 22:21, 22:47 and 22:59 and of 23:34 and 23:59 come between, the ones
    at :59 without a sea level pressure. The 5-minute rows (source 343) hold the 5-minute precipitation and no element
    that is read; two are in the stub. The temperature of an hour is the reading nearest to the full hour, and the sea
    level pressure that of the nearest report that has one: 22:59 reads 17.8 degrees, the METAR of 22:53 the 1013.7.
    The reading is stamped with the full hour it is nearest to, 22:59 with 23:00.
    """
    from tests.provider.value_stubs import ghcnh_psv, serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"USW00003017,39.8466,-104.6562,1647.2,CO,DENVER INTERNATIONAL AIRPORT,,,72565,KDEN,US\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]] + ["precipitation_5_minute"]

    def report(temperature: str, report_type: str, source: str, pressure: str | None = None) -> dict[str, str]:
        row = {
            "temperature": temperature,
            "temperature_Report_Type": report_type,
            "temperature_Source_Code": source,
        }
        if pressure is not None:
            row |= {
                "sea_level_pressure": pressure,
                "sea_level_pressure_Report_Type": report_type,
                "sea_level_pressure_Source_Code": source,
            }
        return row

    five_minutes = {"precipitation_5_minute": "0.0", "precipitation_5_minute_Source_Code": "343"}
    rows = [
        ("2026-09-18T20:53:00", report("28.3", "FM15", "413", "1011.5")),
        ("2026-09-18T21:00:00", report("28.3", "FM12", "412") | five_minutes),
        ("2026-09-18T21:05:00", five_minutes),
        ("2026-09-18T21:53:00", report("28.3", "FM15", "413", "1011.0")),
        ("2026-09-18T22:00:00", five_minutes),
        ("2026-09-18T22:21:00", report("26.1", "FM16", "413")),
        ("2026-09-18T22:47:00", report("22.0", "FM15", "413")),
        ("2026-09-18T22:53:00", report("17.8", "FM15", "413", "1013.7")),
        ("2026-09-18T22:59:00", report("17.8", "FM15", "413")),
        ("2026-09-18T23:34:00", report("15.6", "FM16", "413")),
        ("2026-09-18T23:53:00", report("16.7", "FM15", "413", "1015.5")),
        ("2026-09-18T23:59:00", report("16.7", "FM15", "413")),
        ("2026-09-19T00:05:00", {"precipitation_5_minute": "0.0", "precipitation_5_minute_Source_Code": "343"}),
    ]
    serve(
        monkeypatch,
        api,
        {"ghcnh-station-list": stations, "GHCNh_USW00003017": ghcnh_psv("USW00003017", columns, rows)},
    )
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data", "temperature_air_2m"), ("hourly", "data", "pressure_air_sea_level")],
        start=dt.datetime(2026, 9, 18, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2026, 9, 20, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    ).filter_by_station_id("USW00003017")
    df = request.values().all().df.sort("parameter", "timestamp")

    def column(parameter: str) -> list[tuple[str, float, str | None]]:
        frame = df.filter(pl.col("parameter").eq(parameter))
        return [
            (f"{ts:%d-%H:%M}", value, flags)
            for ts, value, flags in frame.select("timestamp", "value", "quality_flags").iter_rows()
        ]

    # 21:00 is the SYNOP, which is on the hour, not the METAR of 20:53; 22:00 the METAR of 21:53 (the 22:00 row is a
    # 5-minute row without a temperature); 23:00 the report of 22:59 and not the SPECI of 22:21 or the one of 22:47;
    # 00:00 that of 23:59, not the SPECI of 23:34 nor the METAR of 23:53
    assert column("temperature_air_2m") == [
        ("18-21:00", 28.3, "source:412"),
        ("18-22:00", 28.3, "source:413"),
        ("18-23:00", 17.8, "source:413"),
        ("19-00:00", 16.7, "source:413"),
    ]
    # the reports of :59 carry no sea level pressure, so the hours 23:00 and 00:00 read the METARs of :53
    assert column("pressure_air_sea_level") == [
        ("18-21:00", 1011.5, "source:413"),
        ("18-22:00", 1011.0, "source:413"),
        ("18-23:00", 1013.7, "source:413"),
        ("19-00:00", 1015.5, "source:413"),
    ]


def test_api_hourly_precipitation_of_source_412_is_kept_and_says_its_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `FM94_1` precipitation of source 412 is returned beside the METAR's, flagged by its source (GH-3016).

    Rows of GHCNh_USW00003017_2026.psv (Denver, by-year file, read 2026-10-17), 2026-04-02 UTC. Source 412 ("SYNOP/FM12
    or BUFR Surface Land Observations decoded by NOAA/NCEI", 2026 ongoing) files the precipitation of the METAR rows
    of 02:53, 05:53, 08:53, ... (every third hour, `FM94_1`, station `WMO-72565`) in place of the METAR's own (source
    413, `ICAO-KDEN`, which the rows before hold): 2.0 mm at 05:53 and 13.0 mm at 11:53. The documentation gives no
    period for them. The station's own gauge does not agree with them: the GHCN-daily PRCP of USW00003017 is 0.0 for
    2026-04-02 to 2026-04-04, and of the 95 non-zero amounts of source 412 at Denver in 2026, 46 lie in a window of
    three days of which the daily total is 0.0 on each (Chicago O'Hare 25 of 63, Boston 4 of 33, read the same day).
    They are no amount of the hour, and no 3- or 6-hour total that can be told from the file. They are returned as the
    file gives them, and the source code is the only mark of them; whether to null them is open.
    """
    from tests.provider.value_stubs import ghcnh_psv, serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"USW00003017,39.8466,-104.6562,1647.2,CO,DENVER INTERNATIONAL AIRPORT,,,72565,KDEN,US\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]]

    def amount(value: str, source: str, report_type: str, measurement: str | None = None) -> dict[str, str]:
        row = {
            "precipitation": value,
            "precipitation_Report_Type": report_type,
            "precipitation_Source_Code": source,
        }
        if measurement is not None:
            row["precipitation_Measurement_Code"] = measurement
        return row

    rows = [
        ("2026-04-02T00:53:00", amount("2.0", "413", "FM15")),
        ("2026-04-02T01:53:00", amount("0.0", "413", "FM15", "T")),
        ("2026-04-02T02:53:00", amount("0.0", "412", "FM94_1", "T")),
        ("2026-04-02T05:53:00", amount("2.0", "412", "FM94_1")),
        ("2026-04-02T11:53:00", amount("13.0", "412", "FM94_1")),
    ]
    serve(
        monkeypatch,
        api,
        {"ghcnh-station-list": stations, "GHCNh_USW00003017": ghcnh_psv("USW00003017", columns, rows)},
    )
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data", "precipitation_amount_since_last_routine_report")],
        start=dt.datetime(2026, 4, 2, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2026, 4, 3, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    ).filter_by_station_id("USW00003017")
    df = request.values().all().df.sort("timestamp")
    assert [
        (f"{ts:%H:%M}", value, flags)
        for ts, value, flags in df.select("timestamp", "value", "quality_flags").iter_rows()
    ] == [
        ("01:00", 2.0, "source:413"),
        ("02:00", 0.0, "measurement:T,source:413"),
        ("03:00", 0.0, "measurement:T,source:412"),
        ("06:00", 2.0, "source:412"),
        ("12:00", 13.0, "source:412"),
    ]


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
    # the readings of :53 are stamped with the full hour they are nearest to (GH-3000)
    assert got["USW00026451", "wind_speed", "2016-09-04 07:00"] == (4.4, "U")
    assert got["USW00026451", "wind_direction", "2016-09-04 07:00"] == (160.0, "U")
    assert got["USW00026451", "wind_speed", "2006-05-08 09:00"] == (4.0, "P")


def test_api_hourly_measurement_and_source_codes_follow_the_quality_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """The measurement and source codes are the tokens `measurement:` and `source:` after the quality code (GH-2925).

    Rows of the files read on 2026-10-15 (the report type is `SAO` throughout, which nothing reads). The same quality
    code reads differently by source (Table 3 of ghcnh_DOCUMENTATION.pdf): Anchorage (GHCNh_USW00026451_por.psv)
    writes `4` for
    "Passed gross limits check, NCEI" of a temperature of source 335 (1953-11-01 10:00) and "Calculated" of source 223
    (1997-01-31 11:50, stamped 12:00), and ASN00086282 is source 401 with a `0` that Table 3 does not list (1970-06-30
    23:00). The measurement code is a trace of precipitation `T` (Anchorage 1996-07-08 19:00, with the quality code `5`
    of source 335) and the tendency `7` of the 3-hour pressure change, "a decrease" (Antigua 1942-09-01 06:00, -1.4
    hPa). Antigua 1942-01-17 02:00 reads a wind direction of 999 and a speed of 0.0, both with the measurement code C,
    the quality code 1 and source 220: the text of the sentinel stays the last token. CAMU0019904 writes the text
    `Null` for a code it has none of (source 245), which is no code.
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
    assert got["USW00026451", "temperature_air_2m", "1997-01-31 12:00"] == (0.4, "4,source:223")
    assert got["ASN00086282", "temperature_air_2m", "1970-06-30 23:00"] == (10.4, "0,source:401")
    # the measurement code is the trace of a precipitation of 0.0 and the tendency of a pressure change
    assert got["USW00026451", "precipitation_amount_since_last_routine_report", "1996-07-08 19:00"] == (
        0.0,
        "5,measurement:T,source:335",
    )
    assert got["ACM00078861", "pressure_air_site_delta_last_3h", "1942-09-01 06:00"] == (
        -1.4,
        "1,measurement:7,source:220",
    )
    # a calm is the measurement code C; the text of the sentinel is still the last token
    assert got["ACM00078861", "wind_speed", "1942-01-17 02:00"] == (0.0, "1,measurement:C,source:220")
    assert got["ACM00078861", "wind_direction", "1942-01-17 02:00"] == (None, "1,measurement:C,source:220,raw:999")
    # `Null` is the source's way of writing no code: the reading has no flag but the source
    assert got["CAMU0019904", "temperature_air_2m", "1940-01-01 12:00"] == (-28.9, "source:245")


def test_api_hourly_a_value_that_is_no_number_is_null_and_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cell of the file that is a text, not a number, is no reading: null, and the other readings stay (GH-2627).

    The file is read as text and the value was cast to a number by the provider, which raised on the first cell
    that was none and lost the station with it. The core now reads the text as the number it writes and a cell that
    writes none as null, with one debug line for the frame.
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
        2: {"temperature": "n/a", "wind_speed": "2.0"},
        3: {"temperature": "21.5", "wind_speed": "1.0"},
    }
    body = ghcnh_psv("ACM00078861", columns, [(f"1942-01-17T{hour:02d}:00:00", row) for hour, row in rows.items()])
    serve(monkeypatch, api, {"ghcnh-station-list": stations, "GHCNh_ACM00078861": body})
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(1942, 1, 17, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1942, 1, 18, tzinfo=ZoneInfo("UTC")),
        settings=settings,
        options=Options(drop_nulls=False),
    ).filter_by_station_id("ACM00078861")
    df = request.values().all().df
    temperature = df.filter(pl.col("parameter").eq("temperature_air_2m")).sort("timestamp")
    assert temperature.get_column("value").to_list() == [None, 21.5]
    assert df.filter(pl.col("parameter").eq("wind_speed")).get_column("value").drop_nulls().to_list() == [2.0, 1.0]
