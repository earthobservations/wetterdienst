# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The station catalogues are held to their data: a listed station has data, a data file has a station (GH-3248).

The rules are `check_coverage` of `station_catalogue.py`; the ids of the data files of each network are read by
`station_data_index.py`. This module holds the rules to what each stub of a catalogue serves beside it, and holds the
networks to being either in `INDEXES` or named in `NOT_HELD` with the reason. The live lists are held in
`test_station_catalogues_live.py`.
"""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from tests.provider.station_catalogue import COVERAGE_RULES, Accepted, assert_covered, check_coverage
from tests.provider.station_catalogue_stubs import STUBS, Stub
from tests.provider.station_data_index import (
    ACCEPTED_LIVE,
    ACCEPTED_STUB,
    INDEXES,
    NOT_HELD,
    NOT_HELD_DATASETS,
    NOT_LIVE,
    dataset_of,
)
from wetterdienst import Settings, Wetterdienst
from wetterdienst.provider.dwd.observation import fileindex as dwd_fileindex
from wetterdienst.ui.core import resolve_network

_SCHEMA = {"resolution": pl.String, "dataset": pl.String, "station_id": pl.String}


def _frame(*station_ids: str | None) -> pl.DataFrame:
    return pl.DataFrame(
        [{"resolution": "daily", "dataset": "data", "station_id": station_id} for station_id in station_ids],
        schema=_SCHEMA,
    )


def _rules_of(stations: pl.DataFrame, data_ids: list[str], **kwargs: Any) -> dict[str, list[str | None]]:  # noqa: ANN401
    found: dict[str, list[str | None]] = {}
    for violation in check_coverage(stations, data_ids, "test", **kwargs):
        found.setdefault(violation.rule, []).append(violation.station_id)
    return found


def test_a_catalogue_that_matches_its_data_breaks_no_rule() -> None:
    """The same ids on both sides break nothing, whatever their order, and a repeated file is no new station."""
    assert _rules_of(_frame("00044", "00071"), ["00071", "00044", "00044"]) == {}


def test_a_station_without_a_file_is_missing_its_data() -> None:
    """A listed station that no data file is named for breaks `data_missing`, and names the station."""
    assert _rules_of(_frame("00044", "00071"), ["00044"]) == {"data_missing": ["00071"]}


def test_a_file_without_a_station_is_an_orphan() -> None:
    """A data file of a station the list does not carry breaks `data_orphan`, and names the station."""
    assert _rules_of(_frame("00044"), ["00044", "00071", "00099"]) == {"data_orphan": ["00071", "00099"]}


@pytest.mark.parametrize(
    ("listed", "data"),
    [
        ("00044", "44"),  # a padding the reader did not put back
        ("44", "00044"),  # one the file name has and the list has not
        ("SMA", "sma"),  # a case
        ("00044", " 00044"),  # a blank around it
    ],
)
def test_one_id_in_two_spellings_breaks_both_rules_and_says_so(listed: str, data: str) -> None:
    """An id that differs only in padding, case or blanks is a station without data and a file without a station."""
    violations = check_coverage(_frame(listed), [data], "test")
    assert {violation.rule for violation in violations} == set(COVERAGE_RULES)
    assert all("padding or case" in violation.detail for violation in violations)
    assert {violation.station_id for violation in violations} == {listed, data}


def test_an_unrelated_id_is_not_taken_for_a_spelling() -> None:
    """Two ids that differ in more than padding or case are two stations, with no hint."""
    violations = check_coverage(_frame("00044"), ["00045"], "test")
    assert len(violations) == 2
    assert not any("padding or case" in violation.detail for violation in violations)


def test_a_source_that_cannot_be_held_to_both_rules_is_held_to_one() -> None:
    """The rules to apply are chosen, so a feed of the last day is held to its orphans, not its silent stations."""
    assert _rules_of(_frame("1"), ["2"], rules=("data_orphan",)) == {"data_orphan": ["2"]}
    assert _rules_of(_frame("1"), ["2"], rules=("data_missing",)) == {"data_missing": ["1"]}
    assert _rules_of(_frame("1"), ["2"], rules=()) == {}


def test_a_rule_that_does_not_exist_is_refused() -> None:
    """A misspelled rule would apply nothing and pass everything, so it is an error."""
    with pytest.raises(AssertionError, match="unknown coverage rules"):
        check_coverage(_frame("1"), ["2"], "test", rules=("data_orphans",))


def test_a_violation_names_the_catalogue_station_and_rule() -> None:
    """A failure says where to look: the catalogue, the station and the rule."""
    (violation,) = check_coverage(_frame("00044"), ["00044", "00071"], "dwd/observation daily/climate_summary")
    assert str(violation).startswith("dwd/observation daily/climate_summary: data_orphan: station '00071': ")


def test_an_exception_covers_the_stations_it_names_and_nothing_else() -> None:
    """An exception for some stations lets those through and still fails the others, orphans and missing alike."""
    accepted = [Accepted("data_orphan", "the source forgot it", where=lambda row: row["station_id"] == "00071")]
    assert_covered(_frame("00044"), ["00044", "00071"], "test", accepted=accepted)
    with pytest.raises(AssertionError, match="data_orphan: station '00099'"):
        assert_covered(_frame("00044"), ["00044", "00071", "00099"], "test", accepted=accepted)
    with pytest.raises(AssertionError, match="data_missing: station '00044'"):
        assert_covered(_frame("00044", "00011"), ["00011", "00071"], "test", accepted=accepted)


def test_an_exception_can_tell_the_dataset_of_an_orphan() -> None:
    """The row of an orphan carries its resolution and dataset, so an exception can be about one dataset."""
    (violation,) = check_coverage(_frame("00044"), ["00044", "00071"], "test")
    assert violation.row == {"station_id": "00071", "resolution": "daily", "dataset": "data"}


def test_an_exception_that_matches_nothing_fails() -> None:
    """A fixed mismatch cannot leave its exception behind, and an exception for a rule not applied is refused."""
    accepted = [Accepted("data_orphan", "the source forgot it")]
    with pytest.raises(AssertionError, match="the exception for data_orphan matches no station: the source forgot it"):
        assert_covered(_frame("00044"), ["00044"], "test", accepted=accepted)
    # the live pass cannot hold to that, as a source that fixes a defect is no failure of ours
    assert_covered(_frame("00044"), ["00044"], "test", accepted=accepted, fail_on_stale=False)
    with pytest.raises(AssertionError, match="not applied to this source"):
        assert_covered(_frame("00044"), ["00044"], "test", accepted=accepted, rules=("data_missing",))


def test_an_empty_catalogue_or_listing_is_not_covered() -> None:
    """A rule over nothing passes whatever is wrong, so an empty catalogue or an empty listing fails."""
    with pytest.raises(AssertionError, match="the catalogue is empty"):
        assert_covered(_frame(), ["00044"], "test")
    with pytest.raises(AssertionError, match="no data file is listed"):
        assert_covered(_frame("00044"), [], "test")


def test_failures_beyond_the_limit_are_counted_not_listed() -> None:
    """A source with a thousand orphans fails with a short list."""
    stations = _frame("00001")
    with pytest.raises(AssertionError, match=r"data_orphan: \.\.\. and 3 more"):
        assert_covered(stations, ["00001", *(f"1000{index}" for index in range(5))], "test", limit=2)


def test_a_missing_id_in_the_catalogue_is_no_station_to_find() -> None:
    """A row with no id breaks `id_empty` and is not reported again as a station without data."""
    assert _rules_of(_frame("00044", None), ["00044"]) == {}


def _networks_with_a_catalogue() -> set[str]:
    networks = set()
    for provider, names in Wetterdienst.registry.items():
        for name in names:
            if getattr(resolve_network(provider, name), "metadata", None) is not None:
                networks.add(f"{provider}/{name}")
    return networks


def test_every_network_is_held_or_named_with_the_reason() -> None:
    """A new network is held to the coverage rules or says why it cannot be, and no network is both."""
    networks = _networks_with_a_catalogue()
    assert not set(INDEXES) & set(NOT_HELD), "a network is held and not held"
    unaccounted = networks - set(INDEXES) - set(NOT_HELD)
    assert not unaccounted, f"add {sorted(unaccounted)} to INDEXES, or to NOT_HELD with the reason"
    gone = (set(INDEXES) | set(NOT_HELD)) - networks
    assert not gone, f"{sorted(gone)} has no station catalogue (any more)"


def test_every_reason_is_given() -> None:
    """A reason is a sentence that says what the source does not have, not an empty string."""
    reasons = {**NOT_HELD, **NOT_HELD_DATASETS, **NOT_LIVE}
    assert all(len(reason.split()) > 3 for reason in reasons.values()), [
        key for key, reason in reasons.items() if len(reason.split()) <= 3
    ]


def test_the_datasets_and_networks_that_are_named_exist() -> None:
    """A dataset that is not held, or a network that is not live, is one of a network that is held."""
    for key in NOT_HELD_DATASETS:
        network, _, parameter = key.partition(" ")
        resolution, _, dataset = parameter.partition("/")
        assert network in INDEXES, f"{key}: {network} is not held"
        dataset_of(network, resolution, dataset)
    assert set(NOT_LIVE) <= set(INDEXES)
    assert set(ACCEPTED_LIVE) <= set(INDEXES)


def test_the_dwd_listings_are_read_by_a_pattern_that_takes_short_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the stations of a DWD directory whatever the digits of the id, which the file index of the provider cannot.

    The soil files of the stations 44, 73, 78, 91 and 96 carry no padding, and `SOIL_ID_REGEX` of the provider needs
    three digits, so those stations are dropped on both sides of a join and no rule fires (GH-3257). The soil names are
    those of `soil/daily/historical/` as listed on 2026-10-21. The names of the zip files are made up, but for the
    third: no zip of DWD has an unpadded id today, so a short one is a precaution, and the name with a leading
    underscore stands for the temporary files DWD once published under `10_minutes/extreme_wind/now`.
    """
    names = {
        "soil": [
            "derived_germany_soil_daily_historical_v2_44.txt.gz",
            "derived_germany_soil_daily_historical_v2_1001.txt.gz",
            "derived_germany_soil_daily_historical_stations_list.txt",
            "BESCHREIBUNG_derived_ermany_soil_daily_historical_de_v2.pdf",
            "AMBETI.pdf",
        ],
        "zip": [
            "stundenwerte_air_temperature_44_akt.zip",
            "KL_Tageswerte_Beschreibung_Stationen.txt",
            "tageswerte_KL_00001_19370101_19860630_hist.zip",
            "_tageswerte_KL_00002_19370101_19860630_hist.zip",
        ],
    }
    settings = Settings(cache_disable=True)

    def serve(key: str) -> None:
        listed = [f"https://opendata.dwd.de/climate_environment/CDC/{name}" for name in names[key]]
        monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", lambda *_args, **_kwargs: listed)

    serve("soil")
    ids = INDEXES["dwd/derived"].ids(settings, dataset_of("dwd/derived", "daily", "soil"))
    assert ids == {"00044", "01001"}
    serve("zip")
    ids = INDEXES["dwd/observation"].ids(settings, dataset_of("dwd/observation", "daily", "climate_summary"))
    assert ids == {"00044", "00001"}


def _held_stubs() -> list[Stub]:
    """Give the stubs of the datasets that are held."""
    return [
        stub for stub in STUBS if stub.catalogue.split(" ")[0] in INDEXES and stub.catalogue not in NOT_HELD_DATASETS
    ]


def _stub_dataset(stub: Stub) -> tuple[str, str, str]:
    network, parameter = stub.catalogue.split(" ")
    resolution, _, dataset = parameter.partition("/")
    return network, resolution, dataset


def test_every_held_network_has_a_stub_that_is_held() -> None:
    """The offline check of a network is its stub, so a network that is held has one, and so has an exception."""
    held = {stub.catalogue.split(" ")[0] for stub in _held_stubs()}
    assert set(INDEXES) <= held, f"{sorted(set(INDEXES) - held)} have no stub of a dataset that is held"
    stubs = {stub.catalogue for stub in _held_stubs()}
    assert set(ACCEPTED_STUB) <= stubs, f"{sorted(set(ACCEPTED_STUB) - stubs)} are no stub that is held"


@pytest.mark.parametrize("stub", _held_stubs(), ids=lambda stub: stub.catalogue)
def test_a_stub_catalogue_has_its_data(stub: Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold the stations of a stub to the data files it serves beside them, naming the station and rule that fails.

    The ids of the files are read from the listing or feed the stub serves beside the catalogue, the way the provider
    reads it (for the DWD networks the raw listing, with a pattern of `station_data_index.py`, not the file index).
    A reader that joins the list to the files (`dwd/observation`, `dwd/derived`, `dwd/poi`, `dwd/dmo`) shows what it
    drops silently, a file whose station the list does not carry, as `dwd/observation` does with 01018; one that does
    not join (`chmi/observation`, `meteoswiss/observation`) shows a station it lists and has no file for.
    """
    network, resolution, dataset = _stub_dataset(stub)
    stations = stub.build(monkeypatch)
    index = INDEXES[network]
    ids = index.ids(Settings(cache_disable=True), dataset_of(network, resolution, dataset))
    assert_covered(
        stations,
        ids,
        stub.catalogue,
        accepted=ACCEPTED_STUB.get(stub.catalogue, ()),
        rules=index.rules,
    )
