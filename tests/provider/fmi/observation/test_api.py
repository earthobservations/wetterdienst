# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for FMI observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.fmi.observation import FmiObservationRequest
from wetterdienst.provider.fmi.observation.parser import (
    extract_exception_text,
    parse_fmi_observations,
    parse_fmi_stations,
)

HELSINKI_KAISANIEMI = "100971"
UTC = ZoneInfo("UTC")

# FMI's open-data WFS is a live third-party service; xfail rather than a hard failure keeps a
# transient blip from blocking CI/merges, matching the AEMET/SMHI precedent.
xfail_if_fmi_unavailable = pytest.mark.xfail(strict=False, reason="FMI server intermittently unavailable")


def test_parse_fmi_observations_trace_sentinel() -> None:
    """FMI's -1 'no precipitation/no snow' sentinel is normalised to 0.0, other values untouched."""
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <wfs:FeatureCollection
        xmlns:wfs="http://www.opengis.net/wfs/2.0"
        xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">
      <wfs:member>
        <BsWfs:BsWfsElement>
          <BsWfs:Time>2024-01-01T00:00:00Z</BsWfs:Time>
          <BsWfs:ParameterName>rrday</BsWfs:ParameterName>
          <BsWfs:ParameterValue>-1.0</BsWfs:ParameterValue>
        </BsWfs:BsWfsElement>
      </wfs:member>
      <wfs:member>
        <BsWfs:BsWfsElement>
          <BsWfs:Time>2024-01-01T00:00:00Z</BsWfs:Time>
          <BsWfs:ParameterName>snow</BsWfs:ParameterName>
          <BsWfs:ParameterValue>-1.0</BsWfs:ParameterValue>
        </BsWfs:BsWfsElement>
      </wfs:member>
      <wfs:member>
        <BsWfs:BsWfsElement>
          <BsWfs:Time>2024-01-01T00:00:00Z</BsWfs:Time>
          <BsWfs:ParameterName>tday</BsWfs:ParameterName>
          <BsWfs:ParameterValue>-1.0</BsWfs:ParameterValue>
        </BsWfs:BsWfsElement>
      </wfs:member>
      <wfs:member>
        <BsWfs:BsWfsElement>
          <BsWfs:Time>2024-01-01T00:00:00Z</BsWfs:Time>
          <BsWfs:ParameterName>rrday</BsWfs:ParameterName>
          <BsWfs:ParameterValue>NaN</BsWfs:ParameterValue>
        </BsWfs:BsWfsElement>
      </wfs:member>
    </wfs:FeatureCollection>"""
    df = parse_fmi_observations(content)
    values = {(row["parameter"], row["value"]) for row in df.select("parameter", "value").to_dicts()}
    # -1 sentinel -> 0.0 for precipitation and snow depth
    assert ("rrday", 0.0) in values
    assert ("snow", 0.0) in values
    # -1 is a real reading for temperature and must be preserved
    assert ("tday", -1.0) in values
    # NaN stays null and is never coerced to 0.0
    assert ("rrday", None) in values


def test_extract_exception_text() -> None:
    """An OWS ExceptionReport is detected and its text extracted; a normal response returns None."""
    exception = b"""<?xml version="1.0" encoding="UTF-8"?>
    <ExceptionReport xmlns="http://www.opengis.net/ows/1.1" version="2.0.0">
      <Exception exceptionCode="InvalidParameterValue" locator="fmisid">
        <ExceptionText>No locations found for the query.</ExceptionText>
      </Exception>
    </ExceptionReport>"""
    assert extract_exception_text(exception) == "No locations found for the query."
    empty = b"""<?xml version="1.0" encoding="UTF-8"?>
    <wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" numberReturned="0"/>"""
    assert extract_exception_text(empty) is None


def test_parse_fmi_stations_active_station_end_date_null() -> None:
    """A trailing concrete endPosition does not override an active station's null end_date."""
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <wfs:FeatureCollection
        xmlns:wfs="http://www.opengis.net/wfs/2.0"
        xmlns:gml="http://www.opengis.net/gml/3.2"
        xmlns:ef="http://inspire.ec.europa.eu/schemas/ef/4.0">
      <wfs:member>
        <ef:EnvironmentalMonitoringFacility>
          <gml:identifier codeSpace="http://xml.fmi.fi/namespace/stationcode/fmisid">100971</gml:identifier>
          <gml:name codeSpace="http://xml.fmi.fi/namespace/locationcode/name">Helsinki Kaisaniemi</gml:name>
          <gml:name codeSpace="http://xml.fmi.fi/namespace/location/region">Helsinki</gml:name>
          <gml:pos>60.17523 24.94459</gml:pos>
          <ef:operationalActivityPeriod>
            <gml:TimePeriod>
              <gml:beginPosition>1844-01-01T00:00:00Z</gml:beginPosition>
              <gml:endPosition indeterminatePosition="now"/>
            </gml:TimePeriod>
          </ef:operationalActivityPeriod>
          <gml:TimePeriod>
            <gml:beginPosition>2000-01-01T00:00:00Z</gml:beginPosition>
            <gml:endPosition>2020-01-01T00:00:00Z</gml:endPosition>
          </gml:TimePeriod>
        </ef:EnvironmentalMonitoringFacility>
      </wfs:member>
    </wfs:FeatureCollection>"""
    df = parse_fmi_stations(content)
    assert df.height == 1
    row = df.to_dicts()[0]
    assert row["station_id"] == "100971"
    assert row["start_date"] == dt.datetime(1844, 1, 1, tzinfo=UTC)
    # active station: the indeterminate operational endPosition wins over the later concrete one
    assert row["end_date"] is None


@pytest.mark.remote
@xfail_if_fmi_unavailable
def test_fmi_observation_stations() -> None:
    """Station metadata for Helsinki Kaisaniemi matches the FMI station catalogue."""
    request = FmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id(HELSINKI_KAISANIEMI)
    df = request.df
    assert df.select(pl.exclude("latitude", "longitude", "start_date", "end_date", "height")).to_dicts() == [
        {
            "resolution": "hourly",
            "dataset": "data",
            "station_id": HELSINKI_KAISANIEMI,
            "name": "Helsinki Kaisaniemi",
            "state": "Helsinki",
        },
    ]
    # assert coordinates with a tolerance -- FMI may adjust these slightly over time
    assert df["latitude"].item() == pytest.approx(60.17523)
    assert df["longitude"].item() == pytest.approx(24.94459)


@pytest.mark.remote
@xfail_if_fmi_unavailable
def test_fmi_observation_values_hourly() -> None:
    """Hourly values at Helsinki Kaisaniemi for 2024-01-01 00:00 match the FMI reference values."""
    df = (
        FmiObservationRequest(
            parameters=[("hourly", "data")],
            start_date=dt.datetime(2024, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2024, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(HELSINKI_KAISANIEMI)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [HELSINKI_KAISANIEMI]
    assert df["resolution"].unique().to_list() == ["hourly"]

    def value_at(parameter: str, hour: int) -> float:
        date = dt.datetime(2024, 1, 1, hour, tzinfo=UTC)
        return df.filter(pl.col("parameter").eq(parameter), pl.col("date").eq(date)).get_column("value").item()

    assert value_at("temperature_air_mean_2m", 0) == pytest.approx(-14.6)
    assert value_at("temperature_dew_point_mean_2m", 0) == pytest.approx(-16.6)
    assert value_at("wind_speed", 0) == pytest.approx(2.7)
    assert value_at("wind_gust_max", 0) == pytest.approx(5.0)
    assert value_at("wind_direction", 0) == pytest.approx(36.0)
    assert value_at("precipitation_height", 0) == pytest.approx(0.0)
    # humidity is reported by FMI as percent, wetterdienst stores it as fraction
    assert value_at("humidity", 0) == pytest.approx(0.84)
    assert value_at("pressure_air_sea_level", 0) == pytest.approx(1020.1)
    assert value_at("visibility_range", 0) == pytest.approx(10730.0)


@pytest.mark.remote
@xfail_if_fmi_unavailable
def test_fmi_observation_values_daily() -> None:
    """Daily values at Helsinki Kaisaniemi for 2024-01-01 match the FMI reference values."""
    df = (
        FmiObservationRequest(
            parameters=[("daily", "data")],
            start_date=dt.datetime(2024, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2024, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(HELSINKI_KAISANIEMI)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [HELSINKI_KAISANIEMI]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["date"].unique().to_list() == [dt.datetime(2024, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(-15.8)
    assert value_of("temperature_air_max_2m") == pytest.approx(-13.7)
    assert value_of("temperature_air_min_2m") == pytest.approx(-17.4)
