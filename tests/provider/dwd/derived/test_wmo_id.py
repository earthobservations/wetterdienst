# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The WMO numbers of `dwd/derived` stations, from DWD's Stationslexikon where the ids are DWD station ids (GH-4162).

Of the datasets of `dwd/derived`, the degree days, the degree hours and the soil list stations by the id DWD's own
stations have (`KL_Monatswerte_Beschreibung_Stationen.txt`, `stations_list_soil.txt`), which the Stationslexikon holds
the WMO number of. The radiation and the sunshine duration of DUETT list ids of their own (`18xxx`, 0 of 576 in the
Stationslexikon), and the climate correction factor lists postal codes, so a number found for their ids would be the
number of another station: they stay null, and a request for them does not read the Stationslexikon at all. The
stub of the Stationslexikon is `tests/provider/dwd/observation/stationslexikon_rows.py`, which the autouse fixture of
`tests/conftest.py` serves to every offline test.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.dwd.observation.stationslexikon_rows import page
from wetterdienst import Settings
from wetterdienst.exceptions import NoInternetError
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import metaindex as derived_metaindex
from wetterdienst.provider.dwd.derived.metadata import DWD_STATION_ID_DATASETS, DwdDerivedMetadata
from wetterdienst.provider.dwd.observation import fileindex as dwd_fileindex
from wetterdienst.provider.dwd.observation import stationslexikon
from wetterdienst.provider.dwd.observation.stationslexikon import STATIONSLEXIKON_URL, WMO_IDS_UNAVAILABLE
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable

# lines of `KL_Monatswerte_Beschreibung_Stationen.txt` (2026-11-16), cut at the blanks they are padded with:
# Großenkneten (the Stationslexikon has an id of DWD's own for it), Berlin-Dahlem and Berlin-Tempelhof
_KL_MONATSWERTE = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "---------- ------\r\n"
    "00044 19710301 20261031             44     52.9336    8.2370 Großenkneten                             "
    "Niedersachsen                            Frei\r\n"
    "00403 19500101 20261031             51     52.4537   13.3017 Berlin-Dahlem (FU)                       "
    "Berlin                                   Frei\r\n"
    "00433 19180401 20261031             48     52.4676   13.4020 Berlin-Tempelhof                         "
    "Berlin                                   Frei\r\n"
)
# `stations_list_soil.txt` (2026-10-21): Großenkneten, Doberlug-Kirchhain and Dresden-Klotzsche
_SOIL = (
    "Stationsindex; Höhe in m;Breite   ;Länge    ;Name;Bundesland\r\n"
    "           44;        44;    52.93;     8.24;Großenkneten;Niedersachsen\r\n"
    "         1001;        97;    51.65;    13.57;Doberlug-Kirchhain;Brandenburg\r\n"
    "         1048;       228;    51.13;    13.75;Dresden-Klotzsche;Sachsen\r\n"
)
# `fg_duett_Beschreibung_Stationen.txt` (2026-10-15): the DUETT stations are the 18xxx
_DUETT = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "----------\r\n"
    "18000 20240401 20261014            680     47.9736    8.5205 Donaueschingen (Landeplatz)_DUETT        "
    "Baden-Württemberg\r\n"
    "18001 20240401 20261014             44     52.9336    8.2370 Großenkneten_DUETT                       "
    "Niedersachsen\r\n"
)
_BASE = "https://opendata.dwd.de/climate_environment/CDC/derived_germany"


def _listing(url: str, **_: object) -> list[str]:
    """Name the files of a directory of `derived_germany` as DWD lists them, for the stations of the lists above."""
    if "soil" in url:
        return [f"{url.rstrip('/')}/derived_germany_soil_daily_recent_v2_{index}.txt.gz" for index in (44, 1001, 1048)]
    if "duett" in url:
        return [f"{url}/stundenwerte_duett_FG_{station_id}_akt.zip" for station_id in ("18000", "18001")]
    # the technical datasets are a file for each month, whatever the stations
    return [f"{url}/gradtage_202510.csv"]


@pytest.fixture(autouse=True)
def _lists_of_the_stations(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Serve the station lists of the datasets and the listing of the directories, to the tests that are not remote."""
    if request.node.get_closest_marker("remote"):
        return
    bodies = {"KL_Monatswerte": _KL_MONATSWERTE, "stations_list_soil": _SOIL, "fg_duett": _DUETT, "sd_duett": _DUETT}

    def download_file(*, url: str, **_: object) -> File:
        for part, body in bodies.items():
            if part in url:
                return File(url=url, content=BytesIO(body.encode("latin-1")), status=200)
        msg = f"the stub serves nothing for {url}"
        raise AssertionError(msg)

    monkeypatch.setattr(derived_metaindex, "download_file", download_file)
    monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", _listing)


def _request(*parameters: tuple[str, str]) -> DwdDerivedRequest:
    return DwdDerivedRequest(parameters=list(parameters), periods="recent", settings=Settings(cache_disable=True))


def _wmo_ids(frame: pl.DataFrame) -> dict[tuple[str, str], str | None]:
    return {
        (dataset, station_id): wmo_id
        for dataset, station_id, wmo_id in zip(frame["dataset"], frame["station_id"], frame["wmo_id"], strict=True)
    }


def test_the_datasets_that_are_filled_are_the_ones_with_dwd_station_ids() -> None:
    """The degree days, the degree hours and the soil: not the DUETT radiation and sunshine, not the postal codes."""
    assert {(dataset.resolution.name, dataset.name) for dataset in DWD_STATION_ID_DATASETS} == {
        ("monthly", "heating_degreedays"),
        ("monthly", "cooling_degreehours_13"),
        ("monthly", "cooling_degreehours_16"),
        ("monthly", "cooling_degreehours_18"),
        ("daily", "soil"),
        ("monthly", "soil"),
    }
    every_dataset = {
        (dataset.resolution.name, dataset.name) for resolution in DwdDerivedMetadata for dataset in resolution
    }
    left_out = every_dataset - {(dataset.resolution.name, dataset.name) for dataset in DWD_STATION_ID_DATASETS}
    assert left_out == {
        ("hourly", "radiation_global"),
        ("hourly", "sunshine_duration"),
        ("monthly", "climate_correction_factor"),
    }


@pytest.mark.parametrize("dataset", ["heating_degreedays", "cooling_degreehours_13", "cooling_degreehours_16"])
def test_the_degree_days_and_hours_carry_the_wmo_id_of_their_station(dataset: str) -> None:
    """Berlin-Tempelhof `00433` is 10384 and Berlin-Dahlem `00403` is 10381; Großenkneten has an id of DWD's own."""
    stations = _request(("monthly", dataset)).all().df
    assert stations.schema["wmo_id"] == pl.String
    assert _wmo_ids(stations) == {(dataset, "00044"): None, (dataset, "00403"): "10381", (dataset, "00433"): "10384"}


@pytest.mark.parametrize("resolution", ["daily", "monthly"])
def test_the_soil_stations_carry_the_wmo_id_of_their_station(resolution: str) -> None:
    """Dresden-Klotzsche `01048` is 10488; Großenkneten (an id of DWD's own) and Doberlug-Kirchhain have none."""
    stations = _request((resolution, "soil")).all().df
    assert _wmo_ids(stations) == {("soil", "00044"): None, ("soil", "01001"): None, ("soil", "01048"): "10488"}


def test_a_search_by_wmo_id_finds_the_stations_of_the_datasets_that_are_filled() -> None:
    """`filter_by_wmo_id` is the core's, which reads the column: it finds Tempelhof by 10384 and Dresden by 10488."""
    degree_days = _request(("monthly", "heating_degreedays"))
    assert degree_days.filter_by_wmo_id("10384").df["station_id"].to_list() == ["00433"]
    assert degree_days.filter_by_wmo_id(10381).df["station_id"].to_list() == ["00403"]
    assert degree_days.filter_by_wmo_id(["10381", "10384"]).df["station_id"].to_list() == ["00403", "00433"]
    assert degree_days.filter_by_wmo_id("10488").df.is_empty()
    assert _request(("daily", "soil")).filter_by_wmo_id("10488").df["station_id"].to_list() == ["01048"]


def test_a_dataset_with_another_id_scheme_has_no_wmo_id_whatever_its_ids_are_in_the_stationslexikon() -> None:
    """The postal code `00433` is no station: it is Berlin-Tempelhof's id in the Stationslexikon, and that is chance."""
    postal_codes = _request(("monthly", "climate_correction_factor")).filter_by_station_id(["00433", "01048"]).df
    assert postal_codes["station_id"].to_list() == ["00433", "01048"]
    assert postal_codes["wmo_id"].to_list() == [None, None]
    assert postal_codes.schema["wmo_id"] == pl.String
    # and the DUETT ids are 18xxx: none is in the table, and null is what the table would have said as well
    duett = _request(("hourly", "radiation_global")).all().df
    assert duett["station_id"].to_list() == ["18000", "18001"]
    assert duett["wmo_id"].to_list() == [None, None]
    assert duett.schema["wmo_id"] == pl.String


def test_each_dataset_of_a_request_has_the_number_its_own_ids_have() -> None:
    """A request of datasets of all three kinds: the numbers go to the degree days and the soil, and to none else."""
    stations = (
        _request(
            ("monthly", "heating_degreedays"),
            ("hourly", "sunshine_duration"),
            ("monthly", "climate_correction_factor"),
            ("daily", "soil"),
        )
        .filter_by_station_id(["00433", "01048", "18000"])
        .df
    )
    assert _wmo_ids(stations) == {
        ("heating_degreedays", "00433"): "10384",
        ("climate_correction_factor", "00433"): None,
        ("soil", "01048"): "10488",
        ("climate_correction_factor", "01048"): None,
        ("climate_correction_factor", "18000"): None,
        ("sunshine_duration", "18000"): None,
    }


@pytest.mark.parametrize(
    ("parameters", "station_id"),
    [
        (("hourly", "radiation_global"), "18000"),
        (("hourly", "sunshine_duration"), "18001"),
        (("monthly", "climate_correction_factor"), "00433"),
    ],
    ids=["radiation_global", "sunshine_duration", "climate_correction_factor"],
)
def test_a_dataset_with_another_id_scheme_does_not_read_the_stationslexikon(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, parameters: tuple[str, str], station_id: str
) -> None:
    """The table is 5.9 MB and its page another host's: a lookup that needs no number neither reads nor warns of it."""

    def read(*_args: object, **_kwargs: object) -> None:
        msg = "the Stationslexikon was read for a dataset whose ids are no DWD station ids"
        raise AssertionError(msg)

    monkeypatch.setattr(stationslexikon, "read_wmo_ids", read)
    monkeypatch.setattr(stationslexikon, "download_file", read)
    begin_response()
    with caplog.at_level(logging.WARNING, logger=stationslexikon.log.name):
        stations = _request(parameters).filter_by_station_id(station_id).df
    assert stations["station_id"].to_list() == [station_id]
    assert stations["wmo_id"].to_list() == [None]
    assert not [w for w in recorded_warnings() if w["code"] == WMO_IDS_UNAVAILABLE]
    assert not caplog.records


def _unreadable(monkeypatch: pytest.MonkeyPatch, what: Callable[..., File]) -> None:
    monkeypatch.setattr(stationslexikon, "download_file", what)


def test_a_page_that_is_not_the_table_leaves_the_stations_without_wmo_id_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """As for `dwd/observation`: the stations are the answer and the number an addition, with the warning."""
    _unreadable(
        monkeypatch,
        lambda *, url, **_: File(url=url, content=BytesIO(page(headers=("a",) * 11)), status=200),
    )
    begin_response()
    with caplog.at_level(logging.WARNING, logger=stationslexikon.log.name):
        stations = _request(("monthly", "heating_degreedays")).all().df
    assert stations["station_id"].to_list() == ["00044", "00403", "00433"]
    assert stations["wmo_id"].null_count() == stations.height
    assert stations.schema["wmo_id"] == pl.String
    (warning,) = [w for w in recorded_warnings() if w["code"] == WMO_IDS_UNAVAILABLE]
    assert STATIONSLEXIKON_URL in warning["message"]


def test_a_connection_that_cannot_be_made_leaves_the_stations_without_wmo_id_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`www.dwd.de` is not the host the stations are listed from: no connection to it must not fail the lookup."""

    def fail(*, url: str, **_: object) -> File:
        return File(url=url, content=NoInternetError(url), status=0)

    _unreadable(monkeypatch, fail)
    begin_response()
    stations = _request(("daily", "soil")).all().df
    assert stations["station_id"].to_list() == ["00044", "01001", "01048"]
    assert stations["wmo_id"].null_count() == stations.height
    assert [w["code"] for w in recorded_warnings() if w["code"] == WMO_IDS_UNAVAILABLE] == [WMO_IDS_UNAVAILABLE]


# the live page and the live lists


@pytest.mark.remote
def test_the_live_degree_days_and_soil_stations_carry_the_wmo_id_and_the_others_do_not() -> None:
    """Berlin-Tempelhof `00433` is 10384 in the degree days, Dresden-Klotzsche `01048` 10488 in the soil.

    Read 2026-11-16: 270 of the 1,226 stations of the degree days and the degree hours and 198 of the 484 of the soil
    have a number (the names of the Stationslexikon agree with the lists for all of them), none of the 576 DUETT
    stations, and a postal code has none.
    """
    settings = Settings(cache_disable=True)
    degree_days = DwdDerivedRequest(parameters=[("monthly", "heating_degreedays")], periods="recent", settings=settings)
    stations = degree_days.all().df
    assert stations.filter(pl.col("station_id") == "00433")["wmo_id"].to_list() == ["10384"]
    assert 200 <= stations["wmo_id"].drop_nulls().len() <= stations.height
    assert degree_days.filter_by_wmo_id("10381").df["station_id"].to_list() == ["00403"]
    soil = DwdDerivedRequest(parameters=[("daily", "soil")], settings=settings).all().df
    assert soil.filter(pl.col("station_id") == "01048")["wmo_id"].to_list() == ["10488"]
    assert soil.filter(pl.col("station_id") == "00044")["wmo_id"].to_list() == [None]
    duett = DwdDerivedRequest(parameters=[("hourly", "radiation_global")], settings=settings).all().df
    assert duett["wmo_id"].null_count() == duett.height
    postal_codes = DwdDerivedRequest(parameters=[("monthly", "climate_correction_factor")], settings=settings)
    assert postal_codes.filter_by_station_id("00433").df["wmo_id"].to_list() == [None]
