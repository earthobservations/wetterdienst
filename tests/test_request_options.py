# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the options a request takes, and for the settings it falls back on (GH-2639).

A request reads how its values come back and how its stations are chosen from its options. Given
none, it takes what its `Settings` carry as their `ts_*` settings, so that `Settings(ts_x=v)` and
`options=Options(x=v)` are the same request, and each test here says so for every option on a frame
a stubbed request gives. A parity that held for options nothing reads would pass too, so each one
also asserts that the option changed the frame it is held to.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import os
from io import BytesIO
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal
from pydantic import ValidationError

from wetterdienst import Options, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.options import options_from_settings
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from wetterdienst.model.request import TimeseriesRequest

_UTC = ZoneInfo("UTC")


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the options."""
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def _settings(changes: dict[str, Any]) -> Settings:
    """Return settings carrying the changes as their `ts_*` settings."""
    return Settings(cache_disable=True, **{f"ts_{name}": value for name, value in changes.items()})


def _station(sentinel: str = "-999") -> str:
    """Return a DWD daily product with two days of two parameters, the second day short of one."""
    columns = ["STATIONS_ID", "MESS_DATUM", "QN_3", "RSK", "TMK"]
    first = ["44", "20250101", "10", "0.5", "2.9"]
    second = ["44", "20250102", "10", sentinel, "3.5"]
    return "\n".join(";".join(f"{cell:>8}" for cell in row) + ";eor" for row in (columns, first, second)) + "\n"


def _values(monkeypatch: pytest.MonkeyPatch, **given: Any) -> pl.DataFrame:  # noqa: ANN401
    """Give the values of a stubbed DWD station, through a request built with the given arguments."""
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *args, **kwargs: pl.Series(["https://example.invalid/produkt.zip"]),  # noqa: ARG005
    )
    monkeypatch.setattr(
        dwd_observation_api,
        "download_climate_observations_data",
        lambda *args, **kwargs: [  # noqa: ARG005
            File(url="https://example.invalid/produkt.txt", content=BytesIO(_station().encode("latin-1")), status=200)
        ],
    )
    request = DwdObservationRequest(
        parameters=["daily/climate_summary/temperature_air_mean_2m", "daily/climate_summary/precipitation_amount"],
        periods={Period.RECENT},
        start=dt.datetime(2025, 1, 1, tzinfo=_UTC),
        end=dt.datetime(2025, 1, 2, tzinfo=_UTC),
        **{"settings": Settings(cache_disable=True), **given},
    )
    stations = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": "00044",
                "start_timestamp": None,
                "end_timestamp": None,
                "latitude": 50.0,
                "longitude": 10.0,
                "elevation": 100.0,
                "name": "Stub",
            }
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
        },
    )
    sr = StationsResult(stations=request, df=stations, df_all=stations, stations_filter=StationsFilter.BY_STATION_ID)
    return sr.values.all().df


#: for every option the values read: what to change, and what it is held against. The frame under
#: `changes` must differ from the one under `baseline`, or the option would be one nothing reads
VALUES_CASES = {
    "humanize": ({"humanize": False}, {}),
    "shape": ({"shape": "wide"}, {}),
    "convert_units": (
        {"convert_units": False, "unit_targets": {"temperature": "degree_fahrenheit"}},
        {"unit_targets": {"temperature": "degree_fahrenheit"}},
    ),
    "unit_targets": ({"unit_targets": {"temperature": "degree_fahrenheit"}}, {}),
    "skip_empty": ({"skip_empty": True}, {}),
    "skip_threshold": ({"skip_empty": True, "skip_threshold": 0.4}, {"skip_empty": True}),
    "skip_criteria": (
        {"skip_empty": True, "skip_threshold": 0.6, "skip_criteria": "max"},
        {"skip_empty": True, "skip_threshold": 0.6},
    ),
    "drop_nulls": ({"drop_nulls": False}, {}),
}


@pytest.mark.parametrize("name", VALUES_CASES)
def test_values_through_settings_and_through_options_are_the_same_frame(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings(ts_x=v) and options=Options(x=v) give the same values, and the option changes them."""
    changes, baseline = VALUES_CASES[name]
    through_settings = _values(monkeypatch, settings=_settings(changes))
    through_options = _values(monkeypatch, options=Options(**changes))
    through_a_dict = _values(monkeypatch, options=changes)
    expected = _values(monkeypatch, options=Options(**baseline))

    assert_frame_equal(through_settings, through_options)
    assert_frame_equal(through_a_dict, through_options)
    assert not through_options.equals(expected)


_LATITUDE, _LONGITUDE = 50.0, 8.9
#: six stations around the point at 4.0 to 4.5 km. The first two have no reading on the last day and the last two
#: lie to the south, so that the stations that are used, and how many of them, decide what the last day is
_OFFSETS = {
    "00001": (-0.03, -0.03),
    "00002": (-0.03, 0.03),
    "00003": (0.03, 0.03),
    "00004": (0.03, -0.03),
    "00005": (-0.05, -0.02),
    "00006": (-0.05, 0.02),
}
_DAYS = [dt.datetime(2021, 2, day, tzinfo=_UTC) for day in (1, 2, 3)]


def _estimate(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    **given: Any,  # noqa: ANN401
) -> tuple[pl.DataFrame, list[float]]:
    """Interpolate or summarize at a point from six stubbed stations, with the radius the search asked for."""
    stations = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": station_id,
                "start_timestamp": _DAYS[0],
                "end_timestamp": _DAYS[-1],
                "latitude": _LATITUDE + d_lat,
                "longitude": _LONGITUDE + d_lon,
                "elevation": 100.0,
                "name": station_id,
                "region": "x",
                "distance": 4.0 + index / 10,
            }
            for index, (station_id, (d_lat, d_lon)) in enumerate(_OFFSETS.items())
        ],
    )
    asked: list[float] = []

    def _filter_by_distance(
        self: DwdObservationRequest,
        latlon: tuple[float, float],  # noqa: ARG001
        distance: float,
        df_all: pl.DataFrame | None = None,  # noqa: ARG001
    ) -> StationsResult:
        asked.append(distance)
        return StationsResult(stations=self, df=stations, df_all=stations, stations_filter=StationsFilter.BY_DISTANCE)

    def _all(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(stations=self, df=stations, df_all=stations, stations_filter=StationsFilter.ALL)

    def _query(self: DwdObservationValues) -> Iterator[object]:  # noqa: ARG001
        for index, station_id in enumerate(_OFFSETS):
            df = pl.DataFrame(
                [
                    {
                        "station_id": station_id,
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "parameter": parameter,
                        "timestamp": timestamp,
                        # a station with no reading on the last day
                        "value": None if index < 2 and day == len(_DAYS) - 1 else value + index + day / 10,
                        "quality_flags": "10",
                    }
                    for parameter, value in (
                        ("temperature_air_mean_2m", 10.0),
                        ("precipitation_amount", 1.0),
                        ("snow_depth", 5.123456),
                    )
                    for day, timestamp in enumerate(_DAYS)
                ],
                schema_overrides={"value": pl.Float64},
            )
            yield SimpleNamespace(df=df)

    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", _filter_by_distance)
    monkeypatch.setattr(DwdObservationRequest, "all", _all)
    monkeypatch.setattr(DwdObservationValues, "query", _query)
    request = DwdObservationRequest(
        parameters=[
            ("daily", "climate_summary", "temperature_air_mean_2m"),
            ("daily", "climate_summary", "precipitation_amount"),
            ("daily", "climate_summary", "snow_depth"),
        ],
        start=_DAYS[0],
        end=_DAYS[-1],
        **{"settings": Settings(cache_disable=True), **given},
    )
    return getattr(request, method)(latlon=(_LATITUDE, _LONGITUDE)).df, asked


_MILE = {"length_short": "mile"}
#: for every option the interpolation and the summary read: what to change, what it is held against, and which of
#: the two it changes the answer of. The nearest station with data answers a summary, so a wider search, more
#: stations and a station next to the point change nothing there
ESTIMATE_CASES = {
    "humanize": ({"humanize": False}, {}, ("interpolate", "summarize")),
    "shape": ({"shape": "wide"}, {}, ()),
    "convert_units": ({"convert_units": False, "unit_targets": _MILE}, {"unit_targets": _MILE}, ("interpolate",)),
    "unit_targets": ({"unit_targets": _MILE}, {}, ("interpolate", "summarize")),
    "skip_empty": ({"skip_empty": True}, {}, ()),
    "skip_threshold": ({"skip_threshold": 0.5}, {}, ()),
    "skip_criteria": ({"skip_criteria": "max"}, {}, ()),
    "drop_nulls": ({"drop_nulls": False}, {}, ()),
    "geo_station_distance_homogeneous": ({"geo_station_distance_homogeneous": 3.5}, {}, ("interpolate", "summarize")),
    "geo_station_distance_heterogeneous": (
        {"geo_station_distance_heterogeneous": 1.5},
        {},
        ("interpolate", "summarize"),
    ),
    "geo_station_distance": (
        {"geo_station_distance": {"temperature_air_mean_2m": 3.5}},
        {},
        ("interpolate", "summarize"),
    ),
    "geo_station_distance_resolution_factors": (
        {"geo_station_distance_resolution_factors": {"daily": 0.1}},
        {},
        ("interpolate", "summarize"),
    ),
    "geo_use_nearby_station_distance": ({"geo_use_nearby_station_distance": 4.05}, {}, ("interpolate",)),
    "geo_min_gain_of_value_pairs": (
        {"geo_min_gain_of_value_pairs": 0.9, "geo_num_additional_stations": 1},
        {"geo_num_additional_stations": 1},
        ("interpolate",),
    ),
    "geo_num_additional_stations": ({"geo_num_additional_stations": 0}, {}, ("interpolate",)),
}


@pytest.mark.parametrize("method", ["interpolate", "summarize"])
@pytest.mark.parametrize("name", ESTIMATE_CASES)
def test_estimates_through_settings_and_through_options_are_the_same_frame(
    name: str,
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interpolating and summarizing give the same answer through settings and through options."""
    pytest.importorskip("shapely")
    changes, baseline, changed_in = ESTIMATE_CASES[name]
    through_settings, asked_settings = _estimate(monkeypatch, method, settings=_settings(changes))
    through_options, asked_options = _estimate(monkeypatch, method, options=Options(**changes))
    through_a_dict, asked_dict = _estimate(monkeypatch, method, options=changes)
    expected, _ = _estimate(monkeypatch, method, options=Options(**baseline))

    assert_frame_equal(through_settings, through_options)
    assert_frame_equal(through_a_dict, through_options)
    assert asked_settings == asked_options == asked_dict
    if method in changed_in:
        assert not through_options.equals(expected)


def test_estimating_reads_a_long_humanized_copy_and_leaves_the_requests_options() -> None:
    """The copy `interpolate` and `summarize` read through is long and humanized, and the request keeps its own."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        options=Options(shape="wide", humanize=False, drop_nulls=False, skip_empty=True, convert_units=False),
    )

    copy = request._for_estimating()  # noqa: SLF001

    assert copy is not request
    assert (copy.options.shape, copy.options.humanize, copy.options.drop_nulls) == ("long", True, False)
    # nothing else of the options changed, and neither did the settings
    assert copy.options.replace(shape="wide", humanize=False) == request.options
    assert copy.settings is request.settings
    assert (request.options.shape, request.options.humanize) == ("wide", False)


def test_estimating_drops_the_nulls_the_wide_shape_would_not_have() -> None:
    """A copy of a wide request drops nulls as the wide request does, which is none, however `drop_nulls` is set."""
    wide = _request(options={"shape": "wide", "drop_nulls": True})
    assert wide.options.drop_nulls
    assert not wide.options.drop_nulls_effective

    copy = wide._for_estimating()  # noqa: SLF001

    assert not copy.options.drop_nulls_effective
    assert wide.options.drop_nulls


def test_estimating_reads_the_request_itself_where_it_is_long_and_humanized() -> None:
    """A request that already reads as the estimate needs is not copied."""
    request = DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")])
    assert request._for_estimating() is request  # noqa: SLF001


# the options a request takes from the settings it was given, and how it takes them


#: a value other than the default for every option, as the settings carry it
CARRIED = {
    "humanize": False,
    "shape": "wide",
    "convert_units": False,
    "unit_targets": {"temperature": "degree_fahrenheit"},
    "skip_empty": True,
    "skip_threshold": 0.5,
    "skip_criteria": "max",
    "drop_nulls": False,
    "geo_station_distance_homogeneous": 50.0,
    "geo_station_distance_heterogeneous": 25.0,
    "geo_station_distance": {"temperature_air_mean_2m": 60.0},
    "geo_station_distance_resolution_factors": {"daily": 3.0},
    "geo_use_nearby_station_distance": 2.0,
    "geo_min_gain_of_value_pairs": 0.5,
    "geo_num_additional_stations": 5,
}


def _request(**given: Any) -> DwdObservationRequest:  # noqa: ANN401
    """Return a request for one parameter, made with the given arguments."""
    return DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")], **given)


def test_the_cases_name_every_option() -> None:
    """The values these tests carry are one for every option, so that a new option is not left untested."""
    assert (
        set(CARRIED)
        == set(Options.model_fields)
        == set(VALUES_CASES) | {name for name in ESTIMATE_CASES if name.startswith("geo_")}
    )
    assert set(CARRIED) == set(ESTIMATE_CASES)


@pytest.mark.parametrize("name", CARRIED)
def test_a_request_takes_an_option_from_the_settings_it_carries_as(name: str) -> None:
    """A request given settings and no options reads the settings' `ts_*` setting as its option."""
    request = _request(settings=_settings({name: CARRIED[name]}))

    assert isinstance(request.options, Options)
    assert request.options.model_dump() == Options(**{name: CARRIED[name]}).model_dump()
    assert request.options.model_dump()[name] == CARRIED[name]


def test_a_request_takes_the_radii_the_settings_expand_to() -> None:
    """The radius for a parameter and a resolution is the same through the settings and through the options."""
    changes = {
        "geo_station_distance_heterogeneous": 25.0,
        "geo_station_distance": {"temperature_air_mean_2m": 60.0},
        "geo_station_distance_resolution_factors": {"daily": 3.0},
    }
    through_settings = _request(settings=_settings(changes)).options
    through_options = _request(options=Options(**changes)).options

    for parameter in ("temperature_air_mean_2m", "precipitation_amount", "snow_depth"):
        for resolution in ("minute_10", "hourly", "daily"):
            assert through_settings.geo_station_distance_for(parameter, resolution) == (
                through_options.geo_station_distance_for(parameter, resolution)
            )
    assert through_options.geo_station_distance_for("precipitation_amount", "daily") == 75.0
    assert through_options.geo_station_distance_for("temperature_air_mean_2m", "daily") == 60.0


def test_a_request_given_neither_has_the_default_options() -> None:
    """With no options and the default settings, the options are the default ones."""
    assert _request().options == Options()


def test_the_options_follow_the_environment_where_none_are_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_TS_*` sets the options of a request given neither options nor settings, as it set its settings."""
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    monkeypatch.setenv("WD_TS_SKIP_THRESHOLD", "0.5")

    options = _request().options

    assert (options.shape, options.skip_threshold) == ("wide", 0.5)
    assert options == _request(settings=Settings()).options


def test_an_options_object_is_used_as_it_is() -> None:
    """The options a caller built are the request's own, not a copy."""
    options = Options(shape="wide")
    assert _request(options=options).options is options


def test_options_are_the_argument_after_the_periods() -> None:
    """`options` comes after `periods`, so a caller passing the arguments up to `periods` positionally is unaffected."""
    names = [field.name for field in dataclasses.fields(DwdObservationRequest)]
    assert names[names.index("periods") + 1] == "options"

    options = Options(shape="wide")
    request = DwdObservationRequest(
        [("daily", "climate_summary", "temperature_air_mean_2m")],
        None,
        None,
        Settings(cache_disable=True),
        "recent",
        options,
    )
    assert request.options is options
    assert request.periods == {Period.RECENT}


def test_a_dict_of_options_is_the_options_it_names() -> None:
    """A dict names options; the others are the defaults."""
    options = _request(options={"shape": "wide", "unit_targets": {"temperature": "degree_fahrenheit"}}).options

    assert options == Options(shape="wide", unit_targets={"temperature": "degree_fahrenheit"})
    assert options.humanize


def test_a_dict_of_options_is_not_merged_into_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """What a dict names replaces what the environment set, a mapping included; what it leaves out is the environment's.

    `Options(**given)` would deep-merge `WD_TS_UNIT_TARGETS` into the mapping a caller named, so that
    a target they never asked for stayed.
    """
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", '{"temperature": "degree_fahrenheit"}')
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", '{"snow_depth": 30}')
    monkeypatch.setenv("WD_TS_SHAPE", "wide")

    options = _request(options={"unit_targets": {"length_short": "mile"}, "geo_station_distance": {}}).options

    assert options.unit_targets == {"length_short": "mile"}
    assert options.geo_station_distance_for("snow_depth", "hourly") == 40.0
    assert options.shape == "wide"
    # whereas the constructor merges, which is what the dict avoids
    assert Options(unit_targets={"length_short": "mile"}).unit_targets == {
        "temperature": "degree_fahrenheit",
        "length_short": "mile",
    }


@pytest.mark.parametrize(
    "given",
    [{"shpae": "wide"}, {"shape": "tall"}, {"skip_threshold": 2}, {"unit_targets": {"temperature": "kelvins"}}],
    ids=["unknown", "choice", "bound", "unit"],
)
def test_a_dict_of_options_is_refused_where_options_would_be(given: dict[str, object]) -> None:
    """A dict is checked as `Options(**given)` is, and the error does not repeat the input refused."""
    with pytest.raises(ValidationError) as error:
        _request(options=given)
    assert "input_value" not in str(error.value)


def test_a_dict_of_options_notes_a_wide_shape_once(caplog: pytest.LogCaptureFixture) -> None:
    """The note that nulls are kept in the wide shape is given for a dict that makes it wide, as for options."""
    with caplog.at_level(logging.INFO, logger="wetterdienst.options"):
        _request(options={"shape": "wide"})
    assert [record.getMessage() for record in caplog.records if record.name == "wetterdienst.options"] == [
        "option 'drop_nulls' is only available with option 'shape=long' and is thus ignored in this request.",
    ]


@pytest.mark.parametrize("options", [Options(), {}, {"shape": "wide"}], ids=["options", "empty", "dict"])
def test_options_beside_settings_that_carry_options_are_refused(options: Options | dict) -> None:
    """Settings that carry a `ts_*` setting and options are two answers to one question, and a caller is told."""
    with pytest.raises(ValueError, match=r"ts_shape.*options="):
        _request(settings=_settings({"shape": "wide"}), options=options)


def test_options_beside_settings_given_as_a_dict_are_refused() -> None:
    """The settings are checked as they are once validated, whether they were given as a dict or not."""
    with pytest.raises(ValueError, match="ts_humanize, ts_skip_empty"):
        _request(settings={"cache_disable": True, "ts_skip_empty": True, "ts_humanize": False}, options={})


def test_options_beside_settings_that_carry_none_are_taken() -> None:
    """Settings of the host alone leave the options to the caller."""
    settings = Settings(cache_disable=True, ts_shape="long", ts_humanize=True)
    assert _request(settings=settings, options={"shape": "wide"}).options.shape == "wide"


def test_the_environment_is_no_settings_of_the_callers_to_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `WD_TS_*` the operator set is in the settings too, and does not count against options the caller passes."""
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", '{"temperature": "degree_fahrenheit"}')

    assert _request(options=Options(shape="long")).options.shape == "long"
    assert _request(options={"humanize": False}).options.shape == "wide"


def test_a_request_keeps_the_options_it_was_built_with() -> None:
    """Options are fixed when the request is built: changing the settings afterwards does not reach them."""
    settings = Settings(cache_disable=True)
    request = _request(settings=settings)
    settings.ts_shape = "wide"

    assert request.options.shape == "long"
    assert _request(settings=settings).options.shape == "wide"


def test_stations_result_has_the_options_of_its_request() -> None:
    """The result of a request carries its options, which the values read."""
    request = _request(options={"humanize": False})
    stations = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )

    assert stations.options is request.options
    assert stations.values.sr.options.humanize is False


def test_the_settings_of_a_request_are_the_hosts_alone_for_options() -> None:
    """Options are not read from `settings` once given: the request reads them from `options` only."""
    request = _request(settings=Settings(cache_disable=True), options={"shape": "wide"})
    assert request.settings.ts_shape == "long"
    assert request.options.shape == "wide"


def test_options_from_settings_are_those_the_settings_dump() -> None:
    """`options_from_settings` takes the settings' `ts_*` settings as the options of the same name."""
    settings = _settings(CARRIED)
    assert options_from_settings(settings).model_dump() == Options(**CARRIED).model_dump()


@pytest.mark.parametrize(
    ("request_class", "parameter"),
    [
        (DwdMosmixRequest, ("hourly", "small")),
        (DwdDmoRequest, ("hourly", "icon")),
        (DwdDerivedRequest, ("monthly", "heating_degreedays", "heating_degree_day")),
    ],
    ids=["mosmix", "dmo", "derived"],
)
def test_other_requests_take_options(request_class: type[TimeseriesRequest], parameter: tuple[str, ...]) -> None:
    """The argument is the base request's, so a request of another provider takes it too."""
    request = request_class(parameters=[parameter], options={"shape": "wide"})
    assert request.options.shape == "wide"
