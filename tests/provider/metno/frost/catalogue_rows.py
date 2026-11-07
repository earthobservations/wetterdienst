# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Rows of Frost's station catalogue, as it publishes them, for the tests of what the catalogue makes of them.

The catalogue is two requests (GH-3847, GH-3864): the sources, listed with the closed ones, and the time series Frost
lists for the elements and resolutions the network declares, one row for each series of every station. Both are read
from the real answers of 2026-11-07, cut to the stations that show a rule, with each row as Frost writes it (the
series by their sensor system, `SN99700:0`; no `validTo` where a series is open).

- `SN18700` Oslo - Blindern, in service: the source starts in 1931, its declared series in 1937
- `SN46380`, `SN46530`: names padded with a blank (GH-2654); an element of a resolution the network does not declare
  (`sum(precipitation_amount P6M)`) at the first
- `SN99700` Bjornoya radiosonde station: its daily precipitation begins in 1895, 61 years before its source does, and
  ends in 1956 where the source is open
- `SN18702`: the source ends 1996-10-07, its series 1996-10-31
- `SN74550`: two series that start (1900, 1895) and end (1946-05-31, 07-31) apart, the earlier start before the source
  (1916) and the later end after it (1946-07-01)
- `SN57990`: a closed source (2026-01-01) with series that are open
- `SN12240`, in service: its only declared series ended 2026-08-31, and the series that are open (`air_temperature` at
  10 minutes, which no dataset declares) must not keep it open
- `SN76840`, closed in 1921: its only series is of an element no dataset declares (and from 1961), so the span of the
  source stands
- `SN76999` SCARABEO 8: a rig, no position
- `SN6030`: a series of a station that is no source of the list (58 on 2026-11-07), which is unreachable
"""

from __future__ import annotations

import json
from io import BytesIO

from wetterdienst.util.network import File

SOURCES: dict = {
    "data": [
        {
            "id": "SN18700",
            "name": "OSLO - BLINDERN",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [10.72, 59.9423], "nearest": False},
            "masl": 94,
            "validFrom": "1931-01-01T00:00:00.000Z",
            "county": "OSLO",
        },
        {
            "id": "SN46380",
            "name": "KVANNDALEN ",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [6.9777, 59.6814], "nearest": False},
            "masl": 636,
            "validFrom": "2019-01-01T00:00:00.000Z",
            "county": "ROGALAND",
        },
        {
            "id": "SN46530",
            "name": "VIVASSDALEN ",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [6.9627, 59.9534], "nearest": False},
            "masl": 823,
            "validFrom": "2019-01-01T00:00:00.000Z",
            "county": "VESTLAND",
        },
        {
            "id": "SN99700",
            "name": "BJØRNØYA RADIOSONDESTASJON",
            "countryCode": "SJ",
            "geometry": {"@type": "Point", "coordinates": [18.9977, 74.5033], "nearest": False},
            "masl": 18,
            "validFrom": "1956-09-01T00:00:00.000Z",
            "county": "SVALBARD",
        },
        {
            "id": "SN18702",
            "name": "OSLO - BLINDERN PLU2",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [10.72, 59.9427], "nearest": False},
            "masl": 94,
            "validFrom": "1981-08-04T00:00:00.000Z",
            "validTo": "1996-10-07T00:00:00.000Z",
            "county": "OSLO",
        },
        {
            "id": "SN74550",
            "name": "HÅPNES",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [13.188, 64.9528], "nearest": False},
            "masl": 202,
            "validFrom": "1916-01-01T00:00:00.000Z",
            "validTo": "1946-07-01T00:00:00.000Z",
            "county": "TRØNDELAG",
        },
        {
            "id": "SN57990",
            "name": "GJENGEDAL",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [5.9468, 61.6594], "nearest": False},
            "masl": 230,
            "validFrom": "1972-01-01T00:00:00.000Z",
            "validTo": "2026-01-01T00:00:00.000Z",
            "county": "VESTLAND",
        },
        {
            "id": "SN12240",
            "name": "LØTEN - STENDAMMEN",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [11.5409, 60.7347], "nearest": False},
            "masl": 304,
            "validFrom": "2026-08-24T00:00:00.000Z",
            "county": "INNLANDET",
        },
        {
            "id": "SN76840",
            "name": "HERØYSUNDET",
            "countryCode": "NO",
            "geometry": {"@type": "Point", "coordinates": [12.28, 65.98], "nearest": False},
            "masl": 10,
            "validFrom": "1919-01-01T00:00:00.000Z",
            "validTo": "1921-01-01T00:00:00.000Z",
            "county": "NORDLAND",
        },
        {
            "id": "SN76999",
            "name": "SCARABEO 8",
            "countryCode": "NO",
            "validFrom": "2014-10-29T00:00:00.000Z",
            "county": "KONTINENTALSOKKELEN",
            "geometry": None,
        },
    ]
}

SERIES: dict = {
    "data": [
        {
            "sourceId": "SN18700:0",
            "validFrom": "1937-01-01T00:00:00.000Z",
            "validTo": "1992-01-01T00:00:00.000Z",
            "timeResolution": "P1Y",
            "elementId": "max(air_temperature P1Y)",
        },
        {
            "sourceId": "SN18700:0",
            "validFrom": "1992-12-01T00:00:00.000Z",
            "timeResolution": "PT1H",
            "elementId": "air_temperature",
        },
        {
            "sourceId": "SN18700:0",
            "validFrom": "1937-03-01T00:00:00.000Z",
            "timeResolution": "P1D",
            "elementId": "sum(precipitation_amount P1D)",
        },
        {
            "sourceId": "SN46380:0",
            "validFrom": "2020-12-01T00:00:00.000Z",
            "timeResolution": "P1M",
            "elementId": "mean(air_temperature P1M)",
        },
        {
            "sourceId": "SN46380:0",
            "validFrom": "2020-11-16T00:00:00.000Z",
            "timeResolution": "P1D",
            "elementId": "mean(air_temperature P1D)",
        },
        {
            "sourceId": "SN46380:0",
            "validFrom": "2020-12-01T00:00:00.000Z",
            "timeResolution": "P6M",
            "elementId": "sum(precipitation_amount P6M)",
        },
        {
            "sourceId": "SN46530:0",
            "validFrom": "2020-11-15T00:00:00.000Z",
            "timeResolution": "PT1H",
            "elementId": "air_temperature",
        },
        {
            "sourceId": "SN46530:0",
            "validFrom": "2022-02-28T00:00:00.000Z",
            "validTo": "2022-11-01T00:00:00.000Z",
            "timeResolution": "PT1H",
            "elementId": "relative_humidity",
        },
        {
            "sourceId": "SN99700:0",
            "validFrom": "1895-07-07T00:00:00.000Z",
            "validTo": "1956-12-31T00:00:00.000Z",
            "timeResolution": "P1D",
            "elementId": "sum(precipitation_amount P1D)",
        },
        {
            "sourceId": "SN99700:0",
            "validFrom": "1895-07-07T00:00:00.000Z",
            "validTo": "1956-12-31T00:00:00.000Z",
            "timeResolution": "P1D",
            "elementId": "over_time(weather_class1_primary_significance P1D)",
        },
        {
            "sourceId": "SN18702:0",
            "validFrom": "1981-08-14T00:00:00.000Z",
            "validTo": "1996-10-31T00:00:00.000Z",
            "timeResolution": "PT1H",
            "elementId": "sum(precipitation_amount PT1H)",
        },
        {
            "sourceId": "SN18702:0",
            "validFrom": "1981-08-04T00:00:00.000Z",
            "validTo": "1996-10-31T00:00:00.000Z",
            "timeResolution": "PT1M",
            "elementId": "sum(precipitation_amount PT1M)",
        },
        {
            "sourceId": "SN74550:0",
            "validFrom": "1900-01-01T00:00:00.000Z",
            "validTo": "1946-05-31T00:00:00.000Z",
            "timeResolution": "P1Y",
            "elementId": "sum(precipitation_amount P1Y)",
        },
        {
            "sourceId": "SN74550:0",
            "validFrom": "1895-07-01T00:00:00.000Z",
            "validTo": "1946-07-31T00:00:00.000Z",
            "timeResolution": "P1M",
            "elementId": "sum(precipitation_amount P1M)",
        },
        {
            "sourceId": "SN57990:0",
            "validFrom": "1972-09-01T00:00:00.000Z",
            "timeResolution": "P1M",
            "elementId": "mean(surface_snow_thickness P1M)",
        },
        {
            "sourceId": "SN57990:0",
            "validFrom": "1972-09-01T00:00:00.000Z",
            "timeResolution": "P1M",
            "elementId": "sum(precipitation_amount P1M)",
        },
        {
            "sourceId": "SN57990:0",
            "validFrom": "1972-09-01T00:00:00.000Z",
            "validTo": "2025-12-31T00:00:00.000Z",
            "timeResolution": "P1D",
            "elementId": "sum(precipitation_amount P1D)",
        },
        {
            "sourceId": "SN57990:0",
            "validFrom": "1972-09-01T00:00:00.000Z",
            "validTo": "2024-02-29T00:00:00.000Z",
            "timeResolution": "PT6H",
            "elementId": "over_time(weather_class1_tertiary_significance PT6H)",
        },
        {
            "sourceId": "SN12240:0",
            "validFrom": "2026-08-26T00:00:00.000Z",
            "validTo": "2026-08-31T00:00:00.000Z",
            "timeResolution": "PT10M",
            "elementId": "sum(precipitation_amount PT10M)",
        },
        {
            "sourceId": "SN12240:0",
            "validFrom": "2026-08-26T00:00:00.000Z",
            "timeResolution": "PT10M",
            "elementId": "air_temperature",
        },
        {
            "sourceId": "SN12240:0",
            "validFrom": "2026-08-26T00:00:00.000Z",
            "timeResolution": "PT10M",
            "elementId": "weather_type_automatic",
        },
        {
            "sourceId": "SN76840:0",
            "validFrom": "1961-01-01T00:00:00.000Z",
            "validTo": "2006-12-31T00:00:00.000Z",
            "timeResolution": "P1M",
            "elementId": "integral_of_deficit_interpolated(mean(air_temperature P1D) P1M 17.0)",
        },
        {
            "sourceId": "SN76999:0",
            "validFrom": "2016-08-05T00:00:00.000Z",
            "validTo": "2019-06-30T00:00:00.000Z",
            "timeResolution": "P1D",
            "elementId": "mean(wind_speed P1D)",
        },
        {
            "sourceId": "SN76999:0",
            "validFrom": "2017-08-01T00:00:00.000Z",
            "validTo": "2019-06-30T00:00:00.000Z",
            "timeResolution": "P1M",
            "elementId": "mean(relative_humidity P1M)",
        },
        {
            "sourceId": "SN6030:0",
            "validFrom": "2015-08-01T00:00:00.000Z",
            "validTo": "2015-08-31T00:00:00.000Z",
            "timeResolution": "P1M",
            "elementId": "max(air_temperature P1M)",
        },
    ]
}

# what the catalogue must make of each source: (start, end), the end `None` where a declared series is open or the
# source has none. The reasons are the ones of the docstring above
EXPECTED: dict[str, tuple[str, str | None]] = {
    "SN18700": ("1931-01-01", None),
    "SN46380": ("2019-01-01", None),
    "SN46530": ("2019-01-01", None),
    "SN99700": ("1895-07-07", "1956-12-31"),
    "SN18702": ("1981-08-04", "1996-10-31"),
    "SN74550": ("1895-07-01", "1946-07-31"),
    "SN57990": ("1972-01-01", None),
    "SN12240": ("2026-08-24", "2026-08-31"),
    "SN76840": ("1919-01-01", "1921-01-01"),
    "SN76999": ("2014-10-29", "2019-06-30"),
}


def is_series_listing(url: str) -> bool:
    """Say whether a URL is the catalogue's request for the declared series of every station."""
    return "/observations/availableTimeSeries/" in url and "fields=sourceId" in url


def is_sources_listing(url: str) -> bool:
    """Say whether a URL is the catalogue's request for the sources."""
    return "/sources/v0.jsonld" in url and "validtime=" in url


def ok(url: str, payload: dict) -> File:
    """Give a payload as `download_file` hands back an answer of 200."""
    return File(url=url, content=BytesIO(json.dumps(payload).encode()), status=200)


def series_of(station: str) -> dict:
    """Give the series listing of one station, as the rows of Oslo - Blindern under the id of that station.

    For a test of the values, which needs the catalogue of the one station it reads: the first series start in 1937,
    where the source stub of `test_values_failures.py` does, so the span of the station is the source's own.
    """
    return {"data": [{**row, "sourceId": f"{station}:0"} for row in SERIES["data"][:3]]}
