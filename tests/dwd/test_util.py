import pytest
import numpy as np
import pandas as pd
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.util import (
    check_parameters,
    coerce_field_types,
    parse_enumeration_from_template,
    build_parameter_identifier,
)
from wetterdienst.dwd.metadata.period_type import PeriodType
from wetterdienst.dwd.metadata.time_resolution import TimeResolution
from wetterdienst.dwd.metadata.parameter import Parameter
from wetterdienst.exceptions import InvalidParameter


def test_check_parameters():
    assert check_parameters(
        Parameter.PRECIPITATION, TimeResolution.MINUTE_10, PeriodType.HISTORICAL
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
            "QN": pd.Series([1], dtype=pd.Int64Dtype()),
            "RS_IND_01": pd.Series([1], dtype=pd.Int64Dtype()),
            "DATE": [pd.Timestamp("1970-01-01")],
            "END_OF_INTERVAL": [pd.Timestamp("1970-01-01")],
            "V_VV_I": pd.Series(["P"], dtype=pd.StringDtype()),
        }
    )

    df = coerce_field_types(df, TimeResolution.HOURLY)

    assert_frame_equal(df, expected_df)


def test_coerce_field_types_with_nans():
    df = pd.DataFrame(
        {
            "QN": [pd.NA, np.nan, "1"],
            "RS_IND_01": [pd.NA, np.nan, "1"],
            "V_VV_I": [pd.NA, np.nan, "P"],
        }
    )

    expected_df = pd.DataFrame(
        {
            "QN": pd.Series([pd.NA, np.nan, 1], dtype=pd.Int64Dtype()),
            "RS_IND_01": pd.Series([pd.NA, np.nan, 1], dtype=pd.Int64Dtype()),
            "V_VV_I": pd.Series([pd.NA, np.nan, "P"], dtype=pd.StringDtype()),
        }
    )

    df = coerce_field_types(df, TimeResolution.HOURLY)
    assert_frame_equal(df, expected_df)


def test_build_parameter_identifier():
    parameter_identifier = build_parameter_identifier(
        Parameter.CLIMATE_SUMMARY, TimeResolution.DAILY, PeriodType.HISTORICAL, 1
    )

    assert parameter_identifier == "kl/daily/historical/station_id_1"
