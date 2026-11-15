# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations of the providers that publish their ids are found by them, through the provider's own reader (GH-4070).

The reader of each provider runs on the rows of its catalogue stub (`station_catalogue_stubs.py`), so what the search
finds is what the reader gave each station, not a hand-built frame: the WMO number and the WIGOS id of MeteoSwiss (a
WSI of WMO's issuer and one of its own), the WMO number and the ICAO code of the MADIS table of NWS.
"""

from __future__ import annotations

import pytest

from tests.provider.station_catalogue_stubs import _meteoswiss, _nws
from wetterdienst import Settings
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationRequest
from wetterdienst.provider.nws.observation import NwsObservationRequest


@pytest.fixture
def meteoswiss(monkeypatch: pytest.MonkeyPatch) -> MeteoswissObservationRequest:
    """Give the request of MeteoSwiss, whose catalogue is served from the stub."""
    _meteoswiss(monkeypatch)
    return MeteoswissObservationRequest(parameters=[("daily", "data")], settings=Settings(cache_disable=True))


@pytest.fixture
def nws(monkeypatch: pytest.MonkeyPatch) -> NwsObservationRequest:
    """Give the request of NWS, whose catalogue is served from the stub."""
    _nws(monkeypatch)
    return NwsObservationRequest(parameters=[("hourly", "data")], settings=Settings(cache_disable=True))


def _ids(result: object) -> list[str]:
    return sorted(result.df.get_column("station_id").unique().to_list())  # ty: ignore[unresolved-attribute]


def test_a_wmo_id_finds_the_station_whose_wsi_of_the_wmo_issuer_carries_it(
    meteoswiss: MeteoswissObservationRequest,
) -> None:
    """The WMO number is the local part of `0-20000-0-06735`, however the person typing writes it."""
    for wmo_id in ("06735", "6735", 6735):
        assert _ids(meteoswiss.filter_by_wmo_id(wmo_id)) == ["ABO"]


def test_a_station_of_a_national_issuer_has_no_wmo_id_but_its_wigos_id(
    meteoswiss: MeteoswissObservationRequest,
) -> None:
    """Biasca is `0-756-0-BIA`: a WSI of MeteoSwiss's own issuer says no WMO number, and none is made up."""
    assert _ids(meteoswiss.filter_by_wigos_id("0-756-0-BIA")) == ["BIA"]
    wmo_ids = meteoswiss.all().df.filter(station_id="BIA").get_column("wmo_id").to_list()
    assert wmo_ids == [None]


def test_a_wigos_id_finds_its_station_whichever_way_the_issuer_is_written(
    meteoswiss: MeteoswissObservationRequest,
) -> None:
    """The issuer is read without its leading zeros, as the column holds it."""
    for wigos_id in ("0-20000-0-06660", "0-020000-0-06660"):
        assert _ids(meteoswiss.filter_by_wigos_id(wigos_id)) == ["SMA"]


def test_an_icao_id_finds_the_station_whose_id_is_that_code(nws: NwsObservationRequest) -> None:
    """The id of the MADIS table is an ICAO code for most of the stations, so `icao_id` is filled from it."""
    for icao_id in ("KDEN", "kden"):
        assert _ids(nws.filter_by_icao_id(icao_id)) == ["KDEN"]


def test_an_faa_identifier_is_no_icao_id_and_its_station_has_none(nws: NwsObservationRequest) -> None:
    """`03PS` has a digit, so it is an FAA location identifier: the station keeps it as its id and has no ICAO code."""
    with pytest.raises(ValueError, match="is no icao_id"):
        nws.filter_by_icao_id("03PS")
    row = nws.filter_by_station_id("03PS").df.row(0, named=True)
    assert (row["station_id"], row["icao_id"]) == ("03PS", None)


def test_the_wmo_number_of_the_madis_table_is_read_without_its_padding(nws: NwsObservationRequest) -> None:
    """Column 1 is the number zero-padded to ten digits; `0000000000` says the station has none."""
    assert _ids(nws.filter_by_wmo_id(72565)) == ["KDEN"]
    assert nws.filter_by_station_id("K37W").df.get_column("wmo_id").to_list() == [None]
