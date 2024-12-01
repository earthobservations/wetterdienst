# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""tests for file index creation"""

import datetime as dt

import polars as pl
import pytest

from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.provider.dwd.observation.metaindex import (
    _create_csv_line,
    create_meta_index_for_climate_observations,
)


@pytest.mark.remote
def test_meta_index_creation_success(default_settings):
    # Existing combination of parameters
    meta_index = create_meta_index_for_climate_observations(
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.HISTORICAL,
        settings=default_settings,
    ).collect()
    assert not meta_index.is_empty()


@pytest.mark.remote
def test_meta_index_1mph_creation(default_settings):
    meta_index_1mph = create_meta_index_for_climate_observations(
        dataset=DwdObservationMetadata.minute_1.precipitation,
        period=Period.HISTORICAL,
        settings=default_settings,
    ).collect()
    assert meta_index_1mph.filter(pl.col(Columns.STATION_ID.value).eq("00003")).row(0) == (
        (
            "00003",
            dt.datetime(1891, 1, 1, 0, 0),
            dt.datetime(2012, 4, 6, 0, 0),
            202.00,
            50.7827,
            6.0941,
            "Aachen",
            "Nordrhein-Westfalen",
        )
    )


def test_create_csv_line():
    assert (
        _create_csv_line("00001 19370101 19860630 478 47.8413 8.8493 Aach Baden-Württemberg".split())
        == "00001,19370101,19860630,478,47.8413,8.8493,Aach,Baden-Württemberg"
    )
    assert (
        _create_csv_line("00126 19791101 20101130 330 49.5447 10.2213 Uffenheim (Schulstr.) Bayern".split())
        == "00126,19791101,20101130,330,49.5447,10.2213,Uffenheim (Schulstr.),Bayern"
    )
    assert (
        _create_csv_line("00102 19980101 20240514 0 53.8633 8.1275 Leuchtturm Alte Weser Niedersachsen".split())
        == "00102,19980101,20240514,0,53.8633,8.1275,Leuchtturm Alte Weser,Niedersachsen"
    )
    assert (
        _create_csv_line("00197 19900801 20240514 365 51.3219 9.0558 Arolsen-Volkhardinghausen, Bad Hessen".split())
        == """00197,19900801,20240514,365,51.3219,9.0558,"Arolsen-Volkhardinghausen, Bad",Hessen"""
    )
    assert (
        _create_csv_line("01332 19660701 20240514 471 48.4832 12.7241 Falkenberg,Kr.Rottal-Inn Bayern".split())
        == """01332,19660701,20240514,471,48.4832,12.7241,"Falkenberg,Kr.Rottal-Inn",Bayern"""
    )
