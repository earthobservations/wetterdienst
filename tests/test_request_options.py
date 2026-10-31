# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the options a request takes, and for the deprecated settings it still falls back on (GH-2639).

A request reads how its values come back and how its stations are chosen from its options, and each
test here says that a dict of options and an `Options` are the same request for every option, on a
frame a stubbed request gives. A parity that held for options nothing reads would pass too, so each
one also asserts that the option changed the frame it is held to. The `ts_*` settings are options
no more but are still taken, with a warning, from the settings a request is given.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import os
import warnings
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
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
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
    sr = StationsResult(request=request, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_STATION_ID)
    return sr.values().all().df


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
def test_values_through_a_dict_and_through_options_are_the_same_frame(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dict of options and an `Options` give the same values, and the option changes them."""
    changes, baseline = VALUES_CASES[name]
    through_options = _values(monkeypatch, options=Options(**changes))
    through_a_dict = _values(monkeypatch, options=changes)
    expected = _values(monkeypatch, options=Options(**baseline))

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
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_DISTANCE)

    def _all(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.ALL)

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
            yield SimpleNamespace(df=df, data_updated_at=None)

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
#: for every option: what to change, what it is held against, and which of the two it changes the answer of. The
#: nearest station with data answers a summary, so a wider search, more stations and a station next to the point
#: change nothing there. The stubbed query serves the frames that the shape, the skip rules and `drop_nulls` act on
#: whole, so those are held to parity alone (the values cases above change the frame with them)
ESTIMATE_CASES = {
    "humanize": ({"humanize": False}, {}, ("interpolate", "summarize")),
    "shape": ({"shape": "wide"}, {}, ()),
    "convert_units": ({"convert_units": False, "unit_targets": _MILE}, {"unit_targets": _MILE}, ("interpolate",)),
    "unit_targets": ({"unit_targets": _MILE}, {}, ("interpolate", "summarize")),
    "skip_empty": ({"skip_empty": True}, {}, ()),
    "skip_threshold": ({"skip_threshold": 0.5}, {}, ()),
    "skip_criteria": ({"skip_criteria": "max"}, {}, ()),
    "drop_nulls": ({"drop_nulls": False}, {}, ()),
    # the modes of the checks are read by the providers' readers, held in `tests/model/test_plausibility.py`; an
    # estimate leaves out a suspect value in any mode, so the answer is the same
    "plausibility": ({"plausibility": {"range": "soft"}}, {}, ()),
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
def test_estimates_through_a_dict_and_through_options_are_the_same_frame(
    name: str,
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interpolating and summarizing give the same answer through a dict of options and through options."""
    pytest.importorskip("shapely")
    changes, baseline, changed_in = ESTIMATE_CASES[name]
    through_options, asked_options = _estimate(monkeypatch, method, options=Options(**changes))
    through_a_dict, asked_dict = _estimate(monkeypatch, method, options=changes)
    expected, _ = _estimate(monkeypatch, method, options=Options(**baseline))

    assert_frame_equal(through_a_dict, through_options)
    assert asked_options == asked_dict
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


# the options a request takes


#: a value other than the default for every option
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
    "station_window_end_buffer": 7,
    "plausibility": {"range": "soft", "elevation": "hard", "stuck": "hard", "consistency": "hard", "floor": "hard"},
}
#: the options the choice of stations reads and no values frame shows, held in
#: `tests/model/test_station_window_buffer.py`
SELECTION_OPTIONS = {"station_window_end_buffer"}
#: the options the providers' readers read, which the stubbed station here has nothing to judge for, held in
#: `tests/model/test_plausibility.py` and `tests/provider/test_value_stubs.py`
READER_OPTIONS = {"plausibility"}


def _request(**given: Any) -> DwdObservationRequest:  # noqa: ANN401
    """Return a request for one parameter, made with the given arguments."""
    return DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")], **given)


def test_the_cases_name_every_option() -> None:
    """The values these tests carry are one for every option, so that a new option is not left untested."""
    unread = SELECTION_OPTIONS | READER_OPTIONS
    assert (
        set(CARRIED) - unread
        == set(Options.model_fields) - unread
        == set(VALUES_CASES) | {name for name in ESTIMATE_CASES if name.startswith("geo_")}
    )
    assert set(CARRIED) - SELECTION_OPTIONS == set(ESTIMATE_CASES)
    assert set(Options.model_fields) >= unread


@pytest.mark.parametrize("name", CARRIED)
def test_a_request_takes_every_option_as_options_and_as_a_dict(name: str) -> None:
    """`options=Options(x=v)` and `options={"x": v}` give the request the option `x`, and no other changes."""
    for given in (Options(**{name: CARRIED[name]}), {name: CARRIED[name]}):
        request = _request(options=given)

        assert isinstance(request.options, Options)
        assert request.options.model_dump() == Options(**{name: CARRIED[name]}).model_dump()
        assert request.options.model_dump()[name] == CARRIED[name]


def test_a_request_takes_the_radii_a_dict_of_options_expands_to() -> None:
    """The radius for a parameter and a resolution is the same through a dict of options and through `Options`."""
    changes = {
        "geo_station_distance_heterogeneous": 25.0,
        "geo_station_distance": {"temperature_air_mean_2m": 60.0},
        "geo_station_distance_resolution_factors": {"daily": 3.0},
    }
    through_dict = _request(options=changes).options
    through_options = _request(options=Options(**changes)).options

    for parameter in ("temperature_air_mean_2m", "precipitation_amount", "snow_depth"):
        for resolution in ("minute_10", "hourly", "daily"):
            assert through_dict.geo_station_distance_for(parameter, resolution) == (
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


@pytest.mark.parametrize("request_class", [DwdObservationRequest, DwdMosmixRequest, DwdDmoRequest, DwdSwsmosRequest])
def test_options_are_keyword_only(request_class: type[TimeseriesRequest]) -> None:
    """`options` moves none of the arguments a request takes positionally, `issue` of the forecasts included."""
    fields = {field.name: field for field in dataclasses.fields(request_class) if field.init}
    assert fields["options"].kw_only
    positional = [name for name, field in fields.items() if not field.kw_only]
    assert "options" not in positional
    if "issue" in fields:
        assert positional.index("issue") == positional.index("periods") + 1


def test_a_request_copied_with_replace_keeps_its_options() -> None:
    """`dataclasses.replace` hands the resolved options back, which the copy takes as they are."""
    request = _request(options=Options(shape="wide"))

    copy = dataclasses.replace(request, start="2020-01-01")

    assert copy.options == request.options
    assert copy.options.shape == "wide"


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


def test_a_dict_of_options_warns_of_a_radius_for_a_parameter_never_interpolated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The warning of `Options` for a radius that is never read is given for a dict naming it too."""
    with caplog.at_level(logging.WARNING, logger="wetterdienst.options"):
        _request(options={"geo_station_distance": {"precipitation_form": 5.0}})
    messages = [record.getMessage() for record in caplog.records if record.name == "wetterdienst.options"]
    assert len(messages) == 1
    assert "['precipitation_form'], which are never interpolated" in messages[0]


def test_a_dict_of_options_notes_a_wide_shape_once(caplog: pytest.LogCaptureFixture) -> None:
    """The note that nulls are kept in the wide shape is given for a dict that makes it wide, as for options."""
    with caplog.at_level(logging.INFO, logger="wetterdienst.options"):
        _request(options={"shape": "wide"})
    assert [record.getMessage() for record in caplog.records if record.name == "wetterdienst.options"] == [
        "option 'drop_nulls' is only available with option 'shape=long' and is thus ignored in this request.",
    ]


def test_the_environment_is_no_settings_of_the_callers_to_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `WD_TS_*` the operator set is in the settings too, and does not count against options the caller passes."""
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", '{"temperature": "degree_fahrenheit"}')

    assert _request(options=Options(shape="long")).options.shape == "long"
    assert _request(options={"humanize": False}).options.shape == "wide"


def test_stations_result_has_the_options_of_its_request() -> None:
    """The result of a request carries its options, which the values read."""
    request = _request(options={"humanize": False})
    stations = StationsResult(
        request=request,
        df=pl.DataFrame(),
        _df_all=pl.DataFrame(),
        _stations_filter=StationsFilter.ALL,
    )

    assert stations.options is request.options
    assert stations.values().sr.options.humanize is False


def test_the_settings_of_a_request_are_the_hosts_alone_for_options() -> None:
    """Options are not read from `settings` once given: the request reads them from `options` only."""
    request = _request(settings=Settings(cache_disable=True), options={"shape": "wide"})
    assert not [name for name in Settings.model_fields if name.startswith("ts_")]
    assert not [name for name in request.settings.model_dump() if name.startswith("ts_")]
    assert request.options.shape == "wide"


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


@pytest.mark.parametrize("name", CARRIED)
def test_a_ts_setting_is_refused_with_the_option_to_use(name: str) -> None:
    """`Settings(ts_x=v)` is an error that says to pass `options=` instead (GH-3128)."""
    with pytest.raises(ValidationError, match=rf"ts_{name} is no setting.*options=Options\({name}=\.\.\.\)"):
        Settings(cache_disable=True, **{f"ts_{name}": CARRIED[name]})


def test_the_ts_settings_given_together_are_all_named() -> None:
    """Every `ts_*` setting given is named, and the option to pass for each."""
    with pytest.raises(
        ValidationError, match=r"ts_humanize, ts_shape are no settings.*Options\(humanize=\.\.\., shape="
    ) as error:
        Settings(ts_shape="wide", ts_humanize=False)
    assert "input_value" not in str(error.value)


def test_a_ts_setting_in_the_settings_of_a_request_is_refused() -> None:
    """The `settings={...}` of a request and `Settings.model_validate` refuse a `ts_*` setting as `__init__` does."""
    with pytest.raises(ValidationError, match=r"ts_skip_empty is no setting.*options="):
        _request(settings={"cache_disable": True, "ts_skip_empty": True})
    with pytest.raises(ValidationError, match=r"ts_shape is no setting.*options="):
        Settings.model_validate({"ts_shape": "wide"})


def test_a_ts_setting_is_neither_assigned_nor_read() -> None:
    """The settings have no `ts_*` attribute left to read, and an assignment is refused with where to go."""
    settings = Settings(cache_disable=True)
    with pytest.raises(ValidationError, match=r"ts_shape is no setting.*options="):
        settings.ts_shape = "wide"  # ty: ignore[invalid-assignment]
    with pytest.raises(AttributeError):
        _ = settings.ts_shape  # ty: ignore[unresolved-attribute]
    assert not hasattr(settings, "ts_tidy")


def test_the_ts_variables_of_the_environment_are_options_and_never_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_TS_*` is read by `Options` alone: it warns nowhere, and the settings do not read or refuse it."""
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = Settings(cache_disable=True)
        request = _request(settings=settings)
    assert request.options.shape == "wide"
    monkeypatch.setenv("WD_TS_SHAPE", "bogus")
    assert Settings(cache_disable=True).cache_disable


def test_a_ts_setting_that_never_existed_is_still_refused() -> None:
    """Only the `ts_*` settings that existed are taken; another is the unknown setting it is."""
    with pytest.raises(ValidationError, match="ts_nope"):
        Settings(ts_nope=1)
