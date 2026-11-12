# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for CHMI's values, the five resolutions and the empty answers (GH-2627).

The files are the shapes CHMI writes (`dly-`, `mly-`, `yrs-`, `10m-` and `1h-` files of Cheb, 0-20000-0-11406), served
through the provider's own reader. `tests/provider/frames.snapshot.json` records what the core made of each, which is
the net under moving the shaping of the frame (the identity columns, the empty frame) out of the provider.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst.exceptions import DateRequiredError
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.options import Options
from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Iterator

CHEB = "0-20000-0-11406"
BRNO = "0-20000-0-11723"
UTC = dt.UTC

_DAILY_T = (
    "STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,AVG,2020-01-01T00:00Z,-3.0,,0.0,\n"
    f"{CHEB},T,20:00,2020-01-01T20:00Z,-1.0,,0.0,\n"
    f"{CHEB},T,AVG,2020-01-02T00:00Z,,,4.0,\n"
    f"{CHEB},T,AVG,2020-01-03T00:00Z,-2.5,,3.0,\n"
)
_DAILY_SRA = (
    "STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},SRA,06:00,2020-01-01T06:00Z,0.0,T,0.0,\n"
    f"{CHEB},SRA,06:00,2020-01-02T06:00Z,1.2,,0.0,\n"
)
_MONTHLY_T = (
    "STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
    f"{CHEB},T,2020,1,AVG,AVG,1.1,,,\n"
    f"{CHEB},T,2020,2,AVG,AVG,2.3,,I,\n"
    f"{CHEB},T,2020,2,AVG,MAX,9.0,*,,\n"
)
_MONTHLY_SRA = (
    "STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
    f"{CHEB},SRA,2020,1,06:00,SUM,21.3,,,\n"
)
_ANNUAL_T = (
    "STATION,ELEMENT,YEAR,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
    f"{CHEB},T,2018,AVG,AVG,9.7,,,\n"
    f"{CHEB},T,2019,AVG,AVG,10.1,,I,\n"
)
_TEN_MINUTES_T_JANUARY = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,2020-01-31T23:50Z,-2.8,,0.0,\n"
    f"{CHEB},T,2020-01-31T23:40Z,,,4.0,\n"
)
_TEN_MINUTES_T_FEBRUARY = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},T,2020-02-01T00:00Z,-2.7,,0.0,\n"
    f"{CHEB},T,2020-02-01T00:10Z,-2.6,,1.0,\n"
)
_HOURLY_TD = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},Td,2020-01-01T00:00Z,-3.9,,0.0,\n"
    f"{CHEB},Td,2020-01-01T01:00Z,-3.7,,0.0,\n"
)
_HOURLY_SRA1H = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},SRA1H,2020-01-01T00:00Z,0.0,T,0.0,\n"
    f"{CHEB},SRA1H,2020-01-01T01:00Z,0.3,,0.0,\n"
)
_HOURLY_P_DECEMBER_2024 = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},P,2024-12-31T22:00Z,967.5,,0.0,\n"
    f"{CHEB},P,2024-12-31T23:00Z,967.2,,0.0,\n"
)
_HOURLY_P_HM_DECEMBER_2024 = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},P_hm,2024-12-31T22:00Z,1029.1,,0.0,\n"
    f"{CHEB},P_hm,2024-12-31T23:00Z,1028.8,,0.0,\n"
)
_HOURLY_P_HM_JANUARY_2025 = (
    "STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
    f"{CHEB},P_hm,2025-01-01T00:00Z,1028.6,,0.0,\n"
    f"{CHEB},P_hm,2025-01-01T01:00Z,1028.0,,0.0,\n"
)


@pytest.fixture(autouse=True)
def _a_clean_record() -> Iterator[None]:
    """Start each test without the warnings an earlier one recorded in this thread, and leave none behind."""
    begin_response()
    yield
    begin_response()


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> list[str]:
    """Serve the files by the tail of their url; any other file of the portal is a 404, as for a station without it."""
    asked: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        asked.append(url)
        for tail, body in files.items():
            if url.endswith(tail):
                return File(url=url, content=BytesIO(body.encode()), status=200)
        return File(url=url, content=FileNotFoundError(url), status=404)

    monkeypatch.setattr(chmi_api, "download_file", download_file)
    return asked


def _values(
    resolution: str,
    *,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
    drop_nulls: bool = True,
) -> pl.DataFrame:
    request = ChmiObservationRequest(
        parameters=[(resolution, "data")],
        start=start,
        end=end,
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, "data", CHEB).values().all().df


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["station_id"].unique().to_list() == [CHEB]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


def test_chmi_daily_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The daily files of T and SRA: one TIMEFUNC each, a missing value (quality 4) is kept null beside its code."""
    _serve(monkeypatch, {f"dly-{CHEB}-T.csv": _DAILY_T, f"dly-{CHEB}-SRA.csv": _DAILY_SRA})
    df = _values("daily", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 3, tzinfo=UTC))
    _assert_the_long_form(df, resolution="daily")
    assert df.height == 4
    kept = _values(
        "daily", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 3, tzinfo=UTC), drop_nulls=False
    )
    assert kept.height == 5
    assert kept.filter(pl.col("value").is_null())["quality_flags"].to_list() == ["4"]
    assert kept.filter(pl.col("parameter").eq("precipitation_amount")).sort("timestamp")["quality_flags"].to_list() == [
        "0,element:T",
        "0",
    ]


def test_chmi_monthly_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The monthly files pin TIMEFUNCTION and MDFUNCTION, and the period start is the stamp."""
    _serve(monkeypatch, {f"mly-{CHEB}-T.csv": _MONTHLY_T, f"mly-{CHEB}-SRA.csv": _MONTHLY_SRA})
    df = _values("monthly", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 2, 1, tzinfo=UTC))
    _assert_the_long_form(df, resolution="monthly")
    assert df.height == 3
    assert df.sort("timestamp")["timestamp"].to_list()[-1] == dt.datetime(2020, 2, 1, tzinfo=UTC)


def test_chmi_annual_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The annual files have no MONTH column, and the year start is the stamp."""
    _serve(monkeypatch, {f"yrs-{CHEB}-T.csv": _ANNUAL_T})
    df = _values("annual", start=dt.datetime(2018, 1, 1, tzinfo=UTC), end=dt.datetime(2019, 1, 1, tzinfo=UTC))
    _assert_the_long_form(df, resolution="annual")
    assert df.sort("timestamp")["quality_flags"].to_list() == [None, "interrupted:I"]


def test_chmi_10_minutes_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 10 minute files are one per month: the two of January and February are read, the rest are 404."""
    asked = _serve(
        monkeypatch,
        {f"10m-{CHEB}-T-202001.csv": _TEN_MINUTES_T_JANUARY, f"10m-{CHEB}-T-202002.csv": _TEN_MINUTES_T_FEBRUARY},
    )
    df = _values(
        "10_minutes", start=dt.datetime(2020, 1, 31, 23, 40, tzinfo=UTC), end=dt.datetime(2020, 2, 1, 0, 10, tzinfo=UTC)
    )
    _assert_the_long_form(df, resolution="10_minutes")
    assert df.height == 3
    assert any(url.endswith("202002.csv") for url in asked)


def test_chmi_hourly_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hourly files of Td and SRA1H, one month; the P file of the dataset is a 404 and adds no row."""
    _serve(monkeypatch, {f"1h-{CHEB}-Td-202001.csv": _HOURLY_TD, f"1h-{CHEB}-SRA1H-202001.csv": _HOURLY_SRA1H})
    df = _values("hourly", start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 1, 1, tzinfo=UTC))
    _assert_the_long_form(df, resolution="hourly")
    assert df.height == 4


@pytest.mark.parametrize(
    ("resolution", "files"),
    [
        pytest.param("daily", {}, id="daily-no-file"),
        pytest.param("monthly", {}, id="monthly-no-file"),
        pytest.param("10_minutes", {}, id="10-minutes-no-file"),
        pytest.param(
            "daily", {f"dly-{CHEB}-T.csv": "STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"}, id="header-only"
        ),
        pytest.param(
            "daily",
            {f"dly-{CHEB}-T.csv": _DAILY_T.replace(",AVG,", ",MAX,")},
            id="no-timefunc-of-the-element",
        ),
        pytest.param(
            "monthly",
            {f"mly-{CHEB}-T.csv": _MONTHLY_T.replace(",AVG,AVG,", ",AVG,MIN,")},
            id="no-function-pair-of-the-element",
        ),
    ],
)
def test_chmi_without_a_reading_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch, resolution: str, files: dict[str, str]
) -> None:
    """A station without the files of the dataset, or without the series this reader selects, has no rows."""
    _serve(monkeypatch, files)
    df = _values(resolution, start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 3, tzinfo=UTC))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()


def test_chmi_subdaily_without_a_date_range_is_refused_and_asks_for_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The month files of the sub-daily resolutions are addressed by the range: with none, the request is refused."""
    asked = _serve(monkeypatch, {f"10m-{CHEB}-T-202001.csv": _TEN_MINUTES_T_JANUARY})
    with pytest.raises(DateRequiredError, match="The dataset 10_minutes/data needs a window"):
        _values("10_minutes")
    assert asked == []


def test_chmi_hourly_sea_level_pressure_is_its_own_parameter_and_the_station_pressure_ends_with_2024(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A window over the turn of the year reads P_hm on both sides, P up to 2024 only, and says why P stops (GH-3413).

    The source has no `P` file from 2025 on and publishes `P_hm` (the pressure reduced to sea level) in every year:
    two quantities, so `P_hm` is `pressure_air_sea_level` and not `pressure_air_site` under another element. The
    files of `P` of 2025 are not asked for, and the warning is told once for the request, not once for each of its
    two stations.
    """
    asked = _serve(
        monkeypatch,
        {
            f"1h-{station}-{element}-{month}.csv": body
            for station in (CHEB, BRNO)
            for element, month, body in (
                ("P", "202412", _HOURLY_P_DECEMBER_2024),
                ("P_hm", "202412", _HOURLY_P_HM_DECEMBER_2024),
                ("P_hm", "202501", _HOURLY_P_HM_JANUARY_2025),
            )
        },
    )
    request = ChmiObservationRequest(
        parameters=[("hourly", "data", "pressure_air_site"), ("hourly", "data", "pressure_air_sea_level")],
        start=dt.datetime(2024, 12, 31, 22, tzinfo=UTC),
        end=dt.datetime(2025, 1, 1, 1, tzinfo=UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    one = stations_result(request, "hourly", "data", CHEB)
    both = pl.concat([one.df, one.df.with_columns(pl.lit(BRNO).alias("station_id"))])
    with caplog.at_level("WARNING"):
        df = dataclasses.replace(one, df=both, _df_all=both).values().all().df
    assert df["station_id"].unique().sort().to_list() == [CHEB, BRNO]
    for station in (CHEB, BRNO):
        by_parameter = {
            parameter: part.sort("timestamp")["value"].to_list()
            for (parameter,), part in df.filter(pl.col("station_id").eq(station)).group_by("parameter")
        }
        assert by_parameter == {
            "pressure_air_site": [967.5, 967.2],
            "pressure_air_sea_level": [1029.1, 1028.8, 1028.6, 1028.0],
        }
    assert not any("-P-2025" in url for url in asked)
    assert any("-P_hm-202501" in url for url in asked)
    (warning,) = recorded_warnings()
    assert warning["code"] == "parameter-ended"
    assert "pressure_air_site" in warning["message"]
    assert "after 2024" in warning["message"]
    assert "pressure_air_sea_level" in warning["message"]
    assert len([record for record in caplog.records if record.levelname == "WARNING"]) == 1


def test_chmi_hourly_station_pressure_in_a_window_ending_in_2024_has_no_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The warning is for a window that reaches past the last year, not for every hourly request."""
    _serve(monkeypatch, {f"1h-{CHEB}-P-202412.csv": _HOURLY_P_DECEMBER_2024})
    df = _values(
        "hourly", start=dt.datetime(2024, 12, 31, 22, tzinfo=UTC), end=dt.datetime(2024, 12, 31, 23, tzinfo=UTC)
    )
    assert df["parameter"].unique().to_list() == ["pressure_air_site"]
    assert recorded_warnings() == []


def test_chmi_hourly_window_after_2024_is_the_empty_frame_with_the_reason_for_the_station_pressure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asked for P alone in 2025, the answer is empty as before, and now tells that CHMI has no such file."""
    asked = _serve(monkeypatch, {f"1h-{CHEB}-P_hm-202501.csv": _HOURLY_P_HM_JANUARY_2025})
    request = ChmiObservationRequest(
        parameters=[("hourly", "data", "pressure_air_site")],
        start=dt.datetime(2025, 1, 1, tzinfo=UTC),
        end=dt.datetime(2025, 1, 1, 1, tzinfo=UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "hourly", "data", CHEB).values().all().df
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
    assert not any("-P-2025" in url for url in asked)
    # told by `parameter-ended` alone, which names the parameter: `parameter-without-rows` would say it a second time
    (warning,) = recorded_warnings()
    assert warning["code"] == "parameter-ended"
    assert warning["parameter"] == "hourly/data/pressure_air_site"


def test_chmi_hourly_window_after_2024_of_another_parameter_has_no_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dataset is read as a whole, but the warning is for the parameter that was asked for."""
    _serve(monkeypatch, {f"1h-{CHEB}-Td-202501.csv": _HOURLY_TD.replace("2020", "2025")})
    request = ChmiObservationRequest(
        parameters=[("hourly", "data", "temperature_dew_point_2m")],
        start=dt.datetime(2025, 1, 1, tzinfo=UTC),
        end=dt.datetime(2025, 1, 1, 1, tzinfo=UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "hourly", "data", CHEB).values().all().df
    assert df["parameter"].unique().to_list() == ["temperature_dew_point_2m"]
    assert recorded_warnings() == []


def test_chmi_hourly_downloads_the_elements_asked_for_and_the_whole_dataset_asks_for_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dataset is read as a whole, but a request for one parameter fetches the files of that element only."""
    asked = _serve(monkeypatch, {f"1h-{CHEB}-P-202401.csv": _HOURLY_P_DECEMBER_2024.replace("2024-12", "2024-01")})
    one = ChmiObservationRequest(
        parameters=[("hourly", "data", "pressure_air_site")],
        start=dt.datetime(2024, 1, 1, tzinfo=UTC),
        end=dt.datetime(2024, 2, 1, tzinfo=UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    stations_result(one, "hourly", "data", CHEB).values().all()
    assert {url.rsplit("-", 2)[-2] for url in asked} == {"P"}
    asked.clear()
    whole = _values("hourly", start=dt.datetime(2024, 1, 1, tzinfo=UTC), end=dt.datetime(2024, 2, 1, tzinfo=UTC))
    assert whole["parameter"].unique().to_list() == ["pressure_air_site"]
    assert {url.rsplit("-", 2)[-2] for url in asked} == {"Td", "SRA1H", "P", "P_hm"}


@pytest.mark.parametrize("shape", ["long", "wide"])
def test_chmi_element_of_two_resolutions_is_named_for_the_resolution_it_was_read_at(
    monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """The element `T` is `temperature_air_2m` at 10 minutes and `temperature_air_mean_2m` daily (GH-3605).

    The mapping from the name CHMI writes to the canonical one was one dict over the whole request, so asking for both
    resolutions named the 10 minute readings for the daily parameter, the last to be put in the dict.
    """
    _serve(monkeypatch, {f"dly-{CHEB}-T.csv": _DAILY_T, f"10m-{CHEB}-T-202001.csv": _TEN_MINUTES_T_JANUARY})
    request = ChmiObservationRequest(
        parameters=[("10_minutes", "data", "temperature_air_2m"), ("daily", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2020, 1, 1, tzinfo=UTC),
        end=dt.datetime(2020, 1, 31, 23, 50, tzinfo=UTC),
        settings=_settings(),
        options=Options(shape=shape, drop_nulls=True),
    )
    stations = pl.concat(
        [stations_result(request, resolution, "data", CHEB).df for resolution in ("10_minutes", "daily")]
    )
    sr = StationsResult(request=request, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_STATION_ID)
    df = sr.values().all().df
    if shape == "long":
        named = df.group_by("resolution").agg(pl.col("parameter").unique().sort())
        assert dict(named.iter_rows()) == {"10_minutes": ["temperature_air_2m"], "daily": ["temperature_air_mean_2m"]}
        assert df.filter(pl.col("resolution").eq("10_minutes"))["value"].sort().to_list() == [-2.8]
        assert df.filter(pl.col("resolution").eq("daily"))["value"].sort().to_list() == [-3.0, -2.5]
    else:
        ten, daily = (df.filter(pl.col("resolution").eq(resolution)) for resolution in ("10_minutes", "daily"))
        assert ten["temperature_air_2m"].drop_nulls().to_list() == [-2.8]
        assert sorted(daily["temperature_air_mean_2m"].drop_nulls().to_list()) == [-3.0, -2.5]
        assert ten["temperature_air_mean_2m"].drop_nulls().is_empty()
        assert daily["temperature_air_2m"].drop_nulls().is_empty()
