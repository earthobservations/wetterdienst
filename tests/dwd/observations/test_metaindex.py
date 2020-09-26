""" tests for file index creation """
import requests
import pytest
from pandas import Timestamp

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.period_type import PeriodType


@pytest.mark.remote
def test_meta_index_creation():

    # Existing combination of parameters
    meta_index = create_meta_index_for_climate_observations(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL
    )

    assert not meta_index.empty

    # todo: replace IndexError with UrlError/WrongSetOfParametersError
    with pytest.raises(requests.exceptions.HTTPError):
        create_meta_index_for_climate_observations(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
        )


@pytest.mark.remote
def test_meta_index_1mph_creation():

    meta_index_1mph = create_meta_index_for_climate_observations(
        Parameter.PRECIPITATION, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
    )

    assert meta_index_1mph.loc[
        meta_index_1mph[DWDMetaColumns.STATION_ID.value] == 3, :
    ].values.tolist() == [
        [
            3,
            Timestamp("18910101"),
            Timestamp("20120406"),
            202.00,
            50.7827,
            6.0941,
            "Aachen",
            "Nordrhein-Westfalen",
        ]
    ]
