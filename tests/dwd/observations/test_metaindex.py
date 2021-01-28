""" tests for file index creation """
import pytest
import requests

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations import DWDObservationParameterSet
from wetterdienst.dwd.observations.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


@pytest.mark.remote
def test_meta_index_creation():

    # Existing combination of parameters
    meta_index = create_meta_index_for_climate_observations(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        Resolution.DAILY,
        Period.HISTORICAL,
    )

    assert not meta_index.empty

    with pytest.raises(requests.exceptions.HTTPError):
        create_meta_index_for_climate_observations(
            DWDObservationParameterSet.CLIMATE_SUMMARY,
            Resolution.MINUTE_1,
            Period.HISTORICAL,
        )


@pytest.mark.remote
def test_meta_index_1mph_creation():

    meta_index_1mph = create_meta_index_for_climate_observations(
        DWDObservationParameterSet.PRECIPITATION,
        Resolution.MINUTE_1,
        Period.HISTORICAL,
    )

    assert meta_index_1mph.loc[
        meta_index_1mph[DWDMetaColumns.STATION_ID.value] == "00003", :
    ].values.tolist() == [
        [
            "00003",
            "18910101",
            "20120406",
            "202.00",
            "50.7827",
            "6.0941",
            "Aachen",
            "Nordrhein-Westfalen",
        ]
    ]
