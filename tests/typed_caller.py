"""A caller's script, type-checked by `tests/test_typed_surface.py`.

It is never run. It uses the public API the way the README and the documented examples do and states
with `assert_type` what a type checker is to make of each result, so a change that turns one into
`Any` or into something a caller must cast shows up as a diagnostic on the line that says what the
caller expected. Run against the checkout, ty reads the package from `src/` as first-party code;
`check_installed_typing.py` runs this script against the installed wheel, where ty reads the
installed annotations. ty reads them whether or not `py.typed` is there and whatever `__all__` says,
which mypy and pyright do not, so those two are held up by the wheel listing in that script and by
`test_a_package_that_imports_names_exports_them`.
"""

from __future__ import annotations

from typing import Any, Literal, assert_type

import polars as pl

from wetterdienst import (
    ConfigurationError,
    Info,
    NotFoundError,
    Options,
    Period,
    RequestError,
    Resolution,
    Settings,
    UpstreamError,
    Wetterdienst,
    WetterdienstError,
)
from wetterdienst.model.history import TimeseriesHistory
from wetterdienst.model.metadata import CoverageNetwork, CoverageResolution, DatasetModel, MetadataModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.result import (
    HistoryDict,
    InterpolatedValuesDict,
    InterpolatedValuesOgcFeatureCollection,
    InterpolatedValuesResult,
    ResultMetadata,
    StationsDict,
    StationsOgcFeatureCollection,
    StationsResult,
    SummarizedValuesDict,
    SummarizedValuesOgcFeatureCollection,
    SummarizedValuesResult,
    ValuesDict,
    ValuesOgcFeatureCollection,
    ValuesResult,
)
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.provider.dwd.radar import DwdRadarValues

# settings (the host's) and options (the request's) are accepted as the model or as a dict of its fields
settings = Settings(cache_disable=True)
Settings(cache_dir="cache", auth={"knmi": "api-key"}, fsspec_client_kwargs={"trust_env": True})
Settings(**settings.model_dump())

# the fields of the settings are checked by name and by type, as those of the options are
Settings(cache_dsable=True)  # ty: ignore[unknown-argument]
Settings(ts_shape="wide")  # ty: ignore[unknown-argument]  # an option of the request since GH-2639: options=
Settings(cache_disable="yes")  # ty: ignore[invalid-argument-type]
Options(shap="wide")  # ty: ignore[unknown-argument]
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

# dwd/radar and dwd/alerts are no timeseries networks, and are resolved by their own entry point, to
# the exact class where the names are literals
assert_type(Wetterdienst.resolve_standalone("dwd", "radar"), type[DwdRadarValues])
assert_type(Wetterdienst.resolve_standalone("dwd", "alerts"), type[DwdWeatherAlertRequest])


def resolve_by_name(provider_name: str, network_name: str) -> None:
    """Resolve a standalone network by names that are not literals."""
    assert_type(
        Wetterdienst.resolve_standalone(provider_name, network_name),
        type[DwdRadarValues] | type[DwdWeatherAlertRequest],
    )


assert_type(Wetterdienst.is_standalone("dwd", "radar"), bool)

# stations
stations = request.filter_by_station_id(station_id=(5779,))
assert_type(stations, StationsResult)
assert_type(stations.df, pl.DataFrame)
assert_type(stations.request, TimeseriesRequest)
assert_type(stations.filtered_by_sql("station_id = '05779'"), StationsResult)
assert_type(request.all(), StationsResult)
assert_type(request.filter_by_name("Zinnwald"), StationsResult)
assert_type(request.filter_by_rank(latlon=(50.7, 13.7), rank=3), StationsResult)
assert_type(request.filter_by_distance(latlon=(50.7, 13.7), distance=30, unit="km"), StationsResult)
assert_type(request.filter_by_bbox(left=13.0, bottom=50.0, right=14.0, top=51.0), StationsResult)
assert_type(request.filter_by_sql("station_id = '05779'"), StationsResult)
assert_type(stations.to_json(), str)
assert_type(stations.to_csv(), str)
assert_type(stations.to_geojson(), str)
assert_type(stations.to_geojson(with_metadata=True, indent=2), str)
assert_type(stations.to_dict()["stations"][0]["station_id"], str)
assert_type(stations.to_ogc_feature_collection()["data"]["type"], Literal["FeatureCollection"])

# the dictionaries of the results are importable by name, to annotate a function that takes or returns one
assert_type(stations.to_dict(), StationsDict)
assert_type(stations.to_ogc_feature_collection(), StationsOgcFeatureCollection)
assert_type(stations.to_dict(with_metadata=True)["metadata"], ResultMetadata)


def station_ids(document: StationsDict) -> list[str]:
    """Read the ids of a stations document, as a caller's own function would."""
    return [station["station_id"] for station in document["stations"]]


assert_type(station_ids(stations.to_dict()), list[str])

# a typo in the argument of a formatter is an error where it is made, not a different document
stations.to_geojson(with_metdata=True)  # ty: ignore[unknown-argument]
stations.to_ogc_feature_collection(with_metdata=True)  # ty: ignore[unknown-argument]
stations.to_plot(anything=1)  # ty: ignore[unknown-argument]

# values
values_request = stations.values()
assert_type(values_request, TimeseriesValues)
values = values_request.all()
assert_type(values, ValuesResult)
assert_type(values.df, pl.DataFrame)
assert_type(values.df_stations, pl.DataFrame)
assert_type(values.to_json(with_metadata=True), str)
assert_type(values.to_csv(), str)
values.to_dict(with_stations=True)["values"]
assert_type(values.to_dict(), ValuesDict)
assert_type(values.to_ogc_feature_collection(), ValuesOgcFeatureCollection)
assert_type(values.to_ogc_feature_collection()["data"]["type"], Literal["FeatureCollection"])
assert_type(values.filtered_by_date("2002-08"), ValuesResult)
assert_type(values.filtered_by_sql("value > 1"), ValuesResult)
assert_type(values.to_image(fmt="png"), bytes | str)
values.to_target("sqlite:///values.db?table=values", if_exists="replace")
for chunk in values_request.query():
    assert_type(chunk, ValuesResult)

# history
assert_type(stations.history(), TimeseriesHistory)
assert_type(stations.history().to_json(), str)
assert_type(stations.history().to_dict()["histories"], list[dict[str, Any]])
assert_type(stations.history().to_dict(), HistoryDict)

# a point between stations
interpolated = request.interpolate(latlon=(50.7, 13.7))
assert_type(interpolated, InterpolatedValuesResult)
assert_type(interpolated.df, pl.DataFrame)
assert_type(interpolated.to_dict()["values"][0]["taken_station_ids"], list[str])
assert_type(interpolated.to_dict(), InterpolatedValuesDict)
assert_type(interpolated.to_ogc_feature_collection(), InterpolatedValuesOgcFeatureCollection)
summarized = request.summarize(latlon=(50.7, 13.7))
assert_type(summarized, SummarizedValuesResult)
assert_type(summarized.to_dict()["values"][0]["distance"], float | None)
assert_type(summarized.to_dict(), SummarizedValuesDict)
assert_type(summarized.to_ogc_feature_collection(), SummarizedValuesOgcFeatureCollection)

# a forecast, whose request takes an issue
mosmix = DwdMosmixRequest(parameters="hourly/small", issue="latest")
assert_type(mosmix.all().request, TimeseriesRequest)

# metadata
assert_type(request.metadata, MetadataModel)
assert_type(DwdObservationMetadata, MetadataModel)
assert_type(DwdObservationMetadata["daily"]["climate_summary"], DatasetModel)
assert_type(request.discover(resolutions="daily"), dict[str, CoverageResolution])
assert_type(request.discover()["daily"]["datasets"]["climate_summary"]["parameters"][0]["unit"], str)
assert_type(Wetterdienst.discover(), dict[str, dict[str, CoverageNetwork]])
assert_type(Wetterdienst.discover()["dwd"]["observation"]["auth"], bool)
assert_type(Wetterdienst.get_provider_names(), list[str])
assert_type(Resolution("daily"), Resolution)
assert_type(Info().to_dict()["version"], str)

# how the values of a request come back
options = Options(shape="wide")
assert_type(options.shape, Literal["wide", "long"])
assert_type(options.replace(shape="long"), Options)

# whether a provider that needs credentials has them, and accepts them
assert_type(Wetterdienst.is_configured(api), bool)
assert_type(Wetterdienst.is_valid(api), bool | None)


# the exceptions a call raises share a root, and a caller catches them by what to do about them
try:
    request.all().values().all()
except (RequestError, NotFoundError) as error:
    assert_type(error, RequestError | NotFoundError)
except (ConfigurationError, UpstreamError) as error:
    assert_type(error, ConfigurationError | UpstreamError)
except WetterdienstError as error:
    assert_type(error, WetterdienstError)
