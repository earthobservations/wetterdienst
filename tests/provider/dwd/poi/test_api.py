# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the DWD POI (current weather reports) provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.exceptions import NoDataError

from tests.provider.value_stubs import serve, stations_result
from wetterdienst import Options, Settings
from wetterdienst.exceptions import InvalidParameterError
from wetterdienst.provider.dwd.poi import DwdPoiMetadata, DwdPoiRequest
from wetterdienst.provider.dwd.poi import api as dwd_poi_api
from wetterdienst.provider.dwd.poi.api import _read_poi_csv, _station_file_url, _station_id_from_file_name

UTC = ZoneInfo("UTC")

# a file as DWD serves it: English names, units, German descriptions, then the reports, newest first
POI_CSV = (
    "surface observations;Parameter description;cloud_cover_total;dry_bulb_temperature_at_2_meter_above_ground;"
    "present_weather\n"
    "10147;Unit;%;Grad C;CODE_TABLE\n"
    "Datum;Uhrzeit (UTC);Wolkenbedeckung;Temperatur (2m);aktuelles Wetter\n"
    "31.08.26;20:00;100;15,3;8\n"
    "31.08.26;19:00;---;15,4;2\n"
).encode("latin-1")


def test_station_file_url_pads_the_station_id() -> None:
    """DWD names the files after the station id padded out to five characters."""
    assert _station_file_url("10147").endswith("/10147-BEOB.csv")
    assert _station_file_url("A191").endswith("/A191_-BEOB.csv")


def test_station_id_from_file_name_strips_the_padding() -> None:
    """The station id reported is the catalogue's, so that it matches dwd/mosmix."""
    assert _station_id_from_file_name("10147-BEOB.csv") == "10147"
    assert _station_id_from_file_name("A191_-BEOB.csv") == "A191"


def test_read_poi_csv_drops_the_unit_and_description_lines() -> None:
    """Only the first of the three header lines is a header; the other two are not data."""
    df = _read_poi_csv(POI_CSV)
    assert df.columns == [
        "surface observations",
        "Parameter description",
        "cloud_cover_total",
        "dry_bulb_temperature_at_2_meter_above_ground",
        "present_weather",
    ]
    assert df.height == 2
    assert df["dry_bulb_temperature_at_2_meter_above_ground"].to_list() == ["15,3", "15,4"]


def test_read_poi_csv_decodes_latin1() -> None:
    """The German description line carries umlauts and is latin-1, which utf-8 would reject."""
    csv = POI_CSV.replace(b"Wolkenbedeckung", b"Wolkenh\xf6he")
    assert _read_poi_csv(csv).height == 2


def test_read_poi_csv_of_an_empty_file() -> None:
    """Polars raises on empty bytes, so the values path guards on ``File.is_empty`` before parsing.

    DWD rewrites every station file each hour, and a rewrite in progress can be served as an empty
    200; without the guard one such file would abort a whole multi-station query.
    """
    with pytest.raises(NoDataError):
        _read_poi_csv(b"")


def test_metadata_is_hourly_and_now() -> None:
    """POI serves the last day of hourly reports, which is the ``now`` period."""
    resolution = DwdPoiMetadata[0]
    assert resolution.name == "hourly"
    assert [period.value for period in resolution.periods] == ["now"]
    assert len(resolution.datasets[0].parameters) == 39


def test_parameters_are_addressable() -> None:
    """A single parameter resolves through the public API."""
    request = DwdPoiRequest(parameters=[("hourly", "data", "temperature_air_2m")])
    parameter = next(iter(request.parameters))
    assert parameter.name == "temperature_air_2m"
    assert parameter.name_original == "dry_bulb_temperature_at_2_meter_above_ground"


# ---------------------------------------------------------------------------
# Remote tests -- hit the live DWD opendata server. POI only serves the last day, so the values are
# whatever the weather was; assert structure and ranges rather than numbers. Not xfail-guarded: DWD
# opendata is the project's primary source, and a guard would turn a renamed column or a moved
# endpoint into a silent pass.
# ---------------------------------------------------------------------------


@pytest.mark.remote
def test_dwd_poi_stations() -> None:
    """The station list is the MOSMIX catalogue narrowed to the stations that have a POI file."""
    request = DwdPoiRequest(parameters=[("hourly", "data")])
    df = request.all().df
    assert not df.is_empty()
    # ~970 of the catalogue's ~5600 stations report; the catalogue itself is far larger
    assert 500 < df.height < 2000
    hamburg = df.filter(pl.col("station_id") == "10147")
    # the catalogue truncates names to its 19-character column ("HAMBURG-FU." here)
    assert hamburg.get_column("name").item().startswith("HAMBURG")
    assert hamburg.get_column("latitude").item() == pytest.approx(53.63, abs=0.1)
    assert hamburg.get_column("longitude").item() == pytest.approx(9.99, abs=0.1)


@pytest.mark.remote
def test_dwd_poi_values() -> None:
    """A station's reports come back hourly, in UTC, for roughly the last day."""
    request = DwdPoiRequest(parameters=[("hourly", "data")]).filter_by_station_id(["10147"])
    df = request.values().all().df
    assert not df.is_empty()
    assert set(df.columns) >= {
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "timestamp",
        "value",
        "quality_flags",
    }
    dates = df.get_column("timestamp")
    assert dates.dtype.time_zone == "UTC"
    span = dates.max() - dates.min()
    assert dt.timedelta(hours=1) <= span <= dt.timedelta(hours=48)
    # the newest report is recent, which is the whole point of the network
    assert dt.datetime.now(tz=UTC) - dates.max() < dt.timedelta(hours=12)
    temperature = df.filter(pl.col("parameter") == "temperature_air_2m").drop_nulls("value")
    assert not temperature.is_empty()
    assert temperature.get_column("value").is_between(-40.0, 50.0).all()


@pytest.mark.remote
def test_dwd_poi_values_are_converted_to_the_target_units() -> None:
    """DWD publishes km/h and km; wetterdienst reports m/s and m."""
    request = DwdPoiRequest(
        parameters=[("hourly", "data", "wind_speed_mean_last_10min"), ("hourly", "data", "visibility")]
    )
    df = request.filter_by_station_id(["10147"]).values().all().df.drop_nulls("value")
    wind = df.filter(pl.col("parameter") == "wind_speed_mean_last_10min").get_column("value")
    visibility = df.filter(pl.col("parameter") == "visibility").get_column("value")
    assert wind.is_between(0.0, 60.0).all()
    # in kilometres this would be at most a two-digit number
    assert visibility.max() > 100.0


def test_dwd_poi_wind_direction_of_0_is_null_calm_or_variable_and_360_is_north(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a direction of 0 is null with `raw:0` whatever the speed beside it, and 360 stays (GH-2794).

    Rows of the files of 2026-10-12, put into one file: 01008 11.10.26 22:00 has a direction of 0 beside 0 km/h
    (a calm), 03066 12.10.26 01:00 one of 0 beside 4 km/h (no direction, probably variable: 184 of the 346 reports
    with a 0 and a speed above 0 have 4 km/h), 02186 12.10.26 06:00 one of 360 beside 11 km/h. North is 360 in these
    files (141 reports of 11,364, as many as 10), so a 0 is no bearing. A speed of 0 is a reading.
    """
    wind = "mean_wind_direction_during_last_10 min_at_10_meters_above_ground"
    speed = "mean_wind_speed_during last_10_min_at_10_meters_above_ground"
    csv = (
        f"surface observations;Parameter description;{wind};{speed}\n"
        "10147;Unit;Grad;km/h\n"
        "Datum;Uhrzeit (UTC);Windrichtung;Windgeschwindigkeit\n"
        "12.10.26;06:00;360;11\n"
        "12.10.26;01:00;0;4\n"
        "11.10.26;22:00;0;0\n"
    ).encode("latin-1")
    serve(monkeypatch, dwd_poi_api, {"10147-BEOB.csv": csv})
    request = DwdPoiRequest(
        parameters=[
            ("hourly", "data", "wind_direction_mean_last_10min"),
            ("hourly", "data", "wind_speed_mean_last_10min"),
        ],
        start=dt.datetime(2026, 10, 11, tzinfo=UTC),
        end=dt.datetime(2026, 10, 13, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    df = stations_result(request, "hourly", "data", "10147").values().all().df
    df = df.sort("timestamp")
    direction = df.filter(pl.col("parameter") == "wind_direction_mean_last_10min")
    assert direction.select("value", "quality_flags").rows() == [(None, "raw:0"), (None, "raw:0"), (360.0, None)]
    speeds = df.filter(pl.col("parameter") == "wind_speed_mean_last_10min")
    assert speeds.select("value", "quality_flags").rows() == [(0.0, None), (1.1111, None), (3.0556, None)]


def test_dwd_poi_maximum_wind_of_the_previous_day_is_the_maximum_of_the_last_6_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that DWD's "previous day" wind maximum is the maximum of the 6 hourly values up to the stamp (GH-2817).

    Rows of 10637-BEOB.csv (Frankfurt), read 2026-10-15 20:29 UTC: the column
    `maximum_of_10_minutes_mean_of_wind_speed_for_previous_day` ("Maximalwind (vergangener Tag)") holds a value at
    00, 06, 12 and 18 UTC only. The 12:00 value of 12 km/h is the maximum of the hourly
    `maximum_wind_speed_as_10_minutes_mean_during_last_hour` stamped 07:00 to 12:00 (4, 5, 6, 9, 9, 12), the report's
    own row included: the six values stamped 06:00 to 11:00 have a maximum of 9. The 18:00 value of 13 is that of
    13:00 to 18:00 (13, 13, 11, 8, 7, 3), which is not the day's maximum either.
    """
    previous_day = "maximum_of_10_minutes_mean_of_wind_speed_for_previous_day"
    last_hour = "maximum_wind_speed_as_10_minutes_mean_during_last_hour"
    hourly = {18: 3, 17: 7, 16: 8, 15: 11, 14: 13, 13: 13, 12: 12, 11: 9, 10: 9, 9: 6, 8: 5, 7: 4}
    previous = {18: "13", 12: "12"}
    rows = "".join(f"15.10.26;{hour:02d}:00;{previous.get(hour, '---')};{value}\n" for hour, value in hourly.items())
    csv = (
        f"surface observations;Parameter description;{previous_day};{last_hour}\n"
        "10637;Unit;km/h;km/h\n"
        "Datum;Uhrzeit (UTC);Maximalwind (vergangener Tag);Maximalwind (letzte Stunde)\n" + rows
    ).encode("latin-1")
    serve(monkeypatch, dwd_poi_api, {"10637-BEOB.csv": csv})
    request = DwdPoiRequest(
        parameters=[("hourly", "data", "wind_speed_rolling_mean_max_last_6h")],
        start=dt.datetime(2026, 10, 15, tzinfo=UTC),
        end=dt.datetime(2026, 10, 16, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=True),
    )
    df = stations_result(request, "hourly", "data", "10637").values().all().df.sort("timestamp")
    reported = {stamp.hour: value for stamp, value in df.select("timestamp", "value").rows()}
    # km/h as m/s; the stamp's own hour is one of the 6 (06:00 to 11:00 alone would give 9 km/h at 12:00)
    assert reported == {hour: round(max(hourly[h] for h in range(hour - 5, hour + 1)) / 3.6, 4) for hour in (12, 18)}
    assert reported == {12: 3.3333, 18: 3.6111}

    # the old name is not accepted and says what to use instead
    with pytest.raises(InvalidParameterError, match="wind_speed_rolling_mean_max_last_6h"):
        DwdPoiRequest(parameters=[("hourly", "data", "wind_speed_rolling_mean_max_yesterday")])
