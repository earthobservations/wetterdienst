# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import numpy as np
import pandas as pd
from pandas._testing import assert_frame_equal, assert_series_equal

from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)


def test_coerce_strings():
    series = TimeseriesValues._coerce_strings(pd.Series(["foobar"]))
    series_expected = pd.Series(["foobar"], dtype=pd.StringDtype())

    assert_series_equal(series, series_expected)


def test_coerce_floats():
    series = TimeseriesValues._coerce_floats(pd.Series([42.42]))
    series_expected = pd.Series([42.42], dtype="float64")

    assert_series_equal(series, series_expected)


def test_coerce_field_types(settings_humanize_false_wide_shape):
    """Test coercion of fields"""
    # Special cases
    # We require a stations_result object with hourly resolution in order to accurately parse
    # the hourly timestamp (pandas would fail parsing it because it has a strange
    # format)
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.SOLAR,  # RS_IND_01,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        settings=settings_humanize_false_wide_shape,
    ).all()

    # Here we don't query the actual data because it takes too long
    # we rather use a predefined DataFrame to check for coercion
    df = pd.DataFrame(
        {
            "station_id": ["00001"],
            "dataset": ["climate_summary"],
            "parameter": ["rs_ind_01"],
            "date": ["1970010100"],
            "value": [1],
            "quality": ["1"],
        }
    )

    df = request.values._coerce_date_fields(df, "00001")
    df = request.values._coerce_meta_fields(df)
    df = request.values._coerce_parameter_types(df)

    expected_df = pd.DataFrame(
        {
            "station_id": pd.Categorical(["00001"]),
            "dataset": pd.Categorical(["climate_summary"]),
            "parameter": ["rs_ind_01"],
            "date": [pd.Timestamp("1970-01-01").tz_localize("utc")],
            "value": pd.Series([1], dtype=float),
            "quality": pd.Series([1], dtype=float),
        }
    )

    assert_frame_equal(df, expected_df, check_categorical=False)


def test_coerce_field_types_with_nans(settings_humanize_false_wide_shape):
    """Test field coercion with NaNs"""
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.SOLAR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        settings=settings_humanize_false_wide_shape,
    ).all()

    df = pd.DataFrame(
        {
            "quality": [pd.NA, np.nan, "1"],
            "value": [pd.NA, np.nan, "1"],
        }
    )

    expected_df = pd.DataFrame(
        {
            "quality": pd.to_numeric([pd.NA, np.nan, 1], errors="coerce"),
            "value": pd.to_numeric([pd.NA, np.nan, 1], errors="coerce"),
        }
    )

    df = request.values._coerce_parameter_types(df)

    assert_frame_equal(df, expected_df, check_categorical=False)
