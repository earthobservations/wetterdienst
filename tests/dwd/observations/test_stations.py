import pytest
import requests
from pandas import Timestamp

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst import metadata_for_climate_observations, TimeResolution
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.dwd.metadata.period_type import PeriodType


@pytest.mark.remote
def test_metadata_for_climate_observations():

    # Existing combination of parameters
    metadata = metadata_for_climate_observations(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )

    assert not metadata.empty

    assert metadata.loc[
        metadata[DWDMetaColumns.STATION_ID.value] == 1, :
    ].values.tolist() == [
        [
            1,
            Timestamp("19370101"),
            Timestamp("19860630"),
            478.0,
            47.8413,
            8.8493,
            "Aach",
            "Baden-Württemberg",
            True,
        ]
    ]

    # todo: replace IndexError with UrlError/WrongSetOfParametersError
    with pytest.raises(requests.exceptions.HTTPError):
        metadata_for_climate_observations(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
        )


@pytest.mark.remote
def test_metadata_geojson():

    # Existing combination of parameters
    df = metadata_for_climate_observations(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )

    assert not df.empty

    df = df[df[DWDMetaColumns.STATION_ID.value] == 1]

    geojson = df.dwd.to_geojson()

    properties = geojson["features"][0]["properties"]
    geometry = geojson["features"][0]["geometry"]

    assert properties["name"] == "Aach"
    assert properties["state"] == "Baden-Württemberg"

    assert geometry == {
        "type": "Point",
        "coordinates": [8.8493, 47.8413, 478.0],
    }
