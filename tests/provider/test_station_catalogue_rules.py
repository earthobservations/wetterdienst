# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The station catalogue rules fire on the defect each names and stay quiet on a sound catalogue (GH-2616)."""

import datetime as dt
from typing import Any

import polars as pl
import pytest

from tests.provider.station_catalogue import (
    COUNTRY_BBOX,
    RULES,
    Accepted,
    assert_sound,
    check_catalogue,
    unaccepted,
)

_NOW = dt.datetime(2026, 10, 10, tzinfo=dt.timezone.utc)
_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "station_id": pl.String,
    "start_timestamp": pl.Datetime(time_zone="UTC"),
    "end_timestamp": pl.Datetime(time_zone="UTC"),
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "elevation": pl.Float64,
    "name": pl.String,
    "region": pl.String,
}
_GERMANY = COUNTRY_BBOX["dwd/observation"]


def _station(**fields: Any) -> dict[str, Any]:  # noqa: ANN401
    """Make a sound station of a German catalogue, with the fields a test breaks."""
    return {
        "resolution": "daily",
        "dataset": "kl",
        "station_id": "00044",
        "start_timestamp": dt.datetime(1971, 3, 1, tzinfo=dt.timezone.utc),
        "end_timestamp": dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc),
        "latitude": 52.9336,
        "longitude": 8.2370,
        "elevation": 44.0,
        "name": "Großenkneten",
        "region": "Niedersachsen",
    } | fields


def _frame(*stations: dict[str, Any]) -> pl.DataFrame:
    return pl.DataFrame(list(stations), schema=_SCHEMA, orient="row")


def _rules_of(*stations: dict[str, Any], bbox: tuple[float, float, float, float] | None = _GERMANY) -> set[str]:
    return {violation.rule for violation in check_catalogue(_frame(*stations), "test", bbox=bbox, now=_NOW)}


def test_a_sound_catalogue_breaks_no_rule() -> None:
    """A catalogue of ordinary stations, and of the awkward but sound ones, breaks no rule."""
    stations = [
        _station(),
        _station(station_id="00071", name="Albstadt-Badkap", latitude=48.2156, longitude=8.9784, elevation=759.0),
        # the same id in another dataset is another station, and a missing end is a station still reporting
        _station(dataset="more_precip", end_timestamp=None),
        _station(station_id="1048", elevation=None, start_timestamp=None, region=None),
        # a station on the Greenwich meridian is not a missing longitude
        _station(station_id="07621", latitude=43.188, longitude=0.0),
        # a capital A with a tilde is a letter in Portuguese, and Å and Ä are letters elsewhere
        _station(station_id="SP1", name="SÃO JOÃO ÅKERSBERGA ÄNGELHOLM ÄÄNEKOSKI"),
    ]
    assert_sound(_frame(*stations), "test", now=_NOW)
    assert check_catalogue(_frame(*stations), "test", now=_NOW) == []


_CASES = [
    ("id_empty", [_station(station_id="")]),
    ("id_empty", [_station(station_id=None)]),
    ("id_whitespace", [_station(station_id="00044 ")]),
    ("id_duplicate", [_station(), _station(name="Elsewhere")]),
    ("id_collision", [_station(station_id="00044"), _station(station_id="44")]),
    ("id_collision", [_station(station_id="ABC"), _station(station_id="abc")]),
    ("coordinates_missing", [_station(latitude=None)]),
    ("coordinates_missing", [_station(longitude=None)]),
    ("coordinates_out_of_range", [_station(latitude=135.117, longitude=48.8)]),
    ("coordinates_out_of_range", [_station(longitude=-190.0)]),
    ("coordinates_null_island", [_station(latitude=0.0, longitude=0.0)]),
    ("coordinates_outside_country", [_station(latitude=8.237, longitude=52.9336)]),
    ("coordinates_outside_country", [_station(longitude=-8.237)]),
    ("elevation_sentinel", [_station(elevation=-999.0)]),
    ("elevation_sentinel", [_station(elevation=9999.0)]),
    ("elevation_out_of_range", [_station(elevation=-500.0)]),
    ("elevation_out_of_range", [_station(elevation=14500.0)]),  # feet read as metres
    (
        "date_order",
        [
            _station(
                start_timestamp=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
                end_timestamp=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
            )
        ],
    ),
    ("date_in_the_future", [_station(end_timestamp=dt.datetime(2100, 12, 31, tzinfo=dt.timezone.utc))]),
    (
        "date_in_the_future",
        [_station(start_timestamp=dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc), end_timestamp=None)],
    ),
    ("date_implausible", [_station(start_timestamp=dt.datetime(1066, 1, 1, tzinfo=dt.timezone.utc))]),
    ("name_empty", [_station(name="")]),
    ("name_empty", [_station(name=None)]),
    ("name_padding", [_station(name="Großenkneten ")]),
    ("name_padding", [_station(name=" Großenkneten")]),
    ("name_encoding", [_station(name="GroÃŸenkneten")]),
    ("name_encoding", [_station(name="Gro\ufffdenkneten")]),
    ("name_encoding", [_station(name="Gro?enkneten")]),
    ("name_encoding", [_station(name="DzierÅ¼kowice")]),  # ż, which is C5 BC in UTF-8
    ("name_encoding", [_station(name="LUDÅ¹MIERZ")]),  # Ź
    ("name_encoding", [_station(name="Anykšči\u00c5\u00b3")]),  # ų
]


@pytest.mark.parametrize(("rule", "stations"), _CASES)
def test_each_rule_fires_on_the_defect_it_names(rule: str, stations: list[dict[str, Any]]) -> None:
    """Every rule finds the defect it is named for."""
    assert rule in _rules_of(*stations)


def test_every_rule_has_a_case_above() -> None:
    """No rule is left without a defect that it is seen to find."""
    assert {rule for rule, _ in _CASES} == set(RULES)


def test_a_station_outside_the_country_says_what_looks_wrong_with_it() -> None:
    """A position that fits the country after a swap or a sign says which, so a reader can fix it."""

    def detail(station: dict[str, Any]) -> str:
        (violation,) = check_catalogue(_frame(station), "test", bbox=_GERMANY, now=_NOW)
        return violation.detail

    assert "swapped" in detail(_station(latitude=8.237, longitude=52.9336))
    assert "longitude lost its sign" in detail(_station(longitude=-8.237))
    assert "latitude lost its sign" in detail(_station(latitude=-52.9336))
    assert "swapped" not in detail(_station(latitude=-12.0, longitude=130.0))


def test_the_country_is_only_held_against_a_catalogue_that_has_one() -> None:
    """A global catalogue has no country to be outside of, and a missing position is not outside either."""
    far = _station(latitude=-12.0, longitude=130.0)
    assert "coordinates_outside_country" in _rules_of(far)
    assert "coordinates_outside_country" not in _rules_of(far, bbox=None)
    # a station without a position breaks "missing", not "outside"
    assert _rules_of(_station(latitude=None, longitude=None)) == {"coordinates_missing"}


def test_the_same_id_in_two_datasets_is_not_a_duplicate() -> None:
    """Resolutions and datasets share a catalogue, so an id repeats across them without being listed twice."""
    assert _rules_of(_station(), _station(dataset="more_precip"), _station(resolution="hourly")) == set()


def test_a_violation_names_the_catalogue_station_and_rule() -> None:
    """A failure says where to look: the catalogue, the station and the rule."""
    violations = check_catalogue(_frame(_station(station_id="00071", elevation=9999.0)), "dwd/observation", now=_NOW)
    (violation,) = [violation for violation in violations if violation.rule == "elevation_sentinel"]
    assert str(violation).startswith("dwd/observation: elevation_sentinel: station '00071': ")


def test_an_exception_covers_the_stations_it_names_and_nothing_else() -> None:
    """An exception for some stations lets those through and still fails the others."""
    stations = _frame(_station(name="Bad "), _station(station_id="00071", name="Worse "))
    violations = check_catalogue(stations, "test", now=_NOW)
    accepted = Accepted("name_padding", "the source pads it", where=lambda row: row["station_id"] == "00071")
    left, stale = unaccepted(violations, [accepted])
    assert [violation.station_id for violation in left] == ["00044"]
    assert stale == []
    with pytest.raises(AssertionError, match="station '00044'"):
        assert_sound(stations, "test", accepted=[accepted], now=_NOW)


def test_an_exception_that_matches_nothing_fails() -> None:
    """A fixed defect cannot leave its exception behind."""
    accepted = Accepted("name_padding", "the source pads it")
    with pytest.raises(AssertionError, match="the exception for name_padding matches no station: the source pads it"):
        assert_sound(_frame(_station()), "test", accepted=[accepted], now=_NOW)


def test_an_exception_needs_a_known_rule_and_a_reason() -> None:
    """An exception is named by a rule that exists and says why."""
    with pytest.raises(ValueError, match="unknown rule 'name_pading'"):
        Accepted("name_pading", "a typo")
    with pytest.raises(ValueError, match="has no reason"):
        Accepted("name_padding", " ")


def test_an_empty_catalogue_is_not_sound() -> None:
    """A rule over no stations passes whatever is wrong, so an empty catalogue fails."""
    with pytest.raises(AssertionError, match="the catalogue is empty"):
        assert_sound(_frame(), "test", now=_NOW)


def test_failures_beyond_the_limit_are_counted_not_listed() -> None:
    """A catalogue that breaks a rule everywhere fails with a short list, not a page of stations."""
    stations = _frame(*[_station(station_id=f"{index:05d}", name="Bad ") for index in range(5)])
    with pytest.raises(AssertionError, match="and 3 more"):
        assert_sound(stations, "test", now=_NOW, limit=2)


def test_every_exception_that_covers_a_violation_is_used() -> None:
    """Two exceptions for the same rule that overlap are both in use, so neither is reported as stale."""
    violations = check_catalogue(_frame(_station(name="Bad ")), "test", now=_NOW)
    broad = Accepted("name_padding", "the source pads every name")
    narrow = Accepted("name_padding", "the source pads this one", where=lambda row: row["station_id"] == "00044")
    left, stale = unaccepted(violations, [broad, narrow])
    assert left == []
    assert stale == []
