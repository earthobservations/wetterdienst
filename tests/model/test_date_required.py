# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the refusal of a dataset that is read by a window when the request has none (GH-3562)."""

from __future__ import annotations

import datetime as dt
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Wetterdienst
from wetterdienst.exceptions import BufrReaderMissingError, DateRequiredError, StartDateEndDateError
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

# a key that no provider has accepted: it only lets the request be built, and nothing here reaches a provider
SETTINGS = Settings(auth={"aemet": "dummy-key-for-test", "knmi": "dummy-key-for-test", "metno_frost": "client-id"})


def _date_required_datasets() -> list[tuple[str, str, str, str]]:
    """List (provider, network, resolution, dataset) for every dataset of the registry that needs a window."""
    found = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            api = Wetterdienst.resolve(provider, network)
            found.extend(
                (provider, network, resolution.name, dataset.name)
                for resolution in api.metadata
                for dataset in resolution.datasets
                if dataset.date_required
            )
    return found


DATASETS = _date_required_datasets()


def _stations(provider: str, network: str, parameters: list[tuple[str, str]], **window: object) -> StationsResult:
    """Give the stations of a request for datasets, without a station list: nothing is downloaded."""
    request = Wetterdienst.resolve(provider, network)(parameters=parameters, settings=SETTINGS, **window)
    return StationsResult(
        request=request,
        df=pl.DataFrame(),
        _df_all=pl.DataFrame(),
        _stations_filter=StationsFilter.ALL,
    )


def test_every_provider_with_a_date_required_dataset_is_tested() -> None:
    """Test that the registry holds the providers this refusal was written for, so that the list is no empty one."""
    providers = {provider for provider, *_ in DATASETS}

    assert {"metno", "fmi", "knmi", "dmi", "lhmt", "rmi", "nws", "aemet", "wsv", "ea"} <= providers


@pytest.mark.parametrize(("provider", "network", "resolution", "dataset"), DATASETS)
def test_values_of_a_date_required_dataset_are_refused_without_a_window(
    provider: str, network: str, resolution: str, dataset: str
) -> None:
    """Test that the Python API raises, naming the dataset, where it used to answer an empty frame."""
    stations = _stations(provider, network, [(resolution, dataset)])

    with pytest.raises(DateRequiredError, match=f"The dataset {resolution}/{dataset} needs a window") as raised:
        stations.values()
    # what a caller of the REST API, the command line and MCP was told, and what they catch
    assert isinstance(raised.value, ValueError)
    assert isinstance(raised.value, StartDateEndDateError)
    assert "'start' and 'end'" in str(raised.value)


@pytest.mark.parametrize(("provider", "network", "resolution", "dataset"), DATASETS)
def test_values_of_a_date_required_dataset_are_read_with_a_window(
    provider: str, network: str, resolution: str, dataset: str
) -> None:
    """Test that the same request with a window gives a reader, and a bound given alone is a window."""
    day = dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

    try:
        given = _stations(provider, network, [(resolution, dataset)], start=day, end=day)
        alone = _stations(provider, network, [(resolution, dataset)], start="2020-01-01")
        readers = [given.values(), alone.values()]
    except BufrReaderMissingError:
        pytest.skip("the BUFR extra is not installed")

    assert all(isinstance(reader, TimeseriesValues) for reader in readers)


def test_values_of_several_datasets_name_every_one_that_needs_a_window() -> None:
    """Test that the message names each dataset that needs a window once."""
    stations = _stations("dmi", "observation", [("hourly", "data"), ("daily", "data"), ("hourly", "data")])

    with pytest.raises(DateRequiredError, match=r"The datasets hourly/data, daily/data need a window"):
        stations.values()


def test_values_of_a_dataset_that_needs_no_window_are_read_without_one() -> None:
    """Test that the refusal is for the datasets that say they need a window, and no other."""
    stations = _stations("dwd", "observation", [("daily", "kl")])

    assert isinstance(stations.values(), TimeseriesValues)


def test_stations_of_a_date_required_dataset_are_listed_without_a_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that only the values need the window: the stations come without one, and then refuse the values."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    sources = (
        b'{"data": [{"id": "SN18700", "name": "OSLO - BLINDERN", "validFrom": "1937-01-01T00:00:00.000Z",'
        b' "geometry": {"coordinates": [10.72, 59.94]}, "county": "OSLO", "countryCode": "NO", "masl": 94}]}'
    )
    monkeypatch.setattr(
        frost_api, "download_file", lambda *, url, **_: File(url=url, content=BytesIO(sources), status=200)
    )
    request = MetnoFrostRequest(parameters=[("daily", "data")])

    stations = request.filter_by_station_id("SN18700")

    assert stations.df["station_id"].to_list() == ["SN18700"]
    with pytest.raises(DateRequiredError, match="The dataset daily/data needs a window"):
        stations.values().all()
