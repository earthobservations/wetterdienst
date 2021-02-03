# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from unittest.mock import patch

import mock
import numpy as np
import pandas as pd
import pytest
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.observations import (
    DWDObservationData,
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)
from wetterdienst.dwd.util import build_parameter_set_identifier
from wetterdienst.exceptions import InvalidEnumeration
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.enumeration import parse_enumeration_from_template


def test_parse_enumeration_from_template():
    assert (
        parse_enumeration_from_template("climate_summary", DWDObservationParameterSet)
        == DWDObservationParameterSet.CLIMATE_SUMMARY
    )
    assert (
        parse_enumeration_from_template("kl", DWDObservationParameterSet)
        == DWDObservationParameterSet.CLIMATE_SUMMARY
    )

    with pytest.raises(InvalidEnumeration):
        parse_enumeration_from_template("climate", DWDObservationParameterSet)


def test_coerce_field_types():
    df = pd.DataFrame(
        {
            "STATION_ID": ["00001"],
            "QN": ["1"],
            "RS_IND_01": ["1"],
            "DATE": ["1970010100"],
            "END_OF_INTERVAL": ["1970010100:00"],
            "V_VV_I": ["P"],
        }
    )

    def __init__(self):
        self.tidy_data = False
        self.resolution = Resolution.HOURLY

    with patch.object(DWDObservationData, "__init__", __init__):
        observations = DWDObservationData()
        df = observations._coerce_dates(df)
        df = observations._coerce_meta_fields(df)
        df = observations._coerce_parameter_types(df)

    expected_df = pd.DataFrame(
        {
            "STATION_ID": pd.Series(["00001"], dtype="category"),
            "QN": pd.Series([1], dtype=pd.Int64Dtype()),
            "RS_IND_01": pd.Series([1], dtype=pd.Int64Dtype()),
            "DATE": [pd.Timestamp("1970-01-01").tz_localize("UTC")],
            "END_OF_INTERVAL": [pd.Timestamp("1970-01-01")],
            "V_VV_I": pd.Series(["P"], dtype=pd.StringDtype()),
        }
    )

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

    def __init__(self):
        self.tidy_data = False

    with mock.patch.object(DWDObservationData, "__init__", new=__init__):

        df = DWDObservationData()._coerce_parameter_types(df)

    assert_frame_equal(df, expected_df)


def test_build_parameter_identifier():
    parameter_identifier = build_parameter_set_identifier(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObservationResolution.DAILY,
        DWDObservationPeriod.HISTORICAL,
        "00001",
    )

    assert parameter_identifier == "kl/daily/historical/00001"
