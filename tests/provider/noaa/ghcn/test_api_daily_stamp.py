# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the stamp of NOAA GHCN daily values."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import serve
from wetterdienst import Options, Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest, api

# Rows of the per-station files at ncei.noaa.gov/data/global-historical-climatology-network-daily/access/ as NOAA writes
# them (values in tenths of a degree, attributes after each); a column the station never reports is left out.
_TOKYO = (
    '"STATION","DATE","LATITUDE","LONGITUDE","ELEVATION","NAME","PRCP","PRCP_ATTRIBUTES","TMAX","TMAX_ATTRIBUTES"\n'
    '"JA000047662","1951-01-01","35.683","139.767","36.0","TOKYO, JA","    0",",,I","   70",",,I"\n'
    '"JA000047662","1951-01-02","35.683","139.767","36.0","TOKYO, JA","    0",",,I","   82",",,I"\n'
    '"JA000047662","1951-01-03","35.683","139.767","36.0","TOKYO, JA","    0",",,I","   81",",,I"\n'
)
_NEW_YORK = (
    '"STATION","DATE","LATITUDE","LONGITUDE","ELEVATION","NAME","PRCP","PRCP_ATTRIBUTES","TMAX","TMAX_ATTRIBUTES"\n'
    '"USW00094728","1869-01-01","40.77898","-73.96925","42.7",'
    '"NY CITY CENTRAL PARK, NY US","  191",",,Z,","  -17",",,Z"\n'
    '"USW00094728","1869-01-02","40.77898","-73.96925","42.7",'
    '"NY CITY CENTRAL PARK, NY US","    8",",,Z,null","  -28",",,Z"\n'
    '"USW00094728","1869-01-03","40.77898","-73.96925","42.7",'
    '"NY CITY CENTRAL PARK, NY US","    0","T,,Z,null","   17",",,Z"\n'
)
_STATIONS = (
    "JA000047662  35.6830  139.7670   36.0    TOKYO                                  47662\n"
    "USW00094728  40.7789  -73.9692   42.7 NY NY CITY CNTRL PARK                 HCN 72506\n"
)
_INVENTORY = "JA000047662  35.6830  139.7670 TMAX 1951 2025\nUSW00094728  40.7789  -73.9692 TMAX 1869 2025\n"


@pytest.mark.parametrize(
    ("station_id", "day", "expected"),
    [
        ("JA000047662", "1951-01-02", 8.2),  # east of Greenwich: local standard midnight was 15:00 UTC the day before
        ("USW00094728", "1869-01-02", -2.8),  # west of it: 05:00 UTC
    ],
    ids=["tokyo", "new-york"],
)
def test_ghcn_daily_is_stamped_at_00_utc_of_its_date(
    monkeypatch: pytest.MonkeyPatch, station_id: str, day: str, expected: float
) -> None:
    """Test that a daily value is stamped at 00:00 UTC of its DATE, so a request for that one day returns it.

    The stamp was local standard midnight in UTC (Tokyo 15:00 UTC of the day before, New York 05:00 UTC), and a
    request with start=end=day, whose bounds are 00:00 UTC, returned nothing for either station (GH-2683).
    """
    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": _STATIONS.encode("utf8"),
            "ghcnd-inventory": _INVENTORY.encode("utf8"),
            "access/JA000047662": _TOKYO.encode("utf8"),
            "access/USW00094728": _NEW_YORK.encode("utf8"),
        },
    )
    settings = Settings(cache_disable=True)
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "temperature_air_max_2m")], start=day, end=day, settings=settings
    ).filter_by_station_id(station_id)
    df = request.values().all().df
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("UTC"))
    assert df.get_column("timestamp").to_list() == [midnight]
    assert df.get_column("value").to_list() == pytest.approx([expected])
    # and a window of three days holds one value per date, every one at 00:00 UTC
    wide = NoaaGhcnRequest(
        parameters=[("daily", "data", "temperature_air_max_2m")],
        start=midnight - dt.timedelta(days=1),
        end=midnight + dt.timedelta(days=1),
        settings=settings,
    ).filter_by_station_id(station_id)
    assert wide.values().all().df.get_column("timestamp").sort().to_list() == [
        midnight - dt.timedelta(days=1),
        midnight,
        midnight + dt.timedelta(days=1),
    ]


# The attributes are "MFLAG,QFLAG,SFLAG" (ghcn/daily/readme.txt), PRCP, SNOW and SNWD with the observation time as a
# fourth field. QFLAG: "Blank = did not fail any quality assurance check", otherwise the check the value failed,
# "X = failed bounds check", "G = failed gap check", "I = failed internal consistency check", ... MFLAG: "Blank = no
# measurement information applicable", "T = trace of precipitation, snowfall, or snow depth", "H = for TMAX/TMIN/TAVG
# represents highest or lowest hourly temperature". SFLAG: "0 = U.S. Cooperative Summary of the Day (NCDC DSI-3200)",
# "7 = U.S. Cooperative Summary of the Day -- Transmitted via WxCoder3 (NCDC DSI-3207)", "S = Global Summary of the
# Day". The rows are made up from the combinations USW00094728 shows in the live file (checked 2026-10-12: `,,0`,
# `T,,0,2400`, `,I,Z`, `,,X`, ...).
_FLAGGED = (
    '"STATION","DATE","LATITUDE","LONGITUDE","ELEVATION","NAME","PRCP","PRCP_ATTRIBUTES","TMAX","TMAX_ATTRIBUTES"\n'
    '"USW00094728","2000-01-01","40.77898","-73.96925","42.7","NY CITY, NY US","    0",",,0","   61",",,0"\n'
    '"USW00094728","2000-01-02","40.77898","-73.96925","42.7","NY CITY, NY US","  250","T,X,0","  -28",",G,7"\n'
    '"USW00094728","2000-01-03","40.77898","-73.96925","42.7","NY CITY, NY US",,,"   17","H,,S"\n'
)


def test_ghcn_daily_returns_the_flags_of_each_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a value's flags come back as `QFLAG,measurement:MFLAG,source:SFLAG` in `quality_flags` (GH-2758).

    The attributes were dropped with the other columns the value did not need, so a value that failed the bounds or
    the gap check came back as any other. The quality flag is the plain token and comes first, the measurement and the
    source flag follow with their kind; a blank flag is left out and a value with no attributes at all is null.
    """
    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": _STATIONS.encode("utf8"),
            "ghcnd-inventory": _INVENTORY.encode("utf8"),
            "access/USW00094728": _FLAGGED.encode("utf8"),
        },
    )
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "precipitation_amount"), ("daily", "data", "temperature_air_max_2m")],
        start="2000-01-01",
        end="2000-01-03",
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    ).filter_by_station_id("USW00094728")
    df = request.values().all().df.sort("parameter", "timestamp")
    assert df.schema["quality_flags"] == pl.String
    assert "quality" not in df.columns
    assert "quality_flag" not in df.columns
    assert df.select("parameter", "quality_flags").rows() == [
        ("precipitation_amount", "source:0"),
        ("precipitation_amount", "X,measurement:T,source:0"),
        ("precipitation_amount", None),
        ("temperature_air_max_2m", "source:0"),
        ("temperature_air_max_2m", "G,source:7"),
        ("temperature_air_max_2m", "measurement:H,source:S"),
    ]
