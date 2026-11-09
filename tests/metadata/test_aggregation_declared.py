# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that a provider declares the `aggregation` of a plain name only where its source states it (GH-3134).

The canonical table decides `aggregation` for every name that states a statistic (`tests/metadata/test_aggregation.py`).
A plain name (`temperature_air_2m`, `wind_speed`, `snow_depth`) states none: "a reading at one moment, or a source that
states no statistic". Only the provider can tell the two apart, and it does so row by row, in its metadata dict:
`"aggregation": "instant"`. The effective value of a row is the canonical one, else the declaration
(`ParameterModel.effective_aggregation`), and a row without either is not stated (`None`), never a guess.

What the tests hold:

- a declaration is only ever on a name the table leaves open: a provider cannot override a `_mean` (`_max`, ...);
- a declared `instant` has evidence, one of three kinds: the row's own source wording of a reading
  (`instantaneous`, `current value`, `at the time of observation`; the `_SPOT_VALUE` of
  `test_parameter_statistics.py`), a stated mean over at most 5 minutes (a reading by the convention of GH-2660), or an
  entry of `INSTANT_BY_REFERENCE_TIME` that names where the source says it (a sentence of `docs/data/time_reference.md`
  or of the row's own description) and is checked to be there;
- a plain name left `None` does not state, in its own source wording, a mean over 10 minutes or more or a maximum,
  except for the rows of `ALLOWED_UNDECLARED`, each with its reason.

The page and the descriptions are what a reader sees; this test only makes sure the declaration is backed by them.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.metadata.test_parameter_statistics import _MEAN_WINDOW, _MEAN_WORD, _SPOT_VALUE, _source_description
from tests.test_api import ALL_METADATA
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.metadata import ParameterModel

TIME_REFERENCE = Path(__file__).parents[2] / "docs" / "data" / "time_reference.md"

#: a mean over this many minutes or fewer is a reading at the stamp (GH-2660: FMI and KNMI 1-minute means, the NWS
#: 5-minute average); a longer one is a mean, which a plain name does not carry
_READING_WINDOW_MINUTES = 5
#: a maximum a source states: "the highest of the 60 instantaneous values", "maximum over the hour", "valor máximo de";
#: not "publishes the 10 minute maximum separately" nor "the largest value it reports (a cap)"
_STATES_A_MAXIMUM = re.compile(
    r"\b(?:maximum|highest|largest|peak)\s+(?:value\s+)?(?:of|in|within|over|during|per)\s+(?:the|each|a|an|all|\d)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InstantEvidence:
    """Where the source says a plain-named row is a reading, for the rows the row's own wording does not settle.

    `provider` is the name of the metadata (`DwdMosmixMetadata`), `datasets` and `originals` narrow the rows of the
    resolution to those the sentence covers (`None`: all of them). `source` says where `quote` is read: the page
    `docs/data/time_reference.md` (`"page"`, the row that says it) or the description of every row the entry covers
    (`"description"`, a reading at a stated moment: a time of day, a minute, midday). The test fails for a quote that is
    in neither, and for an entry no declared row uses.
    """

    provider: str
    resolution: str
    datasets: frozenset[str] | None
    originals: frozenset[str] | None
    source: str
    quote: str

    def covers(self, provider: str, resolution: str, dataset: str, original: str) -> bool:
        """Say whether the entry speaks for the row."""
        return (
            (self.provider, self.resolution) == (provider, resolution)
            and (self.datasets is None or dataset in self.datasets)
            and (self.originals is None or original in self.originals)
        )


def _entry(
    provider: str,
    resolution: str,
    source: str,
    quote: str,
    originals: str | None = None,
    datasets: str | None = None,
) -> InstantEvidence:
    """Build an entry, naming the datasets and the source's field names as space-separated words."""
    return InstantEvidence(
        provider=provider,
        resolution=resolution,
        datasets=frozenset(datasets.split()) if datasets else None,
        originals=frozenset(originals.split()) if originals else None,
        source=source,
        quote=quote,
    )


#: Rows declared `instant` that no wording of their own settles. Strict: a source that states nothing is not here. The
#: rows of the page that say `unverified`, or name no parameter (DWD 10-minute `rf_10`, `pp_10`, `td_10`, the subdaily
#: moisture, pressure, cloud and wind terms, RMI, the ECCC hourly rows), are left `None`.
INSTANT_BY_REFERENCE_TIME: tuple[InstantEvidence, ...] = (
    # forecasts: the value at the forecast point in time
    _entry(
        "DwdMosmixMetadata",
        "hourly",
        "page",
        "instant (forecast point in time: TTT, Td, T5cm, DD, FF, PPPP, N*, VV, ww ...)",
        originals="ttt td t5cm dd ff pppp n n05 nh nl nm nlm neff vv",
    ),
    _entry(
        "DwdDmoMetadata",
        "hourly",
        "page",
        "instant (ttt, td, t5cm, dd, ff, pppp, n, nh, nl, nm, neff, ww)",
        originals="ttt td t5cm dd ff pppp n nh nl nm neff",
    ),
    _entry(
        "DwdSwsmosMetadata",
        "hourly",
        "page",
        "instant (TL, TD, TS, RC at the forecast time)",
        originals="TL TD TS",
    ),
    # DWD's current weather reports and the road weather stations, at the report time
    _entry(
        "DwdPoiMetadata",
        "hourly",
        "page",
        "instant at the report time for temperature, dew point, humidity, pressure, cloud, visibility, snow depth,",
        originals=(
            "cloud_cover_total relative_humidity pressure_reduced_to_mean_sea_level total_snow_depth "
            "dry_bulb_temperature_at_2_meter_above_ground temperature_at_5_cm_above_ground "
            "dew_point_temperature_at_2_meter_above_ground horizontal_visibility"
        ),
    ),
    _entry(
        "DwdRoadMetadata",
        "15_minutes",
        "page",
        "instant (airTemperature, dewpointTemperature, relativeHumidity, horizontalVisibility, "
        "roadSurfaceTemperature/-Condition, waterFilmThickness, precipitationType/intensity)",
        originals=(
            "airTemperature dewpointTemperature relativeHumidity horizontalVisibility roadSurfaceTemperature "
            "waterFilmThickness intensityOfPrecipitation"
        ),
    ),
    # a reading at the stamp of the hour the page says so for
    _entry(
        "KnmiObservationMetadata",
        "hourly",
        "page",
        "T/TD/U/P 'past 1 minute' values at that end",
        originals="T TD U P",
    ),
    _entry(
        "EAHydrologyMetadata",
        "15_minutes",
        "page",
        "| hydrology | 15_minutes | all | unverified | instant | partly |",
    ),
    _entry(
        "MetOfficeObservationMetadata",
        "hourly",
        "page",
        "| observation | hourly | weather | UTC (GMT) | instant (ob_time) | yes |",
        datasets="weather",
    ),
    _entry(
        "MetOfficeObservationMetadata",
        "hourly",
        "page",
        "| observation | hourly | soil_temperature | UTC (GMT) | instant (ob_time; daily readings usually at 0900Z, "
        "hourly ones usually at 10 cm) | yes |",
        datasets="soil_temperature",
    ),
    _entry(
        "MeteoFranceSynopMetadata",
        "subdaily",
        "page",
        "instant for t/td/u/vv/n/pres/pmer",
        originals="t td u vv n pres pmer",
    ),
    _entry(
        "MeteoFranceObservationMetadata",
        "daily",
        "page",
        "NEIGETOT06 instant at 06 h",
        originals="NEIGETOT06",
        datasets="others",
    ),
    # a reading at a moment the row's own description states
    _entry(
        "EcccObservationMetadata",
        "monthly",
        "description",
        "the monthly value displayed is for the final day of the month",
        originals="snow_on_ground_last_day",
    ),
    _entry(
        "MeteoswissObservationMetadata",
        "daily",
        "description",
        "morning measurement at 6 UTC",
        originals="htoautd0",
    ),
    _entry("ChmiObservationMetadata", "daily", "description", "a reading at 06:00 UTC", originals="SCE"),
    _entry(
        "DmiObservationMetadata",
        "daily",
        "description",
        "measured by hand once a day at 07:00 UTC",
        originals="snow_depth",
    ),
    _entry(
        "DmiObservationMetadata",
        "hourly",
        "description",
        "at minute 0 of the hour (UTC)",
        originals="mean_cloud_cover",
    ),
    _entry(
        "DwdDerivedMetadata",
        "daily",
        "description",
        "at midday",
        originals="zfumi ztkmi ztumi",
        datasets="soil",
    ),
    _entry(
        "DwdObservationMetadata",
        "hourly",
        "description",
        "at mid of interval",
        originals="zenit",
        datasets="solar",
    ),
)

#: Rows left `None` whose own wording nevertheless reads as a mean or a maximum to the rule below, each with the
#: reason it is not a statement of the statistic a plain name would carry. Keyed by `(metadata, resolution, field)`.
ALLOWED_UNDECLARED: dict[tuple[str, str, str], str] = {
    ("DwdRoadMetadata", "15_minutes", "windSpeed"): (
        "a 10-minute mean, a 15-minute mean or a period of 0 by station group, under one name (GH-2838)"
    ),
    ("DwdRoadMetadata", "15_minutes", "windDirection"): (
        "a 10-minute mean, a 15-minute mean or a period of 0 by station group, under one name (GH-2838)"
    ),
    ("EcccObservationMetadata", "hourly", "wind_speed"): (
        "the average of a one-, two- or ten-minute period by station, under one name (GH-2837)"
    ),
    ("DwdMosmixMetadata", "hourly", "rrad1"): (
        "the 'mean difference' is the description's check against Rad1h, not a statistic of the value (a share of the "
        "extraterrestrial radiation, which the source does not call a mean)"
    ),
    ("NoaaGhcnMetadata", "hourly", "altimeter"): (
        "'average conditions' describe the standard atmosphere of the reduction, not the value"
    ),
}


def _rows() -> Iterator[tuple[str, str, str, ParameterModel, str]]:
    """Yield `(metadata, resolution, dataset, parameter, evidence)` for every row; `evidence` is the source's wording.

    That is the source's own description (`_source_description` leaves out one written from the canonical name) and the
    field name the source gives it.
    """
    for metadata in ALL_METADATA:
        for resolution in metadata:
            for dataset in resolution:
                for parameter in dataset.parameters:
                    description = _source_description(metadata.name, resolution.name, dataset.name, parameter)
                    evidence = f"{description} {parameter.name_original}".strip()
                    yield metadata.name, resolution.name, dataset.name, parameter, evidence


def _site(metadata: str, resolution: str, dataset: str, parameter: ParameterModel) -> str:
    return f"{metadata} {resolution}/{dataset}/{parameter.name} [{parameter.name_original}]"


# "the source states no mean or interval" (Hub'Eau) says the opposite of a mean
_NO_MEAN = re.compile(r"\bno (?:mean|average)\b", re.IGNORECASE)


def _mean_window_minutes(evidence: str) -> int | None:
    """Return the shortest mean window in minutes `evidence` states ("1 Min Mean", "Mean over 5 minutes"), if any."""
    windows = [int(g) for match in _MEAN_WINDOW.finditer(evidence) for g in match.groups() if g]
    return min(windows) if windows else None


def _states_a_reading(evidence: str) -> bool:
    """Say whether the wording states a reading at one moment: a spot wording or a mean of at most 5 minutes."""
    window = _mean_window_minutes(evidence)
    return bool(_SPOT_VALUE.search(evidence)) or (window is not None and window <= _READING_WINDOW_MINUTES)


def _states_a_mean_or_a_maximum(evidence: str) -> bool:
    """Say whether the wording states a mean over at least 10 minutes (or of the interval) or a maximum."""
    evidence = _NO_MEAN.sub("", evidence)
    window = _mean_window_minutes(evidence)
    mean = window > _READING_WINDOW_MINUTES if window is not None else bool(_MEAN_WORD.search(evidence))
    return mean or bool(_STATES_A_MAXIMUM.search(evidence))


def _page() -> str:
    """Return the page without the Markdown escapes of its table cells, as a quote is written."""
    return TIME_REFERENCE.read_text(encoding="utf-8").replace("\\", "")


def _declared() -> list[tuple[str, str, str, ParameterModel, str]]:
    return [row for row in _rows() if row[3].aggregation is not None]


def test_a_declaration_is_only_on_a_name_the_table_leaves_open() -> None:
    """A provider cannot override what the name states: `_mean` is a mean, whatever a row says."""
    wrong = [
        f"{_site(*row[:4])}: declares {row[3].aggregation!r}, the table decides {PARAMETERS[row[3].name].aggregation!r}"
        for row in _declared()
        if PARAMETERS[row[3].name].aggregation is not None
    ]
    assert not wrong, "\n".join(wrong)


def test_only_instant_is_declared() -> None:
    """Every declaration today is `instant`; another statistic on a plain name needs its own evidence rule first."""
    declared = {row[3].aggregation for row in _declared()}
    assert declared == {"instant"}, (
        f"declared {declared}: a declaration of another statistic needs an evidence rule in this module, since "
        "`instant` is the only one whose evidence is checked here"
    )


def test_the_effective_aggregation_is_the_name_s_or_the_declaration() -> None:
    """The canonical value wins where the table has one; a plain name takes the row's declaration, else None."""
    seen = set()
    for *_, parameter, _evidence in _rows():
        canonical = PARAMETERS[parameter.name].aggregation
        expected = canonical or parameter.aggregation
        assert parameter.effective_aggregation == expected
        seen.add((canonical is None, parameter.aggregation is None))
    # a decided name, a declared plain one and an undeclared plain one all occur
    assert seen == {(False, True), (True, False), (True, True)}


def _evidence_of(row: tuple[str, str, str, ParameterModel, str]) -> str | None:
    """Return how the declared `instant` of a row is backed: `text`, `entry`, or None."""
    metadata, resolution, dataset, parameter, evidence = row
    # a wording that states a reading and, in the same row, a mean or a maximum ("the highest of the 60 instantaneous
    # values", ECCC's wind "average of the one-, two- or ten-minute period ending at the time of observation") is no
    # evidence of a reading
    if _states_a_reading(evidence) and not _states_a_mean_or_a_maximum(evidence):
        return "text"
    if any(entry.covers(metadata, resolution, dataset, parameter.name_original) for entry in INSTANT_BY_REFERENCE_TIME):
        return "entry"
    return None


def test_a_declared_instant_has_evidence() -> None:
    """A declared `instant` rests on the row's own wording, a short mean or an entry that says where it is said."""
    unbacked = [_site(*row[:4]) for row in _declared() if _evidence_of(row) is None]
    assert not unbacked, (
        "declared `instant` without evidence (a spot wording of the row, a mean over at most "
        f"{_READING_WINDOW_MINUTES} minutes, or an entry of INSTANT_BY_REFERENCE_TIME):\n" + "\n".join(unbacked)
    )


def test_every_reference_entry_is_quoted_and_used() -> None:
    """An entry quotes the page or the descriptions of the rows it covers, and a declared row needs it."""
    page = _page()
    declared = _declared()
    problems = []
    for entry in INSTANT_BY_REFERENCE_TIME:
        label = f"{entry.provider} {entry.resolution} {sorted(entry.datasets or [])} {sorted(entry.originals or [])}"
        assert entry.source in {"page", "description"}, label
        covered = [row for row in _rows() if entry.covers(row[0], row[1], row[2], row[3].name_original)]
        used = [row for row in declared if entry.covers(row[0], row[1], row[2], row[3].name_original)]
        if not used:
            problems.append(f"{label}: no declared row uses it")
        if entry.source == "page" and entry.quote not in page:
            problems.append(f"{label}: not in docs/data/time_reference.md: {entry.quote!r}")
        if entry.source == "description":
            problems.extend(
                f"{_site(*row[:4])}: its description does not say {entry.quote!r}"
                for row in covered
                if row[3].aggregation and entry.quote not in (row[3].description or "")
            )
        # an entry that names fields speaks for each of them: a name that matches no row is a typo
        for original in entry.originals or ():
            if not any(row[3].name_original == original for row in covered):
                problems.append(f"{label}: no row has the field {original!r}")
    assert not problems, "\n".join(problems)


def test_a_plain_name_left_null_does_not_state_a_mean_or_a_maximum() -> None:
    """A row without a statistic is one whose source states none: a stated mean (10 minutes or more) or maximum is read.

    A source that says "mean" or "maximum" of a plain name is a naming defect for the table (a `_mean` name, as the
    renames of GH-3134 did for DWD POI and NWS), not a reason for the row to say nothing. The few rows whose wording
    only looks like it are in `ALLOWED_UNDECLARED` with the reason.
    """
    used = set()
    wrong = []
    for metadata, resolution, dataset, parameter, evidence in _rows():
        if parameter.effective_aggregation is not None or not _states_a_mean_or_a_maximum(evidence):
            continue
        key = (metadata, resolution, parameter.name_original)
        if key in ALLOWED_UNDECLARED:
            used.add(key)
        else:
            wrong.append(f"{_site(metadata, resolution, dataset, parameter)}: {evidence!r}")
    assert not wrong, "the source states a mean or a maximum, name it so or list the reason:\n" + "\n".join(wrong)
    assert used == set(ALLOWED_UNDECLARED), f"allowances nothing needs: {set(ALLOWED_UNDECLARED) - used}"


@pytest.mark.parametrize(
    ("evidence", "reading", "long_mean_or_maximum"),
    [
        ("Air temperature. Instantaneous value, once per hour.", True, False),
        ("Temperature at the time of observation", True, False),
        ("Air temperature. Mean over 1 minute.", True, False),
        ("Air Temperature 1 Min Mean", True, False),
        ("the mean value of the 1 minute interval ending UTC 10:50", True, False),
        ("5-minute average air temperature", True, False),
        ("Wind speed. Mean over 10 minutes.", False, True),
        ("Air temperature 2 m above ground; hourly mean", False, True),
        ("the highest of the 60 instantaneous values", True, True),
        ("The source's largest value (15 statute miles) can stand for a larger visibility.", False, False),
        ("it publishes the 10 minute maximum and minimum separately, as TMA and TMI", False, False),
        ("Each value is dated by the instant it occurred; the source states no mean or interval.", True, False),
        ("Air temperature 2 m above ground.", False, False),
    ],
)
def test_the_wordings_are_read_as_they_are_meant(*, evidence: str, reading: bool, long_mean_or_maximum: bool) -> None:
    """Pin the two readers on the wordings of the sources, so that a change to a pattern is read here."""
    assert _states_a_reading(evidence) is reading
    assert _states_a_mean_or_a_maximum(evidence) is long_mean_or_maximum
