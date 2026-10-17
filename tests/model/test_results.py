# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The result classes: what they hold, what they refuse and that they stay as they were built (GH-2626)."""

import dataclasses
import datetime as dt
import inspect
import re

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.model import result as result_module
from wetterdienst.model.history import TimeseriesHistory
from wetterdienst.model.result import (
    HistoryResult,
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
    ValuesResult,
)
from wetterdienst.model.schema import LONG_SCHEMA, STATIONS_SCHEMA
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest


def _stations_frame() -> pl.DataFrame:
    rows = [
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": station_id,
            "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
            "end_timestamp": None,
            "latitude": 51.0 + index,
            "longitude": 13.0,
            "elevation": 228.0,
            "name": name,
            "region": "Sachsen",
        }
        for index, (station_id, name) in enumerate([("01048", "Dresden-Klotzsche"), ("00044", "Großenhain")])
    ]
    return pl.DataFrame(rows, schema=STATIONS_SCHEMA)


def _stations() -> StationsResult:
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")], settings=Settings(cache_disable=True)
    )
    df = _stations_frame()
    return StationsResult(request=request, df=df, df_all=df, stations_filter=StationsFilter.BY_STATION_ID)


def _values_frame(station_ids: tuple[str, ...] = ("01048",)) -> pl.DataFrame:
    rows = [
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "station_id": station_id,
            "timestamp": dt.datetime(2020, month, 1, tzinfo=dt.UTC),
            "value": float(month),
            "quality_flags": None,
        }
        for station_id in station_ids
        for month in (1, 2, 3)
    ]
    return pl.DataFrame(rows, schema=LONG_SCHEMA)


_RESULTS = (StationsResult, ValuesResult, InterpolatedValuesResult, SummarizedValuesResult, HistoryResult)


def _every_result() -> dict[str, object]:
    stations = _stations()
    df = _values_frame()
    return {
        "stations": stations,
        "values": ValuesResult(stations=stations, df=df),
        "interpolated": InterpolatedValuesResult(stations=stations, df=df, latlon=(51.0, 13.0)),
        "summarized": SummarizedValuesResult(stations=stations, df=df, latlon=(51.0, 13.0)),
        "history": HistoryResult(stations=stations, history=None),  # ty: ignore[invalid-argument-type]
    }


def test_the_request_of_a_stations_result_is_called_request() -> None:
    """The attribute that held the request is named for it, and the stations are `df`."""
    stations = _stations()
    assert isinstance(stations.request, DwdObservationRequest)
    assert stations.df.get_column("station_id").to_list() == ["01048", "00044"]
    # read through the request, as the properties always did
    assert stations.settings is stations.request.settings
    assert stations.parameters == stations.request.parameters


def test_the_old_name_of_the_request_fails_with_the_new_one() -> None:
    """`.stations` and the `stations=` argument of a stations result say they are `request` now."""
    stations = _stations()
    with pytest.raises(AttributeError, match=r"StationsResult\.stations was renamed to 'request'"):
        _ = stations.stations  # ty: ignore[unresolved-attribute]
    with pytest.raises(TypeError, match=r"StationsResult\.stations was renamed to 'request'"):
        StationsResult(  # ty: ignore[unknown-argument]
            stations=stations.request, df=stations.df, df_all=stations.df, stations_filter=StationsFilter.ALL
        )


def test_the_values_of_a_result_do_not_hold_the_reader_that_produced_them() -> None:
    """A values result is the stations and the frame, so that a kept result keeps no downloader alive."""
    assert [field.name for field in dataclasses.fields(ValuesResult)] == ["df", "stations"]
    stations = _stations()
    with pytest.raises(AttributeError, match=r"ValuesResult\.values is gone.*stations\.values\(\)"):
        _ = ValuesResult(stations=stations, df=_values_frame()).values  # ty: ignore[unresolved-attribute]
    with pytest.raises(TypeError, match=r"ValuesResult\.values is gone.*stations\.values\(\)"):
        ValuesResult(stations=stations, values=None, df=_values_frame())  # ty: ignore[unknown-argument]


def test_values_and_history_of_stations_are_methods_that_build_a_reader() -> None:
    """They build a new reader on each call, which reading them as attributes never said."""
    stations = _stations()
    assert isinstance(stations.values(), TimeseriesValues)
    assert stations.values() is not stations.values()
    assert isinstance(stations.history(), TimeseriesHistory)
    assert stations.values().sr is stations


@pytest.mark.parametrize(
    ("read", "write"),
    [
        (lambda stations: stations.values.all, "values().all"),
        (lambda stations: stations.values.query, "values().query"),
        (lambda stations: stations.history.query, "history().query"),
    ],
)
def test_reading_values_or_history_as_an_attribute_says_to_call_it(read: object, write: str) -> None:
    """`stations.values.all()` fails with the call that replaces it, not with 'method has no attribute'."""
    with pytest.raises(AttributeError, match=re.escape(f"is a method, not an attribute: write {write}")):
        read(_stations())  # ty: ignore[call-non-callable]


def test_a_method_that_was_a_property_keeps_its_name_and_docstring() -> None:
    """Tools that read a signature or a docstring see the method, whether on the class or on a result."""
    assert inspect.signature(StationsResult.values).parameters.keys() == {"self"}
    assert StationsResult.values.__doc__
    assert "new" in (_stations().values.__doc__ or "")
    assert callable(_stations().history)


@pytest.mark.parametrize("name", ["stations", "values", "interpolated", "summarized", "history"])
def test_a_result_cannot_be_assigned_to(name: str) -> None:
    """Nothing changes a result once it is built: a holder of one sees the frame it was given."""
    result = _every_result()[name]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.df = pl.DataFrame()  # ty: ignore[invalid-assignment]


def test_filtering_values_gives_a_new_result_and_leaves_the_old_one() -> None:
    """`filtered_by_date` and `filtered_by_sql` do not change what the next `to_json()` writes."""
    result = ValuesResult(stations=_stations(), df=_values_frame())
    by_date = result.filtered_by_date("2020-02")
    by_sql = result.filtered_by_sql("value > 2")
    assert isinstance(by_date, ValuesResult)
    assert by_date.df.get_column("value").to_list() == [2.0]
    assert by_sql.df.get_column("value").to_list() == [3.0]
    assert by_date.stations is result.stations
    assert result.df.height == 3, "the result the filter was asked on is as it was"


@pytest.mark.parametrize("name", ["interpolated", "summarized"])
def test_filtering_an_interpolated_or_summarized_result_keeps_its_point(name: str) -> None:
    """The new result is of the same kind and place as the one it comes from."""
    result = _every_result()[name]
    filtered = result.filtered_by_sql("value > 2")  # ty: ignore[unresolved-attribute]
    assert type(filtered) is type(result)
    assert filtered.latlon == result.latlon
    assert filtered.df.height == 1
    assert result.df.height == 3


def test_filtering_stations_by_sql_gives_a_new_result_too() -> None:
    """A stations result is filtered as a values one is."""
    stations = _stations()
    filtered = stations.filtered_by_sql("station_id = '01048'")
    assert isinstance(filtered, StationsResult)
    assert filtered.df.get_column("station_id").to_list() == ["01048"]
    assert filtered.request is stations.request
    assert stations.df.height == 2


@pytest.mark.parametrize(
    ("name", "call", "new"),
    [
        ("values", lambda result: result.filter_by_date, "filtered_by_date"),
        ("values", lambda result: result.filter_by_sql, "filtered_by_sql"),
        ("stations", lambda result: result.filter_by_sql, "filtered_by_sql"),
    ],
)
def test_the_old_filters_of_a_result_fail_with_the_new_name(name: str, call: object, new: str) -> None:
    """A caller who ignored the return value would otherwise be silently handed the unfiltered result."""
    with pytest.raises(AttributeError, match=rf"was renamed to '{new}', which returns a new result"):
        call(_every_result()[name])  # ty: ignore[call-non-callable]


def test_a_name_that_never_existed_fails_as_it_always_did() -> None:
    """The refusal of the renamed names is no net that catches every missing attribute."""
    with pytest.raises(AttributeError, match="has no attribute 'nope'"):
        _ = _stations().nope  # ty: ignore[unresolved-attribute]
    with pytest.raises(TypeError, match="unexpected keyword argument 'nope'"):
        StationsResult(  # ty: ignore[unknown-argument]
            request=None, df=pl.DataFrame(), df_all=pl.DataFrame(), stations_filter=StationsFilter.ALL, nope=1
        )


def test_every_values_result_names_the_stations_it_describes() -> None:
    """`df_stations` is on all three, and is the stations that have values."""
    stations = _stations()
    # only one of the two stations returned values
    values = ValuesResult(stations=stations, df=_values_frame(("00044",)))
    assert values.df_stations.get_column("station_id").to_list() == ["00044"]
    # a result cut down to nothing names no stations
    assert values.filtered_by_sql("value > 100").df_stations.is_empty()
    # an interpolation or a summary is of the stations it was made from, which the stations result holds already
    for kind in (InterpolatedValuesResult, SummarizedValuesResult):
        result = kind(stations=stations, df=_values_frame(), latlon=(51.0, 13.0))
        assert result.df_stations.equals(stations.df)


def _public(cls: type) -> list[str]:
    """Name what a caller may read off a class: the names that do not start with an underscore."""
    return [name for name in dir(cls) if not name.startswith("_")]


# What a caller may rely on, as `dir` and `inspect` read it. A change here is a change of the surface the
# library promises from 1.0, which is why it is pinned: it shows as a diff in a review (GH-2626, and
# the snapshot of the public surface that #2625 asks for).
_FORMATS = ["to_csv", "to_dict", "to_format", "to_geojson", "to_image", "to_json", "to_ogc_feature_collection"]
_VALUES_SURFACE = [
    "df_stations",
    "filtered_by_date",
    "filtered_by_sql",
    *_FORMATS,
    "to_plot",
    "to_target",
]


def test_the_fields_of_the_results_are_the_ones_the_library_promises() -> None:
    """What each of the five results holds, in the order it is declared (a constructor takes them by keyword)."""
    fields = {cls.__name__: [field.name for field in dataclasses.fields(cls)] for cls in _RESULTS}
    assert fields == {
        "StationsResult": ["df", "request", "df_all", "stations_filter", "rank"],
        "ValuesResult": ["df", "stations"],
        "InterpolatedValuesResult": ["df", "stations", "latlon", "elevation"],
        "SummarizedValuesResult": ["df", "stations", "latlon", "elevation"],
        "HistoryResult": ["stations", "history"],
    }


def test_the_public_methods_of_the_results_are_the_ones_the_library_promises() -> None:
    """What a caller may call on each of the five results, by name."""
    assert _public(StationsResult) == [
        "end",
        "filtered_by_sql",
        "history",
        "options",
        "parameters",
        "rank",
        "settings",
        "start",
        "station_id",
        *_FORMATS,
        "to_plot",
        "to_target",
        "values",
    ]
    assert _public(ValuesResult) == _VALUES_SURFACE
    assert _public(InterpolatedValuesResult) == sorted([*_VALUES_SURFACE, "elevation"])
    assert _public(SummarizedValuesResult) == sorted([*_VALUES_SURFACE, "elevation"])
    assert _public(HistoryResult) == ["to_dict", "to_json"]


def test_the_signatures_the_documentation_shows_are_the_ones_the_results_have() -> None:
    """The calls of the guide: the readers of a stations result and the filters of a values result."""
    signatures = {
        "StationsResult.values": inspect.signature(StationsResult.values),
        "StationsResult.history": inspect.signature(StationsResult.history),
        "ValuesResult.filtered_by_date": inspect.signature(ValuesResult.filtered_by_date),
        "ValuesResult.filtered_by_sql": inspect.signature(ValuesResult.filtered_by_sql),
        "ValuesResult.to_dict": inspect.signature(ValuesResult.to_dict),
        "ValuesResult.to_json": inspect.signature(ValuesResult.to_json),
    }
    assert {name: str(signature) for name, signature in signatures.items()} == {
        "StationsResult.values": "(self) -> 'TimeseriesValues'",
        "StationsResult.history": "(self) -> 'TimeseriesHistory'",
        "ValuesResult.filtered_by_date": "(self, date: 'str') -> 'Self'",
        "ValuesResult.filtered_by_sql": "(self, sql: 'str') -> 'Self'",
        "ValuesResult.to_dict": "(self, *, with_metadata: 'bool' = False, with_stations: 'bool' = False) -> '_DictT'",
        "ValuesResult.to_json": (
            "(self, *, with_metadata: 'bool' = False, with_stations: 'bool' = False, "
            "indent: 'int | bool | None' = 4) -> 'str'"
        ),
    }


def test_an_error_inside_a_property_of_a_result_is_the_error_that_is_raised() -> None:
    """The refusal of renamed names does not swallow what a property of the result raised itself."""
    request = type("RequestWithoutSettings", (), {})()
    stations = StationsResult(
        request=request,  # ty: ignore[invalid-argument-type]
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    with pytest.raises(AttributeError, match="RequestWithoutSettings"):
        _ = stations.settings


def test_the_methods_that_were_properties_look_like_bound_methods() -> None:
    """`repr` and `inspect.ismethod` read them as the methods they are."""
    stations = _stations()
    assert repr(stations.values).startswith("<bound method StationsResult.values of")
    assert stations.values.__self__ is stations
    assert stations.history.__func__ is StationsResult.__dict__["history"]._func  # noqa: SLF001


def test_a_values_result_with_no_station_column_names_no_stations() -> None:
    """A frame built by hand, with no `station_id`, has no stations behind it."""
    result = ValuesResult(stations=_stations(), df=pl.DataFrame())
    assert result.df_stations.is_empty()
    assert result.df_stations.columns == _stations().df.columns


@pytest.mark.parametrize("name", ["stations", "values", "interpolated", "summarized", "history"])
def test_a_result_is_constructed_by_keyword_only(name: str) -> None:
    """The order the fields come in is no part of the constructor, so a positional call is refused (GH-3044)."""
    result = _every_result()[name]
    fields = {field.name: getattr(result, field.name) for field in dataclasses.fields(result)}  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="positional argument"):
        type(result)(*fields.values())
    rebuilt = type(result)(**fields)
    assert all(getattr(rebuilt, name) is value for name, value in fields.items())


@pytest.mark.parametrize("name", ["stations", "values", "interpolated", "summarized"])
@pytest.mark.parametrize("method", ["to_dict", "to_json", "to_geojson", "to_ogc_feature_collection", "to_plot"])
def test_a_formatter_takes_no_argument_it_does_not_know(name: str, method: str) -> None:
    """A typo in `with_metadata` is an error where it is made, not a silently different document (GH-3043)."""
    result = _every_result()[name]
    parameters = inspect.signature(getattr(result, method)).parameters
    assert not any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    with pytest.raises(TypeError, match="unexpected keyword argument 'with_metdata'"):
        getattr(result, method)(with_metdata=True)


def test_to_image_refuses_a_keyword_the_image_does_not_take() -> None:
    """`to_image` passes its keywords on to the image: `fmt`, `width`, `height`, `scale`, `max_side` (GH-3043)."""
    with pytest.raises(TypeError, match="unexpected keyword argument 'wdith'"):
        _stations().to_image(fmt="html", wdith=3)  # ty: ignore[unknown-argument]


@pytest.mark.parametrize("name", ["stations", "values", "interpolated", "summarized"])
def test_to_format_gives_a_formatter_the_arguments_it_takes(name: str) -> None:
    """The one set of arguments the command line, the REST API and MCP build is cut down to each format (GH-3043)."""
    result = _every_result()[name]
    everything = {"with_metadata": True, "indent": 2, "with_stations": True, "width": 3, "height": 4, "scale": 1.0}
    assert result.to_format("json", **everything) == result.to_json(  # ty: ignore[unresolved-attribute]
        with_metadata=True, indent=2, **({"with_stations": True} if name != "stations" else {})
    )
    assert result.to_format("geojson", **everything) == result.to_geojson(with_metadata=True, indent=2)  # ty: ignore[unresolved-attribute]
    assert result.to_format("csv", **everything) == result.to_csv()  # ty: ignore[unresolved-attribute]


@pytest.mark.parametrize("name", ["stations", "values", "interpolated", "summarized"])
def test_to_format_gives_an_image_the_arguments_of_an_image(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A chart is not given the `indent` or `with_metadata` of the JSON formats (GH-3043)."""
    result = _every_result()[name]
    given: dict[str, object] = {}

    def image(
        _self: object,
        fmt: str,
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        max_side: int | None = None,
    ) -> str:
        given.update(fmt=fmt, width=width, height=height, scale=scale, max_side=max_side)
        return "image"

    monkeypatch.setattr(type(result), "_to_image", image)
    everything = {
        "with_metadata": True,
        "indent": 2,
        "with_stations": True,
        "width": 3,
        "height": 4,
        "scale": 1.5,
        "max_side": 9,
    }
    assert result.to_format("PNG", **everything) == "image"  # ty: ignore[unresolved-attribute]
    assert given == {"fmt": "png", "width": 3, "height": 4, "scale": 1.5, "max_side": 9}


def test_the_dictionaries_of_the_results_are_importable_by_a_public_name() -> None:
    """A caller annotates a function with `StationsDict` and the like, the classes the formats return (GH-3046).

    The classes keep their private names, which the REST API publishes as OpenAPI components; the
    public names are the same classes, so the components are the ones `/api/v1` freezes.
    """
    names = {
        "ResultMetadata": "_Metadata",
        "StationsDict": "_StationsDict",
        "StationsOgcFeatureCollection": "_StationsOgcFeatureCollection",
        "ValuesDict": "_ValuesDict",
        "ValuesOgcFeatureCollection": "_ValuesOgcFeatureCollection",
        "InterpolatedValuesDict": "_InterpolatedValuesDict",
        "InterpolatedValuesOgcFeatureCollection": "_InterpolatedValuesOgcFeatureCollection",
        "SummarizedValuesDict": "_SummarizedValuesDict",
        "SummarizedValuesOgcFeatureCollection": "_SummarizedValuesOgcFeatureCollection",
        "HistoryDict": "_HistoryDict",
    }
    for public, private in names.items():
        assert getattr(result_module, public) is getattr(result_module, private), public
        assert public in result_module.__all__
    assert sorted(set(result_module.__all__) - set(names)) == [
        "HistoryResult",
        "InterpolatedValuesResult",
        "StationsFilter",
        "StationsResult",
        "SummarizedValuesResult",
        "ValuesResult",
    ]


# ----- equality (GH-3037): a result is equal to another of its class that holds the same, and is unhashable


@pytest.mark.parametrize("name", ["stations", "values", "interpolated", "summarized", "history"])
def test_results_that_hold_the_same_are_equal(name: str) -> None:
    """Two results built apart, of equal frames, compare equal: the generated `__eq__` raised on the frames."""
    first, second = _every_result()[name], _every_result()[name]
    assert first is not second
    assert first == second
    assert not first != second  # noqa: SIM202


@pytest.mark.parametrize("name", ["stations", "values", "interpolated", "summarized", "history"])
def test_a_result_is_unhashable(name: str) -> None:
    """It holds frames, which are unhashable, so it is no key and no member of a set (the same on all five)."""
    result = _every_result()[name]
    assert type(result).__hash__ is None
    with pytest.raises(TypeError, match="unhashable"):
        hash(result)


@pytest.mark.parametrize(
    ("name", "other"),
    [
        pytest.param("values", lambda result: ValuesResult(stations=result.stations, df=result.df.head(2)), id="rows"),
        pytest.param(
            "values",
            lambda result: ValuesResult(stations=result.stations, df=result.df.with_columns(pl.col("value") + 1)),
            id="values",
        ),
        pytest.param(
            "values",
            lambda result: ValuesResult(stations=result.stations, df=result.df.reverse()),
            id="row-order",
        ),
        pytest.param(
            "values",
            lambda result: ValuesResult(
                stations=result.stations, df=result.df.with_columns(pl.col("value").cast(pl.Float32))
            ),
            id="dtype",
        ),
        pytest.param(
            "values",
            lambda result: ValuesResult(stations=result.stations.filtered_by_sql("station_id = '01048'"), df=result.df),
            id="stations",
        ),
        pytest.param(
            "stations",
            lambda result: dataclasses.replace(result, stations_filter=StationsFilter.ALL),
            id="stations-filter",
        ),
        pytest.param("stations", lambda result: dataclasses.replace(result, rank=3), id="rank"),
        pytest.param(
            "stations",
            lambda result: dataclasses.replace(result, df_all=result.df_all.head(1)),
            id="df-all",
        ),
        pytest.param(
            "stations",
            lambda result: dataclasses.replace(
                result, request=DwdObservationRequest(parameters="daily/kl", settings=Settings(cache_disable=True))
            ),
            id="request",
        ),
        pytest.param("interpolated", lambda result: dataclasses.replace(result, latlon=(51.0, 14.0)), id="latlon"),
        pytest.param("summarized", lambda result: dataclasses.replace(result, elevation=200.0), id="elevation"),
    ],
)
def test_results_that_differ_in_a_field_are_unequal(name: str, other: object) -> None:
    """Every field counts: rows, order, values, dtypes, the stations, the request and the point."""
    result = _every_result()[name]
    assert result == _every_result()[name]
    assert result != other(result)  # ty: ignore[call-non-callable]


def test_results_of_different_classes_are_unequal_even_when_they_hold_the_same() -> None:
    """The same stations and frame in a values, an interpolated and a summarized result are three results."""
    results = _every_result()
    assert results["interpolated"] != results["summarized"]
    assert results["values"] != results["interpolated"]
    assert results["values"] != results["stations"]
    assert results["values"] != 1
    # `NotImplemented` and not False, so that the other side gets to answer
    assert results["values"].__eq__(results["stations"]) is NotImplemented


def test_nulls_and_nans_in_a_frame_do_not_make_a_result_unequal_to_itself() -> None:
    """A null equals a null and a NaN a NaN, as in `DataFrame.equals`: a result with gaps equals its twin."""
    frame = _values_frame().with_columns(
        value=pl.Series([None, float("nan"), 3.0], dtype=pl.Float64),
    )
    first = ValuesResult(stations=_stations(), df=frame)
    assert first == ValuesResult(stations=_stations(), df=frame.clone())
