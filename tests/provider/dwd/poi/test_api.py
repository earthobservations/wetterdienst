# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the DWD POI (current weather reports) provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.exceptions import NoDataError

from wetterdienst.provider.dwd.poi import DwdPoiMetadata, DwdPoiRequest
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
    request = DwdPoiRequest(parameters=[("hourly", "data", "temperature_air_mean_2m")])
    parameter = next(iter(request.parameters))
    assert parameter.name == "temperature_air_mean_2m"
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
    df = request.values.all().df
    assert not df.is_empty()
    assert set(df.columns) >= {"station_id", "resolution", "dataset", "parameter", "date", "value", "quality"}
    dates = df.get_column("date")
    assert dates.dtype.time_zone == "UTC"
    span = dates.max() - dates.min()
    assert dt.timedelta(hours=1) <= span <= dt.timedelta(hours=48)
    # the newest report is recent, which is the whole point of the network
    assert dt.datetime.now(tz=UTC) - dates.max() < dt.timedelta(hours=12)
    temperature = df.filter(pl.col("parameter") == "temperature_air_mean_2m").drop_nulls("value")
    assert not temperature.is_empty()
    assert temperature.get_column("value").is_between(-40.0, 50.0).all()


@pytest.mark.remote
def test_dwd_poi_values_are_converted_to_the_target_units() -> None:
    """DWD publishes km/h and km; wetterdienst reports m/s and m."""
    request = DwdPoiRequest(parameters=[("hourly", "data", "wind_speed"), ("hourly", "data", "visibility_range")])
    df = request.filter_by_station_id(["10147"]).values.all().df.drop_nulls("value")
    wind = df.filter(pl.col("parameter") == "wind_speed").get_column("value")
    visibility = df.filter(pl.col("parameter") == "visibility_range").get_column("value")
    assert wind.is_between(0.0, 60.0).all()
    # in kilometres this would be at most a two-digit number
    assert visibility.max() > 100.0
