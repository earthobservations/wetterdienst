from wetterdienst import DWDObservationMetadata, TimeResolution, Parameter, PeriodType


def test_dwd_observation_metadata_discover_parameters():

    parameters = DWDObservationMetadata(
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
    ).discover_parameters()

    assert parameters == {
        str(TimeResolution.DAILY): {
            str(Parameter.CLIMATE_SUMMARY): [
                str(PeriodType.HISTORICAL),
                str(PeriodType.RECENT),
            ]
        }
    }


def test_dwd_observation_metadata_describe_fields_kl_daily():

    metadata = DWDObservationMetadata(
        parameter=Parameter.CLIMATE_SUMMARY,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
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
        parameter=Parameter.SOLAR,
        time_resolution=TimeResolution.HOURLY,
        period_type=PeriodType.RECENT,
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
        parameter=Parameter.TEMPERATURE_AIR,
        time_resolution=TimeResolution.MINUTE_10,
        period_type=PeriodType.RECENT,
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
