from wetterdienst import DWDObservationMetadata, TimeResolution, Parameter, PeriodType


def test_dwd_observation_metadata_discover_parameters():
    parameters = DWDObservationMetadata.discover_parameters(
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
    )
    assert parameters == {
        str(TimeResolution.DAILY): {
            str(Parameter.CLIMATE_SUMMARY): [
                str(PeriodType.HISTORICAL),
                str(PeriodType.RECENT),
            ]
        }
    }
