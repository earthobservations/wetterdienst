# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A station with data files and no line in the station description is told, not dropped silently (GH-3258)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tests.provider import station_catalogue_stubs
from tests.provider.station_catalogue_stubs import _dwd_derived_soil, _dwd_observation
from wetterdienst import Settings
from wetterdienst.provider.dwd.coverage import warn_files_without_description
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.observation import fileindex as dwd_fileindex

if TYPE_CHECKING:
    import polars as pl
    import pytest

LOGGER = "wetterdienst.provider.dwd.coverage"


def _read_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let a stub read the stations of the reader and not hand them through the core, which the snapshot holds."""

    def stations(request_class: type, *parameters: tuple[str, str], **kwargs: object) -> pl.DataFrame:
        request = request_class(parameters=list(parameters), settings=Settings(cache_disable=True), **kwargs)
        return request._all().collect()  # noqa: SLF001

    monkeypatch.setattr(station_catalogue_stubs, "_stations", stations)


def _messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == LOGGER]


def test_nothing_is_said_when_every_file_has_a_line(caplog: pytest.LogCaptureFixture) -> None:
    """Hold the log silent for a dataset whose files all have a line."""
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        warn_files_without_description("dwd/observation", "daily/kl", ["00001", "00003"], ["00001", "00003", "00106"])
    assert _messages(caplog) == []


def test_the_stations_without_a_line_are_named(caplog: pytest.LogCaptureFixture) -> None:
    """Name each station of the file index that the description lacks, in order, and count them."""
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        warn_files_without_description("dwd/observation", "daily/kl", ["05047", "00001", "01018"], ["00001"])
    (message,) = _messages(caplog)
    assert message.startswith("dwd/observation daily/kl: the server has data files of 2 station(s)")
    assert message.endswith("cannot be requested: 01018, 05047 (GH-3258)")


def test_a_long_list_of_stations_is_cut_and_counted(caplog: pytest.LogCaptureFixture) -> None:
    """Name the first twenty and count the rest."""
    file_ids = [f"{number:05d}" for number in range(1, 26)]
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        warn_files_without_description("dwd/observation", "daily/kl", file_ids, [])
    (message,) = _messages(caplog)
    assert "of 25 station(s)" in message
    assert message.endswith("00020 and 5 more (GH-3258)")


def test_observation_names_the_file_of_a_station_the_description_lacks(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The stub serves a file for 01018 and no line for it: the station stays out of the list, and the log says why."""
    _read_the_list(monkeypatch)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        stations = _dwd_observation(monkeypatch)
    assert "01018" not in stations.get_column("station_id").to_list()
    (message,) = _messages(caplog)
    assert message.startswith("dwd/observation daily/climate_summary: the server has data files of 1 station(s)")
    # Altenau (00106) is described and has no file, which is no station that the description lacks
    assert message.endswith("cannot be requested: 01018 (GH-3258)")


def test_derived_names_the_file_of_a_station_the_description_lacks(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Serve the soil stub's list and a file for station 1584, which the list does not carry."""
    _read_the_list(monkeypatch)
    _dwd_derived_soil(monkeypatch)
    base = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/daily/recent/"
    files = [f"{base}derived_germany_soil_daily_recent_v2_{index}.txt.gz" for index in ("44", "73", "1001", "1584")]
    monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", lambda *_args, **_kwargs: files)
    request = DwdDerivedRequest(parameters=[("daily", "soil")], settings=Settings(cache_disable=True))
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        stations = request._all().collect()  # noqa: SLF001
    assert stations.get_column("station_id").to_list() == ["00044", "00073", "01001"]
    (message,) = _messages(caplog)
    assert message.startswith("dwd/derived daily/soil: the server has data files of 1 station(s)")
    assert message.endswith("cannot be requested: 01584 (GH-3258)")
