# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the stamp of NOAA GHCN daily values."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import ghcnd_by_station, serve
from wetterdienst import Options, Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest, api

# Rows of the per-station files of the AWS bucket (noaa-ghcn-pds, `csv.gz/by_station/<id>.csv.gz`) as NOAA writes them:
# one row for each reading, the value in tenths of a degree or of a millimetre; a reading that is missing has no row.
_TOKYO = ghcnd_by_station(
    [
        ("JA000047662", "19510101", "PRCP", "0", "", "", "I"),
        ("JA000047662", "19510101", "TMAX", "70", "", "", "I"),
        ("JA000047662", "19510102", "PRCP", "0", "", "", "I"),
        ("JA000047662", "19510102", "TMAX", "82", "", "", "I"),
        ("JA000047662", "19510103", "PRCP", "0", "", "", "I"),
        ("JA000047662", "19510103", "TMAX", "81", "", "", "I"),
    ]
)
_NEW_YORK = ghcnd_by_station(
    [
        ("USW00094728", "18690101", "PRCP", "191", "", "", "Z"),
        ("USW00094728", "18690101", "TMAX", "-17", "", "", "Z"),
        ("USW00094728", "18690102", "PRCP", "8", "", "", "Z"),
        ("USW00094728", "18690102", "TMAX", "-28", "", "", "Z"),
        ("USW00094728", "18690103", "PRCP", "0", "T", "", "Z"),
        ("USW00094728", "18690103", "TMAX", "17", "", "", "Z"),
    ]
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
            "by_station/JA000047662": _TOKYO,
            "by_station/USW00094728": _NEW_YORK,
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


# The attributes are the columns M_FLAG, Q_FLAG and S_FLAG (ghcn/daily/readme.txt; the bucket adds OBS_TIME, set on
# some elements only: PRCP, TMAX, TMIN and TOBS in the NYC file, not SNOW). QFLAG: "Blank = did not fail any quality
# assurance check", otherwise the check the value failed, "X = failed bounds check", "G = failed gap check", "I =
# failed internal consistency check", ... MFLAG: "Blank = no measurement information applicable", "T = trace of
# precipitation, snowfall, or snow depth", "H = for TMAX/TMIN/TAVG
# represents highest or lowest hourly temperature". SFLAG: "0 = U.S. Cooperative Summary of the Day (NCDC DSI-3200)",
# "7 = U.S. Cooperative Summary of the Day -- Transmitted via WxCoder3 (NCDC DSI-3207)", "S = Global Summary of the
# Day". The rows are made up from the combinations USW00094728 shows in the live file (checked 2026-10-12: `,,0`,
# `T,,0,2400`, `,I,Z`, `,,X`, ...).
_FLAGGED = ghcnd_by_station(
    [
        ("USW00094728", "20000101", "PRCP", "0", "", "", "0"),
        ("USW00094728", "20000101", "TMAX", "61", "", "", "0"),
        ("USW00094728", "20000102", "PRCP", "250", "T", "X", "0"),
        ("USW00094728", "20000102", "TMAX", "-28", "", "G", "7"),
        # no PRCP on the third day: the file has no row for a missing reading, the reader returns it as a null
        ("USW00094728", "20000103", "TMAX", "17", "H", "", "S"),
    ]
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
            "by_station/USW00094728": _FLAGGED,
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
        ("precipitation_amount", "X,measurement:T,source:0,suspect:source"),
        ("precipitation_amount", None),
        ("temperature_air_max_2m", "source:0"),
        ("temperature_air_max_2m", "G,source:7,suspect:source"),
        ("temperature_air_max_2m", "measurement:H,source:S"),
    ]


# The fourteen letters of QFLAG that the readme words as a failed check (`model/source_flags.py`), each on a day of a
# station file as NOAA writes it. The values are the ones of the live file of USW00094728 (read 2026-11-02): the TMAX of
# 1869-06-22 is 172 tenths with QFLAG `I`, and the file returns it, flagged, with the days that failed no check.
_QFLAG_LETTERS = "DGIKLMNORSTWXZ"


def _flagged_by_letter() -> bytes:
    rows = [
        ("USW00094728", f"200001{day:02d}", "TMAX", "172", "", letter, "Z")
        for day, letter in enumerate(_QFLAG_LETTERS, start=1)
    ]
    rows.append(("USW00094728", "20000115", "TMAX", "100", "", "", "0"))
    return ghcnd_by_station(rows)


@pytest.mark.parametrize("mode", ["soft", "hard"])
def test_ghcn_daily_every_letter_of_qflag_is_the_verdict_of_the_check_source(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Test that a value whose QFLAG is one of the fourteen letters of a failed check is judged (GH-3677).

    "QFLAG1 is the quality flag for the first day of the month. There are fourteen possible values: Blank = did not
    fail any quality assurance check, D = failed duplicate check, G = failed gap check, I = failed internal consistency
    check, K = failed streak/frequent-value check, L = failed check on length of multiday period, M = failed
    megaconsistency check, N = failed naught check, O = failed climatological outlier check, R = failed lagged range
    check, S = failed spatial consistency check, T = failed temporal consistency check, W = temperature too warm for
    snow, X = failed bounds check, Z = flagged as a result of an official Datzilla investigation"
    (https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt). The default, soft, keeps the value and writes
    `suspect:source`; hard nulls it and keeps the number as `rejected:source,raw:17.2`, the tenths of a degree the file
    writes (`  172`) as the reader hands them over, in degrees.
    """
    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": _STATIONS.encode("utf8"),
            "ghcnd-inventory": _INVENTORY.encode("utf8"),
            "by_station/USW00094728": _flagged_by_letter(),
        },
    )
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "temperature_air_max_2m")],
        start="2000-01-01",
        end="2000-01-15",
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False, plausibility={"source": mode}),
    ).filter_by_station_id("USW00094728")
    df = request.values().all().df.sort("timestamp")
    flags = df.get_column("quality_flags").to_list()
    values = df.get_column("value").to_list()
    assert len(flags) == len(_QFLAG_LETTERS) + 1
    for letter, flag, value in zip(_QFLAG_LETTERS, flags, values, strict=False):
        if mode == "soft":
            assert flag == f"{letter},source:Z,suspect:source", letter
            assert value == pytest.approx(17.2), letter
        else:
            assert flag == f"{letter},source:Z,rejected:source,raw:17.2", letter
            assert value is None, letter
    # the day that failed no check is as it was in both modes
    assert flags[-1] == "source:0"
    assert values[-1] == pytest.approx(10.0)


def test_ghcn_daily_a_value_that_is_no_number_is_null_and_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cell of the file that is a text is no reading: null, and the days around it stay (GH-2627).

    The value was read as a number by the provider, which raised on a cell that was none and lost the station with
    it. The cell is null now, and so is the row, which the core drops unless the caller asked for the nulls.
    """
    body = ghcnd_by_station(
        [
            ("JA000047662", "19510101", "TMAX", "70", "", "", "I"),
            ("JA000047662", "19510102", "TMAX", "n/a", "", "", "I"),
            ("JA000047662", "19510103", "TMAX", "81", "", "", "I"),
        ]
    )
    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": _STATIONS.encode("utf8"),
            "ghcnd-inventory": _INVENTORY.encode("utf8"),
            "by_station/JA000047662": body,
        },
    )
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "temperature_air_max_2m")],
        start="1951-01-01",
        end="1951-01-03",
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    ).filter_by_station_id("JA000047662")
    df = request.values().all().df.sort("timestamp")
    assert df.get_column("value").to_list() == [7.0, None, 8.1]
