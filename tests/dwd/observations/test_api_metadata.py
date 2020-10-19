from wetterdienst.dwd.observations import DWDObservationMetadata
from wetterdienst.dwd.observations.metadata import (
    DWDObsPeriodType,
    DWDObsTimeResolution,
    DWDObsParameterSet,
)


def test_dwd_observation_metadata_discover_parameters():

    parameters = DWDObservationMetadata(
        parameter=DWDObsParameterSet.CLIMATE_SUMMARY,
        time_resolution=DWDObsTimeResolution.DAILY,
    ).discover_parameters()

    assert parameters == {
        str(DWDObsTimeResolution.DAILY): {
            str(DWDObsParameterSet.CLIMATE_SUMMARY): [
                str(DWDObsPeriodType.HISTORICAL),
                str(DWDObsPeriodType.RECENT),
            ]
        }
    }


def test_dwd_observation_metadata_describe_fields_kl_daily():

    metadata = DWDObservationMetadata(
        parameter=DWDObsParameterSet.CLIMATE_SUMMARY,
        time_resolution=DWDObsTimeResolution.DAILY,
        period_type=DWDObsPeriodType.RECENT,
    )

    assert list(metadata.describe_fields().keys()) == [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN_3",
        "FX",
        "FM",
        "QN_4",
        "RSK",
        "RSKF",
        "SDK",
        "SHK_TAG",
        "NM",
        "VPM",
        "PM",
        "TMK",
        "UPM",
        "TXK",
        "TNK",
        "TGK",
    ]


def test_dwd_observation_metadata_describe_fields_solar_hourly():

    metadata = DWDObservationMetadata(
        parameter=DWDObsParameterSet.SOLAR,
        time_resolution=DWDObsTimeResolution.HOURLY,
        period_type=DWDObsPeriodType.RECENT,
    )

    assert list(metadata.describe_fields().keys()) == [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN_592",
        "ATMO_STRAHL",
        "FD_STRAHL",
        "FG_STRAHL",
        "SD_STRAHL",
        "ZENITH",
    ]


def test_dwd_observation_metadata_describe_fields_temperature_10minutes():

    metadata = DWDObservationMetadata(
        parameter=DWDObsParameterSet.TEMPERATURE_AIR,
        time_resolution=DWDObsTimeResolution.MINUTE_10,
        period_type=DWDObsPeriodType.RECENT,
    )

    assert list(metadata.describe_fields().keys()) == [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN",
        "PP_10",
        "TT_10",
        "TM5_10",
        "RF_10",
        "TD_10",
    ]
