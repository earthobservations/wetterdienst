from wetterdienst.file_path_handling.file_list_creation import (
    create_file_list_for_climate_observations,
)
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.parameter_enumeration import Parameter


def test_create_file_list_for_dwd_server():
    remote_file_path = create_file_list_for_climate_observations(
        station_ids=[1048],
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
    )
    assert remote_file_path == ["daily/kl/recent/tageswerte_KL_01048_akt.zip"]
