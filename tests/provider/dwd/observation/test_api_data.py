# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
import pytz
from freezegun import freeze_time
from pandas._testing import assert_frame_equal

from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationDatasetTree,
    DwdObservationParameter,
)


def test_dwd_observation_data_api():
    request = DwdObservationRequest(
        parameter=["precipitation_height"],
        resolution="daily",
        period=["recent", "historical"],
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT],
        resolution=Resolution.DAILY,
        period=[Period.HISTORICAL, Period.RECENT],
        start_date=None,
        end_date=None,
    )

    assert request.parameter == [
        (
            DwdObservationDatasetTree.DAILY.CLIMATE_SUMMARY.PRECIPITATION_HEIGHT,  # Noqa: E501, B950
            DwdObservationDataset.CLIMATE_SUMMARY,
        )
    ]


@pytest.mark.remote
def test_dwd_observation_data_dataset():
    """ Request a parameter set"""
    expected = DwdObservationRequest(
        parameter=["kl"],
        resolution="daily",
        period=["recent", "historical"],
    ).filter_by_station_id(station_id=(1,))

    given = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    ).filter_by_station_id(
        station_id=(1,),
    )

    assert given == expected

    expected = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
    ).filter_by_station_id(
        station_id=(1,),
    )

    given = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    ).filter_by_station_id(
        station_id=(1,),
    )

    assert expected == given

    assert expected.parameter == [
        (
            DwdObservationDataset.CLIMATE_SUMMARY,
            DwdObservationDataset.CLIMATE_SUMMARY,
        )
    ]


def test_dwd_observation_data_parameter():
    """ Test parameter given as single value without dataset """
    request = DwdObservationRequest(
        parameter=["precipitation_height"],
        resolution="daily",
        period=["recent", "historical"],
    )

    assert request.parameter == [
        (
            DwdObservationDatasetTree.DAILY.CLIMATE_SUMMARY.PRECIPITATION_HEIGHT,
            DwdObservationDataset.CLIMATE_SUMMARY,
        )
    ]

    request = DwdObservationRequest(
        parameter=["climate_summary"],
        resolution="daily",
        period=["recent", "historical"],
    )

    assert request.parameter == [
        (DwdObservationDataset.CLIMATE_SUMMARY, DwdObservationDataset.CLIMATE_SUMMARY)
    ]


def test_dwd_observation_data_parameter_dataset_pairs():
    """ Test parameters given as parameter - dataset pair """
    request = DwdObservationRequest(
        parameter=[("climate_summary", "climate_summary")],
        resolution="daily",
        period=["recent", "historical"],
    )

    assert request.parameter == [
        (DwdObservationDataset.CLIMATE_SUMMARY, DwdObservationDataset.CLIMATE_SUMMARY)
    ]

    request = DwdObservationRequest(
        parameter=[("precipitation_height", "precipitation_more")],
        resolution="daily",
        period=["recent", "historical"],
    )

    assert request.parameter == [
        (
            DwdObservationDatasetTree.DAILY.PRECIPITATION_MORE.PRECIPITATION_HEIGHT,
            DwdObservationDataset.PRECIPITATION_MORE,
        )
    ]


@pytest.mark.remote
def test_dwd_observation_data_fails():
    # station id
    assert (
        DwdObservationRequest(
            parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
            period=[DwdObservationPeriod.HISTORICAL],
            resolution=DwdObservationResolution.DAILY,
        )
        .filter_by_station_id(
            station_id=["test"],
        )
        .df.empty
    )

    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameter=["abc"],
            resolution=DwdObservationResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
        )

    # TODO: check first if parameters are found
    # with pytest.raises(NoParametersFound):
    #     DWDObservationStations(
    #         parameter=["abc"],
    #         resolution=DWDObservationResolution.DAILY,
    #         start_date="1951-01-01",
    #         end_date="1961-01-01",
    #     )


def test_dwd_observation_data_dates():
    # time input
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
    ).filter_by_station_id(
        station_id=[1],
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[
            DwdObservationPeriod.HISTORICAL,
        ],
        start_date=datetime(1971, 1, 1),
        end_date=datetime(1971, 1, 1),
    ).filter_by_station_id(
        station_id=[1],
    )

    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL],
        end_date="1971-01-01",
    ).filter_by_station_id(
        station_id=[1],
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[
            DwdObservationPeriod.HISTORICAL,
        ],
        start_date=datetime(1971, 1, 1),
        end_date=datetime(1971, 1, 1),
    ).filter_by_station_id(
        station_id=[1],
    )

    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
            resolution=DwdObservationResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
        )


def test_request_period_historical():
    # Historical period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
    )

    assert request.period == [
        Period.HISTORICAL,
    ]


def test_request_period_historical_recent():
    # Historical and recent period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(days=400),
    )

    assert request.period == [
        Period.HISTORICAL,
        Period.RECENT,
    ]


def test_request_period_historical_recent_now():
    # Historical, recent and now period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()),
    )

    assert request.period == [
        Period.HISTORICAL,
        Period.RECENT,
        Period.NOW,
    ]


def test_request_period_now():

    # Now period
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(hours=2),
    )
    assert Period.NOW in request.period


@freeze_time("2021-03-28T18:38:00+02:00")
def test_request_period_now_fixeddate():

    # Now period
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(hours=2),
    )
    assert Period.NOW in request.period


def test_request_period_empty():
    # No period (for example in future)
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) + pd.Timedelta(days=720),
    )

    assert request.period == []


@pytest.mark.remote
def test_dwd_observation_data_result_missing_data():
    """Test for DataFrame having empty values for dates where the station should not
    have values"""
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-27",  # few days before official start
        end_date="1934-01-04",  # few days after official start,
        tidy=True,
    ).filter_by_station_id(
        station_id=[1048],
    )

    # Leave only one column to potentially contain NaN which is VALUE
    df = request.values.all().df.drop("quality", axis=1)

    df_1933 = df[df["date"].dt.year == 1933]
    df_1934 = df[df["date"].dt.year == 1934]

    assert not df_1933.empty and df_1933.dropna().empty
    assert not df_1934.empty and not df_1934.dropna().empty

    request = DwdObservationRequest(
        parameter=DwdObservationParameter.HOURLY.TEMPERATURE_AIR_200,
        resolution=DwdObservationResolution.HOURLY,
        start_date="2020-06-09 12:00:00",  # no data at this time (reason unknown)
        end_date="2020-06-09 12:00:00",
    ).filter_by_station_id(
        station_id=["03348"],
    )

    df = request.values.all().df  # .drop("quality", axis=1)

    assert_frame_equal(
        df,
        pd.DataFrame(
            {
                "station_id": pd.Categorical(["03348"]),
                "dataset": pd.Categorical(["temperature_air"]),
                "parameter": pd.Categorical(["temperature_air_200"]),
                "date": [datetime(2020, 6, 9, 12, 0, 0, tzinfo=pytz.UTC)],
                "value": [np.nan],
                "quality": [np.nan],
            }
        ),
    )


@pytest.mark.remote
def test_dwd_observation_data_result_tabular():
    """ Test for actual values (tabular) """
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        tidy=False,
        humanize=False,
        si_units=False,
    ).filter_by_station_id(
        station_id=[1048],
    )

    df = request.values.all().df

    assert list(df.columns.values) == [
        "station_id",
        "date",
        "qn_3",
        "fx",
        "fm",
        "qn_4",
        "rsk",
        "rskf",
        "sdk",
        "shk_tag",
        "nm",
        "vpm",
        "pm",
        "tmk",
        "upm",
        "txk",
        "tnk",
        "tgk",
    ]

    assert_frame_equal(
        df,
        pd.DataFrame(
            {
                "station_id": pd.Categorical(["01048", "01048"]),
                "date": [
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                ],
                "qn_3": pd.Series([pd.NA, pd.NA], dtype=pd.Int64Dtype()),
                "fx": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "fm": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "qn_4": pd.Series([pd.NA, 1], dtype=pd.Int64Dtype()),
                "rsk": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
                "rskf": pd.to_numeric([pd.NA, 8], errors="coerce"),
                "sdk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "shk_tag": pd.Series([pd.NA, 0], dtype=pd.Int64Dtype()),
                "nm": pd.to_numeric([pd.NA, 8.0], errors="coerce"),
                "vpm": pd.to_numeric([pd.NA, 6.4], errors="coerce"),
                "pm": pd.to_numeric([pd.NA, 1008.60], errors="coerce"),
                "tmk": pd.to_numeric([pd.NA, 0.5], errors="coerce"),
                "upm": pd.to_numeric([pd.NA, 97.00], errors="coerce"),
                "txk": pd.to_numeric([pd.NA, 0.7], errors="coerce"),
                "tnk": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
                "tgk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            }
        ),
    )


@pytest.mark.remote
def test_dwd_observation_data_result_tabular_metric():
    """ Test for actual values (tabular) in metric units """
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        tidy=False,
        humanize=False,
        si_units=True,
    ).filter_by_station_id(
        station_id=[1048],
    )

    df = request.values.all().df

    assert list(df.columns.values) == [
        "station_id",
        "date",
        "qn_3",
        "fx",
        "fm",
        "qn_4",
        "rsk",
        "rskf",
        "sdk",
        "shk_tag",
        "nm",
        "vpm",
        "pm",
        "tmk",
        "upm",
        "txk",
        "tnk",
        "tgk",
    ]

    assert_frame_equal(
        df,
        pd.DataFrame(
            {
                "station_id": pd.Categorical(["01048", "01048"]),
                "date": [
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                ],
                "qn_3": pd.Series([pd.NA, pd.NA], dtype=pd.Int64Dtype()),
                "fx": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "fm": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "qn_4": pd.Series([pd.NA, 1], dtype=pd.Int64Dtype()),
                "rsk": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
                "rskf": pd.to_numeric([pd.NA, 8], errors="coerce"),
                "sdk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "shk_tag": pd.Series([pd.NA, 0], dtype=pd.Int64Dtype()),
                "nm": pd.to_numeric([pd.NA, 100.0], errors="coerce"),
                "vpm": pd.to_numeric([pd.NA, 640.0], errors="coerce"),
                "pm": pd.to_numeric([pd.NA, 100860.0], errors="coerce"),
                "tmk": pd.to_numeric([pd.NA, 273.65], errors="coerce"),
                "upm": pd.to_numeric([pd.NA, 97.00], errors="coerce"),
                "txk": pd.to_numeric([pd.NA, 273.84999999999997], errors="coerce"),
                "tnk": pd.to_numeric([pd.NA, 273.34999999999997], errors="coerce"),
                "tgk": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            }
        ),
    )


@pytest.mark.remote
def test_dwd_observation_data_result_tidy_metric():
    """ Test for actual values (tidy) in metric units """
    request = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        tidy=True,
        humanize=False,
        si_units=True,
    ).filter_by_station_id(
        station_id=(1048,),
    )

    df = request.values.all().df

    assert list(df.columns.values) == [
        "station_id",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]

    assert_frame_equal(
        df,
        pd.DataFrame(
            {
                "station_id": pd.Categorical(["01048"] * 28),
                "dataset": pd.Categorical(["climate_summary"] * 28),
                "parameter": pd.Categorical(
                    [
                        "fx",
                        "fx",
                        "fm",
                        "fm",
                        "rsk",
                        "rsk",
                        "rskf",
                        "rskf",
                        "sdk",
                        "sdk",
                        "shk_tag",
                        "shk_tag",
                        "nm",
                        "nm",
                        "vpm",
                        "vpm",
                        "pm",
                        "pm",
                        "tmk",
                        "tmk",
                        "upm",
                        "upm",
                        "txk",
                        "txk",
                        "tnk",
                        "tnk",
                        "tgk",
                        "tgk",
                    ]
                ),
                "date": [
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                ],
                "value": pd.to_numeric(
                    [
                        # FX
                        pd.NA,
                        pd.NA,
                        # FM
                        pd.NA,
                        pd.NA,
                        # RSK
                        pd.NA,
                        0.2,
                        # RSKF
                        pd.NA,
                        8,
                        # SDK
                        pd.NA,
                        pd.NA,
                        # SHK_TAG
                        pd.NA,
                        0,
                        # NM
                        pd.NA,
                        100.0,
                        # VPM
                        pd.NA,
                        640.0,
                        # PM
                        pd.NA,
                        100860.0,
                        # TMK
                        pd.NA,
                        273.65,
                        # UPM
                        pd.NA,
                        97.00,
                        # TXK
                        pd.NA,
                        273.84999999999997,
                        # TNK
                        pd.NA,
                        273.34999999999997,
                        # TGK
                        pd.NA,
                        pd.NA,
                    ],
                    errors="coerce",
                ).astype(float),
                "quality": pd.Series(
                    [
                        # FX
                        np.NaN,
                        np.NaN,
                        # FM
                        np.NaN,
                        np.NaN,
                        # RSK
                        np.NaN,
                        1,
                        # RSKF
                        np.NaN,
                        1,
                        # SDK
                        np.NaN,
                        np.NaN,
                        # SHK_TAG
                        np.NaN,
                        1,
                        # NM
                        np.NaN,
                        1,
                        # VPM
                        np.NaN,
                        1,
                        # PM
                        np.NaN,
                        1,
                        # TMK
                        np.NaN,
                        1,
                        # UPM
                        np.NaN,
                        1,
                        # TXK
                        np.NaN,
                        1,
                        # TNK
                        np.NaN,
                        1,
                        # TGK
                        np.NaN,
                        np.NaN,
                    ],
                    dtype=float,
                ),
            },
        ),
        # Needed since pandas 1.2?
        check_categorical=False,
    )


def test_create_humanized_column_names_mapping():
    """ Test for function to create a mapping to humanized column names """
    kl_daily_hcnm = {
        # "qn_3": "quality_wind",
        "fx": "wind_gust_max",
        "fm": "wind_speed",
        # "qn_4": "quality_general",
        "rsk": "precipitation_height",
        "rskf": "precipitation_form",
        "sdk": "sunshine_duration",
        "shk_tag": "snow_depth",
        "nm": "cloud_cover_total",
        "vpm": "pressure_vapor",
        "pm": "pressure_air",
        "tmk": "temperature_air_200",
        "upm": "humidity",
        "txk": "temperature_air_max_200",
        "tnk": "temperature_air_min_200",
        "tgk": "temperature_air_min_005",
    }
    hcnm = (
        DwdObservationRequest(
            [DwdObservationDataset.CLIMATE_SUMMARY],
            DwdObservationResolution.DAILY,
            [DwdObservationPeriod.RECENT],
        )
        .filter_by_station_id(
            (0,),
        )
        .values._create_humanized_parameters_mapping()
    )

    assert set(kl_daily_hcnm.items()).issubset(set(hcnm.items()))


def test_tidy_up_data():
    """ Test for function to tidy data"""
    request = DwdObservationRequest(
        "kl",
        "daily",
        "historical",
        start_date="2019-01-23 00:00:00",
        tidy=True,
        humanize=False,
    ).filter_by_station_id((1048,))

    df = pd.DataFrame(
        {
            "station_id": [1048],
            "date": [pd.Timestamp("2019-01-23 00:00:00")],
            "qn_3": [10],
            "fx": [11.8],
            "fm": [5.8],
            "qn_4": [3],
            "rsk": [0.0],
            "rskf": [0.0],
            "sdk": [7.1],
            "shk_tag": [0.0],
            "nm": [2.3],
            "vpm": [3.2],
            "pm": [975.4],
            "tmk": [-5.5],
            "upm": [79.17],
            "txk": [-1.7],
            "tnk": [-7.9],
            "tgk": [-11.4],
        }
    )

    df_tidied = request.values.tidy_up_df(df, request.parameter[0][1])
    df_tidied_organized = request.values._organize_df_columns(df_tidied)

    df_tidy = pd.DataFrame(
        {
            "station_id": [1048] * 14,
            "dataset": ["climate_summary"] * 14,
            "parameter": [
                "fx",
                "fm",
                "rsk",
                "rskf",
                "sdk",
                "shk_tag",
                "nm",
                "vpm",
                "pm",
                "tmk",
                "upm",
                "txk",
                "tnk",
                "tgk",
            ],
            "date": [pd.Timestamp("2019-01-23 00:00:00")] * 14,
            "value": [
                11.8,
                5.8,
                0.0,
                0.0,
                7.1,
                0.0,
                2.3,
                3.2,
                975.4,
                -5.5,
                79.17,
                -1.7,
                -7.9,
                -11.4,
            ],
            "quality": pd.Series(
                [10, 10, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], dtype=float
            ),
        }
    )

    assert_frame_equal(df_tidied_organized, df_tidy)
