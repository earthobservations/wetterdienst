from wetterdienst.dwd.observations import (
    DWDObservationMetadata,
    DWDObservationPeriod,
    DWDObservationResolution,
    DWDObservationParameterSet,
)


def test_dwd_observation_metadata_discover_parameters():

    parameters = DWDObservationMetadata(
        parameter_set=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
    ).discover_parameter_sets()

    assert parameters == {
        str(DWDObservationResolution.DAILY): {
            str(DWDObservationParameterSet.CLIMATE_SUMMARY): [
                str(DWDObservationPeriod.HISTORICAL),
                str(DWDObservationPeriod.RECENT),
            ]
        }
    }


def test_dwd_observation_metadata_describe_fields_kl_daily():

    metadata = DWDObservationMetadata(
        parameter_set=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.RECENT,
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
        parameter_set=DWDObservationParameterSet.SOLAR,
        resolution=DWDObservationResolution.HOURLY,
        period=DWDObservationPeriod.RECENT,
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
        parameter_set=DWDObservationParameterSet.TEMPERATURE_AIR,
        resolution=DWDObservationResolution.MINUTE_10,
        period=DWDObservationPeriod.RECENT,
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
