# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The station catalogue rules fire on the defect each names and stay quiet on a sound catalogue (GH-2616)."""

import datetime as dt
from typing import Any

import polars as pl
import pytest

from tests.provider.station_catalogue import (
    COUNTRY_BBOX,
    EXTENT_LISTED,
    FROST_ANTARCTIC,
    FROST_FOREIGN_WMO,
    RULES,
    Accepted,
    Bbox,
    assert_sound,
    check_catalogue,
    check_extent,
    has_encoding_damage,
    unaccepted,
)
from tests.provider.station_catalogue_stubs import question_mark_in_the_name
from wetterdienst import Wetterdienst

_NOW = dt.datetime(2026, 10, 10, tzinfo=dt.UTC)
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
        "start_timestamp": dt.datetime(1971, 3, 1, tzinfo=dt.UTC),
        "end_timestamp": dt.datetime(2026, 10, 9, tzinfo=dt.UTC),
        "latitude": 52.9336,
        "longitude": 8.2370,
        "elevation": 44.0,
        "name": "Großenkneten",
        "region": "Niedersachsen",
    } | fields


def _frame(*stations: dict[str, Any]) -> pl.DataFrame:
    return pl.DataFrame(list(stations), schema=_SCHEMA, orient="row")


def _rules_of(*stations: dict[str, Any], bbox: Bbox | tuple[Bbox, ...] | None = _GERMANY) -> set[str]:
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
                start_timestamp=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                end_timestamp=dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
            )
        ],
    ),
    ("date_in_the_future", [_station(end_timestamp=dt.datetime(2100, 12, 31, tzinfo=dt.UTC))]),
    (
        "date_in_the_future",
        [_station(start_timestamp=dt.datetime(2027, 1, 1, tzinfo=dt.UTC), end_timestamp=None)],
    ),
    ("date_implausible", [_station(start_timestamp=dt.datetime(1066, 1, 1, tzinfo=dt.UTC))]),
    ("date_implausible", [_station(start_timestamp=None, end_timestamp=dt.datetime(1, 1, 1, tzinfo=dt.UTC))]),
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


def test_a_country_of_several_boxes_holds_a_station_to_any_of_them() -> None:
    """France with its overseas departments is several boxes (GH-3468): in one is inside, the sea between is not."""
    france = COUNTRY_BBOX["eaufrance/hubeau"]
    assert len(france) > 1

    def rules(latitude: float, longitude: float) -> set[str]:
        return _rules_of(_station(latitude=latitude, longitude=longitude), bbox=france)

    assert rules(48.85, 2.35) == set()  # Paris
    assert rules(51.09, 2.54) == set()  # Bray-Dunes, the northernmost point of France (GH-3481)
    assert rules(51.2, 2.54) == {"coordinates_outside_country"}  # beyond the Channel coast, in Belgium
    assert rules(16.19, -61.66) == set()  # Guadeloupe
    assert rules(-12.80, 45.21) == set()  # Mayotte
    assert rules(35.11, 0.84) == {"coordinates_outside_country"}  # the Blavet as the referential lists it
    assert rules(4.10, 49.99) == {"coordinates_outside_country"}  # Anor, swapped
    assert rules(0.0, -30.0) == {"coordinates_outside_country"}
    # a swapped position is told as one, by any of the boxes
    (violation,) = check_catalogue(_frame(_station(latitude=4.10, longitude=49.99)), "test", bbox=france, now=_NOW)
    assert "swapped" in violation.detail
    # and one at Bray-Dunes, where the box once stopped at 51.0, is told as swapped too (GH-3481)
    (violation,) = check_catalogue(_frame(_station(latitude=2.54, longitude=51.09)), "test", bbox=france, now=_NOW)
    assert "swapped" in violation.detail


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
    with pytest.raises(AssertionError, match=r"name_padding: \.\.\. and 3 more"):
        assert_sound(stations, "test", now=_NOW, limit=2)


def test_every_exception_that_covers_a_violation_is_used() -> None:
    """Two exceptions for the same rule that overlap are both in use, so neither is reported as stale."""
    violations = check_catalogue(_frame(_station(name="Bad ")), "test", now=_NOW)
    broad = Accepted("name_padding", "the source pads every name")
    narrow = Accepted("name_padding", "the source pads this one", where=lambda row: row["station_id"] == "00044")
    left, stale = unaccepted(violations, [broad, narrow])
    assert left == []
    assert stale == []


def test_a_question_mark_excuses_no_other_damage() -> None:
    """A name with a question mark and mojibake is damaged beyond the question mark."""
    assert has_encoding_damage("NAR?JAN-MAR")
    assert not has_encoding_damage("NAR?JAN-MAR", question_marks=False)
    assert has_encoding_damage("DzierÅ¼kowice?", question_marks=False)
    assert not has_encoding_damage("SÃO PAULO?", question_marks=False)


def test_the_question_mark_exception_covers_a_name_with_that_damage_only() -> None:
    """The predicate of the exceptions covers NAR?JAN-MAR and not a name with mojibake as well."""
    assert question_mark_in_the_name({"name": "NAR?JAN-MAR"})
    assert not question_mark_in_the_name({"name": "DzierÅ¼kowice?"})
    assert not question_mark_in_the_name({"name": "Großenkneten"})


def test_a_rule_broken_everywhere_does_not_hide_the_others() -> None:
    """The limit is for each rule, so a second rule's violations are listed even after thousands of the first."""
    stations = _frame(
        *[_station(station_id=f"{index:05d}", name="Bad ") for index in range(5)],
        _station(station_id="x", elevation=9999.0),
    )
    with pytest.raises(AssertionError, match="elevation_sentinel: station 'x'"):
        assert_sound(stations, "test", now=_NOW, limit=2)


def test_a_station_outside_the_extent_is_accepted_for_its_id_only() -> None:
    """An exception of `coordinates_outside_extent` covers the station it names, and nothing else outside the box."""
    extent = Wetterdienst.resolve("metno", "frost").metadata.extent
    stations = pl.DataFrame(
        {
            "station_id": ["SN18700", "SN1039300", "SN2"],
            "latitude": [59.94, 52.209482, 40.0],
            "longitude": [10.72, 14.120075, 14.0],
        }
    )
    accepted = (
        Accepted("coordinates_outside_extent", "listed in Germany", where=lambda row: row["station_id"] == "SN1039300"),
    )

    assert not check_extent(stations.head(1), "metno/frost", extent)
    assert "SN1039300" in "\n".join(check_extent(stations.head(2), "metno/frost", extent))
    problems = check_extent(stations, "metno/frost", extent, accepted=accepted)
    assert len(problems) == 1
    assert "SN2" in problems[0]
    assert not check_extent(stations.head(2), "metno/frost", extent, accepted=accepted)


def test_the_foreign_wmo_stations_of_frost_are_accepted_by_their_id_and_a_norwegian_one_is_not() -> None:
    """The ids that are a WMO number x 100 are accepted outside the box of Norway, and a Norwegian id is not.

    The Norwegian ids outside the box include one of five digits that ends in 00 (SN99900), which a looser pattern
    (a pattern that takes any number of digits before the 00) would take for a foreign one.
    """
    extent = Wetterdienst.resolve("metno", "frost").metadata.extent
    foreign = ["SN743400", "SN623500", "SN1039300", "SN1240000"]
    norwegian_outside = ["SN99900", "SN99999", "SN123456"]
    stations = pl.DataFrame(
        {
            # SN18700 is Oslo, in the box
            "station_id": ["SN18700", *foreign, *norwegian_outside],
            "latitude": [59.94, 45.861, 52.927, 52.209, 51.93, 40.0, 40.0, 40.0],
            "longitude": [10.72, 1.175, 4.781, 14.12, 15.52, 14.0, 14.0, 14.0],
        }
    )

    problems = check_extent(stations, "metno/frost", extent, accepted=(FROST_FOREIGN_WMO,))

    assert len(problems) == len(norwegian_outside)
    for station_id, problem in zip(norwegian_outside, problems, strict=True):
        assert station_id in problem


def test_the_antarctic_stations_of_frost_are_accepted_south_of_60_and_not_north_of_it() -> None:
    """A station south of 60 S is accepted outside the box of Norway, one just north of it is still a failure."""
    extent = Wetterdienst.resolve("metno", "frost").metadata.extent
    stations = pl.DataFrame(
        {
            "station_id": ["SN18700", "SN99990", "SN92100", "SN1", "SN2"],
            "latitude": [59.94, -72.012, -71.9563, -59.9, 0.0],
            "longitude": [10.72, 2.5408, 2.4668, 2.5, 2.5],
        }
    )

    problems = check_extent(stations, "metno/frost", extent, accepted=(FROST_ANTARCTIC,))

    assert len(problems) == 2
    assert "SN1 " in problems[0]
    assert "SN2 " in problems[1]


def test_a_station_outside_the_extent_is_named_once_and_all_of_them_are_named() -> None:
    """The datasets of a network list a station each, which is one station, and the failure names every station."""
    extent = Wetterdienst.resolve("metno", "frost").metadata.extent
    ids = [f"SN{number}" for number in range(10, 30)]
    one_dataset = pl.DataFrame({"station_id": ids, "latitude": [0.0] * 20, "longitude": [0.0] * 20})
    stations = pl.concat([one_dataset] * 6)

    problems = check_extent(stations, "metno/frost", extent)

    assert len(problems) == 20
    assert [station_id in problem for station_id, problem in zip(ids, problems, strict=True)] == [True] * 20
    assert not any("more stations" in problem for problem in problems)


def test_a_failure_names_no_more_than_the_listed_stations_and_counts_the_rest() -> None:
    """A network that is wrong as a whole does not fill the log: the first stations are named and the rest counted."""
    extent = Wetterdienst.resolve("metno", "frost").metadata.extent
    count = EXTENT_LISTED + 7
    stations = pl.DataFrame(
        {
            "station_id": [f"SN{number}" for number in range(count)],
            "latitude": [0.0] * count,
            "longitude": [0.0] * count,
        }
    )

    problems = check_extent(stations, "metno/frost", extent)

    assert len(problems) == EXTENT_LISTED + 1
    assert problems[-1] == "metno/frost: ... and 7 more stations outside the extent"


def test_an_accepted_station_does_not_hold_the_box_open() -> None:
    """The box is compared with the stations that are in it, not with one the source lists elsewhere."""
    extent = Wetterdienst.resolve("metno", "frost").metadata.extent
    stations = pl.DataFrame(
        {
            "station_id": ["SN90450", "SN99910", "SN1039300"],
            "latitude": [69.65, 70.9, 52.209482],
            "longitude": [18.94, 29.0, 14.120075],
        }
    )
    accepted = (Accepted("coordinates_outside_extent", "listed in Germany"),)

    with_it = check_extent(stations, "metno/frost", extent, whole=True)
    without_it = check_extent(stations, "metno/frost", extent, whole=True, accepted=accepted)

    assert any("outside the extent" in problem for problem in with_it)
    assert all("outside the extent" not in problem for problem in without_it)
    assert any("degrees south" in problem for problem in without_it)


def test_a_catalogue_with_no_position_at_all_is_reported_by_the_extent_check() -> None:
    """With no position there is nothing to compare, and the check says so instead of passing."""
    stations = pl.DataFrame(
        {"station_id": ["01067"], "latitude": [None], "longitude": [None]},
        schema={"station_id": pl.String, "latitude": pl.Float64, "longitude": pl.Float64},
    )
    extent = Wetterdienst.resolve("dwd", "derived").metadata.extent

    assert check_extent(stations, "dwd/derived", extent) == [
        "dwd/derived: the catalogue has no station with a position, so no extent was checked"
    ]
