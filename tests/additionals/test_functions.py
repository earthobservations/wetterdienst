import pytest
import numpy as np
import pandas as pd

from wetterdienst.additionals.functions import (
    check_parameters,
    parse_enumeration_from_template,
    create_humanized_column_names_mapping,
    coerce_field_types,
)
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.exceptions import InvalidParameter


def test_check_parameters():
    assert check_parameters(
        Parameter.PRECIPITATION, TimeResolution.MINUTES_10, PeriodType.HISTORICAL
    )
    assert not check_parameters(
        Parameter.CLIMATE_SUMMARY, TimeResolution.MINUTE_1, PeriodType.HISTORICAL
    )


def test_parse_enumeration_from_template():
    assert (
        parse_enumeration_from_template("climate_summary", Parameter)
        == Parameter.CLIMATE_SUMMARY
    )
    assert parse_enumeration_from_template("kl", Parameter) == Parameter.CLIMATE_SUMMARY

    with pytest.raises(InvalidParameter):
        parse_enumeration_from_template("climate", Parameter)


def test_coerce_field_types():
    df = pd.DataFrame(
        {
            "QN": ["1"],
            "RS_IND_01": ["1"],
            "DATE": ["1970010100"],
            "END_OF_INTERVAL": ["1970010100:00"],
            "V_VV_I": ["P"],
        }
    )

    expected_df = pd.DataFrame(
        {
            "QN": pd.Series([1], dtype=np.int32),
            "RS_IND_01": pd.Series([1], dtype=np.int32),
            "DATE": [pd.Timestamp("1970-01-01")],
            "END_OF_INTERVAL": [pd.Timestamp("1970-01-01")],
            "V_VV_I": ["P"],
        }
    )

    assert (
        coerce_field_types(df, TimeResolution.HOURLY).values.tolist()
        == expected_df.values.tolist()
    )


def test_create_humanized_column_names_mapping():
    """ Test for function to create a mapping to humanized column names """
    hcnm = create_humanized_column_names_mapping(
        TimeResolution.DAILY, Parameter.CLIMATE_SUMMARY
    )

    assert hcnm == {
        "QN_3": "QUALITY_WIND",
        "FX": "WIND_GUST_MAX",
        "FM": "WIND_VELOCITY",
        "QN_4": "QUALITY_GENERAL",
        "RSK": "PRECIPITATION_HEIGHT",
        "RSKF": "PRECIPITATION_FORM",
        "SDK": "SUNSHINE_DURATION",
        "SHK_TAG": "SNOW_DEPTH",
        "NM": "CLOUD_COVERAGE_TOTAL",
        "VPM": "PRESSURE_VAPOR",
        "PM": "PRESSURE_AIR",
        "TMK": "TEMPERATURE_AIR_200",
        "UPM": "HUMIDITY",
        "TXK": "TEMPERATURE_AIR_MAX_200",
        "TNK": "TEMPERATURE_AIR_MIN_200",
        "TGK": "TEMPERATURE_AIR_MIN_005",
    }
