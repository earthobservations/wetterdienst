""" tests for file index creation """
import pytest
import requests

from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.indexing.file_index_creation import (
    create_file_index_for_climate_observations,
)
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.period_type_enumeration import PeriodType


@pytest.mark.remote
def test_file_index_creation():

    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.RECENT
    )

    assert not file_index.empty

    assert (
        file_index.loc[
            file_index[DWDMetaColumns.STATION_ID.value] == 1048,
            DWDMetaColumns.FILENAME.value,
        ].values.tolist()
        == ["daily/kl/recent/tageswerte_KL_01048_akt.zip"]
    )

    with pytest.raises(requests.exceptions.HTTPError):
        create_file_index_for_climate_observations(
            Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
        )
