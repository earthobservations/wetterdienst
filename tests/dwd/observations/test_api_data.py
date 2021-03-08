# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
import pytz
from pandas._testing import assert_frame_equal

from wetterdienst.dwd.observations import (
    DwdObservationParameterSet,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.dwd.observations.api import DwdObservationRequest
from wetterdienst.dwd.observations.metadata.parameter import (
    DwdObservationParameter,
    DwdObservationParameterSetStructure,
)
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


def test_dwd_observation_data_parameter_set():
    """ Request a parameter set"""
    request = DwdObservationRequest(
        parameter=["kl"],
        resolution="daily",
        period=["recent", "historical"],
    )

    stations = request.filter(station_id=(1,))

    assert stations == DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    ).filter(
        station_id=(1,),
    )

    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
    ).filter(
        station_id=(1,),
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    ).filter(
        station_id=(1,),
    )

    assert request.parameter == [
        (
            DwdObservationParameterSet.CLIMATE_SUMMARY,
            DwdObservationParameterSet.CLIMATE_SUMMARY,
        )
    ]


def test_dwd_observation_data_parameter():
    request = DwdObservationRequest(
        parameter=["precipitation_height"],
        resolution="daily",
        period=["recent", "historical"],
    ).filter(
        station_id=[1],
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT],
        resolution=Resolution.DAILY,
        period=[Period.HISTORICAL, Period.RECENT],
        start_date=None,
        end_date=None,
    ).filter(
        station_id=[1],
    )

    assert request.parameter == [
        (
            DwdObservationParameterSetStructure.DAILY.PRECIPITATION_MORE.PRECIPITATION_HEIGHT,  # Noqa: E501, B950
            DwdObservationParameterSet.PRECIPITATION_MORE,
        )
    ]


def test_dwd_observation_data_fails():
    # station id
    assert (
        DwdObservationRequest(
            parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
            period=[DwdObservationPeriod.HISTORICAL],
            resolution=DwdObservationResolution.DAILY,
        )
        .filter(
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
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
    ).filter(
        station_id=[1],
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[
            DwdObservationPeriod.HISTORICAL,
        ],
        start_date=datetime(1971, 1, 1),
        end_date=datetime(1971, 1, 1),
    ).filter(
        station_id=[1],
    )

    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL],
        end_date="1971-01-01",
    ).filter(
        station_id=[1],
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[
            DwdObservationPeriod.HISTORICAL,
        ],
        start_date=datetime(1971, 1, 1),
        end_date=datetime(1971, 1, 1),
    ).filter(
        station_id=[1],
    )

    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
            resolution=DwdObservationResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
        )


def test_dwd_observation_data_dynamic_period():
    # Historical period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
    )

    assert request.period == [
        Period.HISTORICAL,
    ]

    # Historical and recent period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(days=400),
    )

    assert request.period == [
        Period.HISTORICAL,
        Period.RECENT,
    ]

    # Historical, recent and now period expected
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1971-01-01",
        end_date=pd.Timestamp(datetime.utcnow()),
    )

    assert request.period == [
        Period.HISTORICAL,
        Period.RECENT,
        Period.NOW,
    ]

    # !!!Recent and now period cant be tested dynamically
    # TODO: add test with mocked datetime here

    # Now period
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) - pd.Timedelta(hours=2),
    )
    assert Period.NOW in request.period

    # No period (for example in future)
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date=pd.Timestamp(datetime.utcnow()) + pd.Timedelta(days=720),
    )

    assert request.period == []


def test_dwd_observation_data_result_missing_data():
    """Test for DataFrame having empty values for dates where the station should not
    have values"""
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-27",  # few days before official start
        end_date="1934-01-04",  # few days after official start,
        tidy_data=True,
    ).filter(
        station_id=[1048],
    )

    # Leave only one column to potentially contain NaN which is VALUE
    df = request.values.all().df.drop("QUALITY", axis=1)

    df_1933 = df[df["DATE"].dt.year == 1933]
    df_1934 = df[df["DATE"].dt.year == 1934]

    assert not df_1933.empty and df_1933.dropna().empty
    assert not df_1934.empty and not df_1934.dropna().empty

    request = DwdObservationRequest(
        parameter=DwdObservationParameter.HOURLY.TEMPERATURE_AIR_200,
        resolution=DwdObservationResolution.HOURLY,
        start_date="2020-06-09 12:00:00",  # no data at this time (reason unknown)
        end_date="2020-06-09 12:00:00",
    ).filter(
        station_id=["03348"],
    )

    df = request.values.all().df.drop("QUALITY", axis=1)

    assert_frame_equal(
        df,
        pd.DataFrame(
            {
                "DATE": [datetime(2020, 6, 9, 12, 0, 0, tzinfo=pytz.UTC)],
                "STATION_ID": pd.Categorical(["03348"]),
                "PARAMETER_SET": pd.Categorical(["TEMPERATURE_AIR"]),
                "PARAMETER": pd.Categorical(["TEMPERATURE_AIR_200"]),
                "VALUE": [np.nan],
            }
        ),
    )


@pytest.mark.remote
def test_dwd_observation_data_result_untidy():
    """ Test for actual values (untidy) """
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        tidy_data=False,
        humanize_parameters=False,
    ).filter(
        station_id=[1048],
    )

    df = request.values.all().df

    assert list(df.columns.values) == [
        "DATE",
        "STATION_ID",
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

    assert_frame_equal(
        df,
        pd.DataFrame(
            {
                "DATE": [
                    datetime(1933, 12, 31, tzinfo=pytz.UTC),
                    datetime(1934, 1, 1, tzinfo=pytz.UTC),
                ],
                "STATION_ID": pd.Categorical(["01048", "01048"]),
                "QN_3": pd.Series([pd.NA, pd.NA], dtype=pd.Int64Dtype()),
                "FX": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "FM": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "QN_4": pd.Series([pd.NA, 1], dtype=pd.Int64Dtype()),
                "RSK": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
                "RSKF": pd.to_numeric([pd.NA, 8], errors="coerce"),
                "SDK": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
                "SHK_TAG": pd.to_numeric([pd.NA, 0], errors="coerce"),
                "NM": pd.to_numeric([pd.NA, 8.0], errors="coerce"),
                "VPM": pd.to_numeric([pd.NA, 6.4], errors="coerce"),
                "PM": pd.to_numeric([pd.NA, 1008.60], errors="coerce"),
                "TMK": pd.to_numeric([pd.NA, 0.5], errors="coerce"),
                "UPM": pd.to_numeric([pd.NA, 97.00], errors="coerce"),
                "TXK": pd.to_numeric([pd.NA, 0.7], errors="coerce"),
                "TNK": pd.to_numeric([pd.NA, 0.2], errors="coerce"),
                "TGK": pd.to_numeric([pd.NA, pd.NA], errors="coerce"),
            }
        ),
    )


@pytest.mark.remote
def test_dwd_observation_data_result_tidy():
    """ Test for actual values (tidy) """
    request = DwdObservationRequest(
        parameter=[DwdObservationParameterSet.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        start_date="1933-12-31",  # few days before official start
        end_date="1934-01-01",  # few days after official start,
        tidy_data=True,
        humanize_parameters=False,
    ).filter(
        station_id=[1048],
    )

    df = request.values.all().df

    assert list(df.columns.values) == [
        "DATE",
        "STATION_ID",
        "PARAMETER_SET",
        "PARAMETER",
        "VALUE",
        "QUALITY",
    ]

    assert_frame_equal(
        df,
        pd.DataFrame(
            {
                "DATE": [
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
                "STATION_ID": pd.Categorical(
                    [
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                        "01048",
                    ]
                ),
                "PARAMETER_SET": pd.Categorical(
                    [
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                        "CLIMATE_SUMMARY",
                    ]
                ),
                "PARAMETER": pd.Categorical(
                    [
                        "FX",
                        "FX",
                        "FM",
                        "FM",
                        "RSK",
                        "RSK",
                        "RSKF",
                        "RSKF",
                        "SDK",
                        "SDK",
                        "SHK_TAG",
                        "SHK_TAG",
                        "NM",
                        "NM",
                        "VPM",
                        "VPM",
                        "PM",
                        "PM",
                        "TMK",
                        "TMK",
                        "UPM",
                        "UPM",
                        "TXK",
                        "TXK",
                        "TNK",
                        "TNK",
                        "TGK",
                        "TGK",
                    ]
                ),
                "VALUE": pd.to_numeric(
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
                        8.0,
                        # VPM
                        pd.NA,
                        6.4,
                        # PM
                        pd.NA,
                        1008.60,
                        # TMK
                        pd.NA,
                        0.5,
                        # UPM
                        pd.NA,
                        97.00,
                        # TXK
                        pd.NA,
                        0.7,
                        # TNK
                        pd.NA,
                        0.2,
                        # TGK
                        pd.NA,
                        pd.NA,
                    ],
                    errors="coerce",
                ),
                "QUALITY": pd.Categorical(
                    [
                        # FX
                        pd.NA,
                        pd.NA,
                        # FM
                        pd.NA,
                        pd.NA,
                        # RSK
                        pd.NA,
                        1,
                        # RSKF
                        pd.NA,
                        1,
                        # SDK
                        pd.NA,
                        pd.NA,
                        # SHK_TAG
                        pd.NA,
                        1,
                        # NM
                        pd.NA,
                        1,
                        # VPM
                        pd.NA,
                        1,
                        # PM
                        pd.NA,
                        1,
                        # TMK
                        pd.NA,
                        1,
                        # UPM
                        pd.NA,
                        1,
                        # TXK
                        pd.NA,
                        1,
                        # TNK
                        pd.NA,
                        1,
                        # TGK
                        pd.NA,
                        pd.NA,
                    ]
                ),
            }
        ),
    )


def test_create_humanized_column_names_mapping():
    """ Test for function to create a mapping to humanized column names """
    kl_daily_hcnm = {
        # "QN_3": "QUALITY_WIND",
        "FX": "WIND_GUST_MAX",
        "FM": "WIND_SPEED",
        # "QN_4": "QUALITY_GENERAL",
        "RSK": "PRECIPITATION_HEIGHT",
        "RSKF": "PRECIPITATION_FORM",
        "SDK": "SUNSHINE_DURATION",
        "SHK_TAG": "SNOW_DEPTH",
        "NM": "CLOUD_COVER_TOTAL",
        "VPM": "PRESSURE_VAPOR",
        "PM": "PRESSURE_AIR",
        "TMK": "TEMPERATURE_AIR_200",
        "UPM": "HUMIDITY",
        "TXK": "TEMPERATURE_AIR_MAX_200",
        "TNK": "TEMPERATURE_AIR_MIN_200",
        "TGK": "TEMPERATURE_AIR_MIN_005",
    }
    hcnm = (
        DwdObservationRequest(
            [DwdObservationParameterSet.CLIMATE_SUMMARY],
            DwdObservationResolution.DAILY,
            [DwdObservationPeriod.RECENT],
        )
        .filter(
            (0,),
        )
        .values._create_humanized_parameters_mapping()
    )

    assert set(kl_daily_hcnm.items()).issubset(set(hcnm.items()))


def test_tidy_up_data():
    """ Test for function to tidy data"""
    df = pd.DataFrame(
        {
            "STATION_ID": [1048],
            "DATE": [pd.Timestamp("2019-01-23 00:00:00")],
            "QN_3": [10],
            "FX": [11.8],
            "FM": [5.8],
            "QN_4": [3],
            "RSK": [0.0],
            "RSKF": [0.0],
            "SDK": [7.1],
            "SHK_TAG": [0.0],
            "NM": [2.3],
            "VPM": [3.2],
            "PM": [975.4],
            "TMK": [-5.5],
            "UPM": [79.17],
            "TXK": [-1.7],
            "TNK": [-7.9],
            "TGK": [-11.4],
        }
    )

    df_tidy = pd.DataFrame(
        {
            "STATION_ID": [1048] * 14,
            "DATE": [pd.Timestamp("2019-01-23 00:00:00")] * 14,
            "PARAMETER": [
                "FX",
                "FM",
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
            ],
            "VALUE": [
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
            "QUALITY": pd.Series(
                [10, 10, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], dtype=pd.Int64Dtype()
            ),
        }
    )

    df_tidy = df_tidy.astype(
        {
            "STATION_ID": "category",
            "PARAMETER": "category",
            "QUALITY": "category",
        }
    )

    assert_frame_equal(df.dwd.tidy_up_data(), df_tidy)
