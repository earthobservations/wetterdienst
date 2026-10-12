"""A caller's script, type-checked by `tests/test_typed_surface.py`.

It is never run. It uses the public API the way the README and the documented examples do and states
with `assert_type` what a type checker is to make of each result, so a change that turns one into
`Any` or into something a caller must cast shows up as a diagnostic on the line that says what the
caller expected. ty reads the package from `src/` as first-party code, so what depends on the marker
or on `__all__` is held up by the tests beside it, not by this script.
"""

from __future__ import annotations

from typing import Any, Literal, assert_type

import polars as pl

from wetterdienst import Options, Period, Resolution, Settings, Wetterdienst
from wetterdienst.model.history import TimeseriesHistory
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsResult,
    SummarizedValuesResult,
    ValuesResult,
)
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest

# settings (the host's) and options (the request's) are accepted as the model or as a dict of its fields
settings = Settings(cache_disable=True)
request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "precipitation_amount")],
    start="2002-08-11",
    end="2002-08-13",
    settings=settings,
    options=Options(humanize=True),
)
assert_type(request, DwdObservationRequest)
DwdObservationRequest(
    parameters="daily/climate_summary", periods=["historical", Period.RECENT], settings={}, options={}
)

# the request class of a provider, looked up by name
api = Wetterdienst.resolve("dwd", "observation")
assert_type(api, type[TimeseriesRequest])

# stations
stations = request.filter_by_station_id(station_id=(5779,))
assert_type(stations, StationsResult)
assert_type(stations.df, pl.DataFrame)
assert_type(request.all(), StationsResult)
assert_type(request.filter_by_name("Zinnwald"), StationsResult)
assert_type(request.filter_by_rank(latlon=(50.7, 13.7), rank=3), StationsResult)
assert_type(request.filter_by_distance(latlon=(50.7, 13.7), distance=30, unit="km"), StationsResult)
assert_type(request.filter_by_bbox(left=13.0, bottom=50.0, right=14.0, top=51.0), StationsResult)
assert_type(request.filter_by_sql("station_id = '05779'"), StationsResult)
assert_type(stations.to_json(), str)
assert_type(stations.to_csv(), str)
assert_type(stations.to_geojson(), str)
assert_type(stations.to_dict()["stations"][0]["station_id"], str)
assert_type(stations.to_ogc_feature_collection()["data"]["type"], Literal["FeatureCollection"])

# values
values_request = stations.values
assert_type(values_request, TimeseriesValues)
values = values_request.all()
assert_type(values, ValuesResult)
assert_type(values.df, pl.DataFrame)
assert_type(values.df_stations, pl.DataFrame)
assert_type(values.to_json(with_metadata=True), str)
assert_type(values.to_csv(), str)
values.to_dict(with_stations=True)["values"]
assert_type(values.to_ogc_feature_collection()["data"]["type"], Literal["FeatureCollection"])
assert_type(values.filter_by_date("2002-08"), pl.DataFrame)
assert_type(values.to_image(fmt="png"), bytes | str)
values.to_target("sqlite:///values.db?table=values", if_exists="replace")
for chunk in values_request.query():
    assert_type(chunk, ValuesResult)

# history
assert_type(stations.history, TimeseriesHistory)

# a point between stations
interpolated = request.interpolate(latlon=(50.7, 13.7))
assert_type(interpolated, InterpolatedValuesResult)
assert_type(interpolated.df, pl.DataFrame)
assert_type(interpolated.to_dict()["values"][0]["taken_station_ids"], list[str])
summarized = request.summarize(latlon=(50.7, 13.7))
assert_type(summarized, SummarizedValuesResult)
assert_type(summarized.to_dict()["values"][0]["distance"], float | None)

# metadata
assert_type(request.discover(resolutions="daily"), dict[str, Any])
assert_type(Resolution("daily"), Resolution)

# how the values of a request come back
options = Options(shape="wide")
assert_type(options.shape, Literal["wide", "long"])
assert_type(options.replace(shape="long"), Options)

# whether a provider that needs credentials has them, and accepts them
assert_type(Wetterdienst.is_configured(api), bool)
assert_type(Wetterdienst.is_valid(api), bool | None)
