# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import numpy as np
import pandas as pd
import pytest
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.observations import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.dwd.util import build_parameter_set_identifier
from wetterdienst.exceptions import InvalidEnumeration
from wetterdienst.util.enumeration import parse_enumeration_from_template


def test_parse_enumeration_from_template():
    assert (
        parse_enumeration_from_template("climate_summary", DwdObservationDataset)
        == DwdObservationDataset.CLIMATE_SUMMARY
    )
    assert (
        parse_enumeration_from_template("kl", DwdObservationDataset)
        == DwdObservationDataset.CLIMATE_SUMMARY
    )

    with pytest.raises(InvalidEnumeration):
        parse_enumeration_from_template("climate", DwdObservationDataset)


def test_coerce_field_types():
    """ Test coercion of fields """
    # Special cases
    # We require a stations object with hourly resolution in order to accurately parse
    # the hourly timestamp (pandas would fail parsing it because it has a strange
    # format)
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.SOLAR,  # RS_IND_01,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        humanize_parameters=False,
        tidy_data=False,
    ).all()

    # Here we don't query the actual data because it tales too long
    # we rather use a predefined DataFrame to check for coercion
    df = pd.DataFrame(
        {
            "STATION_ID": ["00001"],
            "DATE": ["1970010100"],
            "QN": ["1"],
            "RS_IND_01": [1],
            "END_OF_INTERVAL": ["1970010100:00"],
            "V_VV_I": ["P"],
        }
    )

    df = request.values._coerce_date_fields(df)
    df = request.values._coerce_meta_fields(df)
    df = request.values._coerce_parameter_types(df)

    expected_df = pd.DataFrame(
        {
            "STATION_ID": pd.Categorical(["00001"]),
            "DATE": [pd.Timestamp("1970-01-01").tz_localize("UTC")],
            "QN": pd.Series([1], dtype=pd.Int64Dtype()),
            "RS_IND_01": pd.Series([1], dtype=pd.Int64Dtype()),
            "END_OF_INTERVAL": [pd.Timestamp("1970-01-01")],
            "V_VV_I": pd.Series(["P"], dtype=pd.StringDtype()),
        }
    )

    assert_frame_equal(df, expected_df)


def test_coerce_field_types_with_nans():
    """ Test field coercion with NaNs """
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.SOLAR,  # RS_IND_01,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        humanize_parameters=False,
        tidy_data=False,
    ).all()

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

    df = request.values._coerce_parameter_types(df)

    assert_frame_equal(df, expected_df)


def test_build_parameter_identifier():
    parameter_identifier = build_parameter_set_identifier(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
        "00001",
    )

    assert parameter_identifier == "kl/daily/historical/00001"
