import pytest
import numpy as np
import pandas as pd
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.util import (
    check_parameters,
    coerce_field_types,
    parse_enumeration_from_template,
    build_parameter_set_identifier,
)
from wetterdienst.dwd.observations.metadata.period_type import PeriodType
from wetterdienst.dwd.metadata.time_resolution import DWDObservationTimeResolution
from wetterdienst.dwd.observations.metadata.parameter_set import DWDParameterSet
from wetterdienst.exceptions import InvalidEnumeration


def test_check_parameters():
    assert check_parameters(
        DWDParameterSet.PRECIPITATION, DWDObservationTimeResolution.MINUTE_10, PeriodType.HISTORICAL
    )
    assert not check_parameters(
        DWDParameterSet.CLIMATE_SUMMARY, DWDObservationTimeResolution.MINUTE_1, PeriodType.HISTORICAL
    )


def test_parse_enumeration_from_template():
    assert (
        parse_enumeration_from_template("climate_summary", DWDParameterSet)
        == DWDParameterSet.CLIMATE_SUMMARY
    )
    assert (
        parse_enumeration_from_template("kl", DWDParameterSet)
        == DWDParameterSet.CLIMATE_SUMMARY
    )

    with pytest.raises(InvalidEnumeration):
        parse_enumeration_from_template("climate", DWDParameterSet)


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

    df = coerce_field_types(df, DWDObservationTimeResolution.HOURLY)

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

    df = coerce_field_types(df, DWDObservationTimeResolution.HOURLY)
    assert_frame_equal(df, expected_df)


def test_build_parameter_identifier():
    parameter_identifier = build_parameter_set_identifier(
        DWDParameterSet.CLIMATE_SUMMARY, DWDObservationTimeResolution.DAILY, PeriodType.HISTORICAL, 1
    )

    assert parameter_identifier == "kl/daily/historical/station_id_1"
