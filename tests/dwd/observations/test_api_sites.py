import pytest
from pandas import Timestamp

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations.metadata import (
    DWDObsParameterSet,
    DWDObsPeriodType,
    DWDObsTimeResolution,
)
from wetterdienst.dwd.observations.api import DWDObservationSites
from wetterdienst.exceptions import InvalidParameterCombination


@pytest.mark.remote
def test_dwd_observation_sites_success():

    # Existing combination of parameters
    sites = DWDObservationSites(
        DWDObsParameterSet.CLIMATE_SUMMARY,
        DWDObsTimeResolution.DAILY,
        DWDObsPeriodType.HISTORICAL,
    ).all()

    assert not sites.empty

    assert sites.loc[
        sites[DWDMetaColumns.STATION_ID.value] == 1, :
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
        ]
    ]


def test_dwd_observation_sites_fail():
    with pytest.raises(InvalidParameterCombination):
        DWDObservationSites(
            DWDObsParameterSet.CLIMATE_SUMMARY,
            DWDObsTimeResolution.MINUTE_1,
            DWDObsPeriodType.HISTORICAL,
        ).all()


@pytest.mark.remote
def test_dwd_observation_sites_geojson():

    # Existing combination of parameters
    df = DWDObservationSites(
        DWDObsParameterSet.CLIMATE_SUMMARY,
        DWDObsTimeResolution.DAILY,
        DWDObsPeriodType.HISTORICAL,
    ).all()

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
