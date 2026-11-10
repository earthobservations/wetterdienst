# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that a provider declares the `aggregation` of a plain name only where its source states it (GH-3134).

The canonical table decides `aggregation` for every name that states a statistic (`tests/metadata/test_aggregation.py`).
A plain name (`temperature_air_2m`, `wind_speed`, `snow_depth`) states none: "a reading at one moment, or a source that
states no statistic". Only the provider can tell the two apart, and it does so row by row, in its metadata dict:
`"aggregation": "instant"`. The effective value of a row is the canonical one, else the declaration
(`ParameterModel.effective_aggregation`), and a row without either is not stated (`None`), never a guess.

`instant` is a single reading, not a statistic over a window; when it was taken is said by the `timestamp_position` of
the dataset and by the description of the row. A mean over at most 5 minutes counts as a reading (GH-2660).

What the tests hold:

- a declaration is only ever on a name the table leaves open: a provider cannot override a `_mean` (`_max`, ...);
- a declared `instant` has evidence, one of three kinds: the row's own source wording of a reading
  (`instantaneous`, `current value`, `at the time of observation`; not the bare noun "instant", which wetterdienst's own
  paraphrases use), a stated mean over at most 5 minutes (the longest window the wording states), or an entry of
  `INSTANT_BY_REFERENCE_TIME` that says where the source states it (or, for the DWD hourly readings, the measured
  verdict the maintainer accepted) and is checked to be there;
- a `docs/data/time_reference.md` cell that only says where the timestamp sits (the forecast step, `ob_time`, the report
  time) is no evidence of the statistic: an entry quotes a sentence that speaks of the parameter's own statistic (a
  reading, an instantaneous value, a value at a stated hour), in the section and the row it names;
- a plain name left `None` does not state, in its own source wording, a mean over 10 minutes or more or a maximum,
  except for the rows of `ALLOWED_UNDECLARED`, each with its reason.

The page and the descriptions are what a reader sees; this test only makes sure the declaration is backed by them.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.metadata.test_parameter_statistics import _MEAN_WINDOW, _source_description
from tests.test_api import ALL_METADATA
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.metadata import ParameterModel

TIME_REFERENCE = Path(__file__).parents[2] / "docs" / "data" / "time_reference.md"

#: a mean over this many minutes or fewer is a reading at the stamp (GH-2660: FMI and KNMI 1-minute means, the NWS
#: 5-minute average); a longer one is a mean, which a plain name does not carry
_READING_WINDOW_MINUTES = 5
#: the wordings a source uses for a reading: DWD urban "momentaner", MeteoSwiss "current value", SMHI "Instantaneous
#: value", MET Norway "present value", AEMET "at the time given by 'fint'", NOAA GHCN "at the time of observation". Not
#: the bare noun "instant" (Hub'Eau's "dated by the instant it occurred" is wetterdienst's paraphrase of "date
#: d'occurence de la donnee": an entry quotes the source instead)
_READING_WORDING = re.compile(
    r"\b(?:instantaneous|instant value|current value|present value|at the time (?:of|given by))\b", re.IGNORECASE
)
#: a window the wording states for a mean: "1 Min Mean", "Mean over 5 minutes", "averaged to 10 minutes"
_AVERAGED_TO = re.compile(r"\baveraged (?:over|to|into) (\d+)[ -]?min(?:ute)?s?\b", re.IGNORECASE)
# "the source states no mean or interval" (Hub'Eau) says the opposite of a mean
_NO_MEAN = re.compile(r"\bno (?:mean|average)\b", re.IGNORECASE)
#: a daily or coarser row: a plain "mean sea level pressure" there reads as the mean of the day (KNMI `PG`)
_COARSE_RESOLUTIONS = {"daily", "monthly", "annual"}
#: "mean sea level" is a datum, not a statistic, unless a period says what is averaged ("daily mean sea level pressure")
_MEAN_SEA_LEVEL = re.compile(
    r"(?<!daily )(?<!hourly )(?<!monthly )(?<!annual )(?<![a-z])mean[ _]sea(?![a-z])", re.IGNORECASE
)
#: a mean or an average, in English and in the languages of the sources (Mittel, moyenne, media, promedio, srednia)
_MEAN_WORDS = re.compile(
    r"(?<![a-z])(?:mean|average|averaged|avg|mittel\w*|moyenn\w*|media|m[eé]dia|medio|promedio|[sś]redni\w*)(?![a-z])",
    re.IGNORECASE,
)
#: a maximum a source states: "the highest of the 60 instantaneous values", "maximum over the hour", "valor máximo de",
#: "maximum gust"; not "publishes the 10 minute maximum separately" nor "the largest value it reports (a cap)"
_STATES_A_MAXIMUM = re.compile(
    r"\b(?:maximum|highest|largest|peak)\s+(?:value\s+)?(?:of|in|within|over|during|per)\s+(?:the|each|a|an|all|\d)"
    r"|\bm[aá]xim[oa]s?\b|\b(?:maximum|highest|peak) gusts?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InstantEvidence:
    """Where a plain-named row is a reading, for the rows the row's own wording does not settle.

    The source says so, or it is a measured verdict the maintainer accepted (the DWD hourly readings, GH-3134).

    `provider` is the name of the metadata (`DwdRoadMetadata`), `resolutions`, `datasets` and `originals` (all
    required, space-separated in `_entry`) narrow the rows to those the sentence covers. `source` says where `quote` is
    read: the page `docs/data/time_reference.md` (`"page"`: the table row of `network` and the resolution, or, with
    `note`, the note of `network/resolution`, in the section `section` of the provider) or the description of every
    row the entry covers (`"description"`, a reading at a stated moment: a time of day, a minute, midday). The test
    fails for a quote that is not where it is said to be, and for an entry no declared row uses.
    """

    provider: str
    resolutions: frozenset[str]
    datasets: frozenset[str] | None
    originals: frozenset[str]
    source: str
    quote: str
    section: str = ""
    network: str = ""
    note: bool = False

    def covers(self, provider: str, resolution: str, dataset: str, original: str) -> bool:
        """Say whether the entry speaks for the row."""
        return (
            provider == self.provider
            and resolution in self.resolutions
            and (self.datasets is None or dataset in self.datasets)
            and original in self.originals
        )


def _entry(
    provider: str,
    resolutions: str,
    originals: str,
    source: str,
    quote: str,
    *,
    datasets: str | None = None,
    section: str = "",
    network: str = "",
    note: bool = False,
) -> InstantEvidence:
    """Build an entry, naming resolutions, datasets and the source's field names as space-separated words."""
    return InstantEvidence(
        provider=provider,
        resolutions=frozenset(resolutions.split()),
        datasets=frozenset(datasets.split()) if datasets else None,
        originals=frozenset(originals.split()),
        source=source,
        quote=quote,
        section=section,
        network=network,
        note=note,
    )


#: Rows declared `instant` that no wording of their own settles. Strict: a source that states nothing is not here. A
#: page cell that only says where the stamp sits (MOSMIX and DMO "instant (forecast point in time ...)", SWSMOS "at the
#: forecast time", POI "at the report time", Met Office "instant (ob_time)", Météo-France SYNOP) is not evidence of the
#: statistic and has no entry; nor do the rows the page leaves `unverified` or does not name (DWD 10-minute `rf_10`,
#: `pp_10`, `td_10`, the subdaily terms, RMI, the ECCC hourly rows, Météo-France hourly `others`, LHMT, MET Norway).
INSTANT_BY_REFERENCE_TIME: tuple[InstantEvidence, ...] = (
    # DWD says `instant` for the two temperatures of the 10-minute dataset and does not qualify the others
    _entry(
        "DwdObservationMetadata",
        "10_minutes",
        "tt_10 tm5_10",
        "page",
        "instant: TT_10, TM5_10",
        datasets="temperature_air",
        section="dwd",
        network="observation",
    ),
    # the road weather stations: the BUFR descriptors of these four rows carry "no time period or statistic
    # attached"; the page's instant cell of the road row names the other fields too but only places the stamp
    _entry(
        "DwdRoadMetadata",
        "15_minutes",
        "airTemperature dewpointTemperature relativeHumidity roadSurfaceTemperature",
        "description",
        "no time period or statistic attached",
    ),
    # KNMI's hourly values are 'past 1 minute' values (a mean over at most 5 minutes)
    _entry(
        "KnmiObservationMetadata",
        "hourly",
        "T TD U P",
        "page",
        "T/TD/U/P 'past 1 minute' values at that end",
        section="knmi",
        network="observation",
    ),
    # the Environment Agency's reference table names the series "instantaneous"
    _entry(
        "EAHydrologyMetadata",
        "15_minutes",
        "flow-i-900",
        "page",
        "Flow 15min instantaneous m3/s",
        section="ea",
        network="hydrology",
        note=True,
    ),
    _entry(
        "EAHydrologyMetadata",
        "15_minutes",
        "level-i-900",
        "page",
        "Level 15min instantaneous m",
        section="ea",
        network="hydrology",
        note=True,
    ),
    _entry(
        "MeteoFranceObservationMetadata",
        "daily",
        "NEIGETOT06",
        "page",
        "instant: NEIGETOT06 at 06 h",
        datasets="others",
        section="meteofrance",
        network="observation",
    ),
    # a reading at a moment the row's own description states
    _entry(
        "EcccObservationMetadata",
        "monthly",
        "snow_on_ground_last_day",
        "description",
        "the monthly value displayed is for the final day of the month",
    ),
    _entry("MeteoswissObservationMetadata", "daily", "htoautd0", "description", "morning measurement at 6 UTC"),
    _entry("ChmiObservationMetadata", "daily", "SCE", "description", "a reading at 06:00 UTC"),
    _entry("DmiObservationMetadata", "daily", "snow_depth", "description", "measured by hand once a day at 07:00 UTC"),
    _entry("DmiObservationMetadata", "hourly", "mean_cloud_cover", "description", "at minute 0 of the hour (UTC)"),
    _entry("DwdDerivedMetadata", "daily", "zfumi ztkmi ztumi", "description", "at midday", datasets="soil"),
    _entry("DwdObservationMetadata", "hourly", "zenit", "description", "at mid of interval", datasets="solar"),
    # DWD's urban hourly sheets follow the SYNOP convention: the value of 10 minutes before the hour (the temperatures
    # of the same sheets say it as the mean of the 1 minute interval ending then)
    _entry(
        "DwdObservationMetadata",
        "hourly",
        "luftdruck_stationshoehe",
        "description",
        "the hour x corresponds to the measurement from 10 min before",
        datasets="urban_pressure",
    ),
    # the hourly air temperature, dew point, humidity and pressure of the moisture, dew point and pressure datasets
    # are readings of 10 to 30 min before the stamp (measured against the 10 minute series and NOAA ISD, GH-3134). The
    # basis is the maintainer's decision of 2026-11-10 (item 2, on #3134): a reading taken before the stamp is `end`
    # with aggregation `instant`. `p` (the sea level pressure) is covered as a reduction of readings of the same row,
    # the station pressure and the air temperature
    _entry(
        "DwdObservationMetadata",
        "hourly",
        "tt td tt_std td_std rf_std p_std p0 p",
        "page",
        "The stamp's value is a reading",
        datasets="dew_point moisture pressure",
        section="dwd",
        network="observation",
        note=True,
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


def _mean_window_minutes(evidence: str) -> int | None:
    """Return the longest mean window in minutes `evidence` states, if any.

    "1-minute mean, averaged to 10 minutes" is a 10-minute mean, so the longest window counts.
    """
    windows = [int(g) for match in _MEAN_WINDOW.finditer(evidence) for g in match.groups() if g]
    windows += [int(match.group(1)) for match in _AVERAGED_TO.finditer(evidence)]
    return max(windows) if windows else None


def _states_a_reading(evidence: str) -> bool:
    """Say whether the wording states a reading at one moment: a spot wording or a mean of at most 5 minutes."""
    window = _mean_window_minutes(evidence)
    return bool(_READING_WORDING.search(evidence)) or (window is not None and window <= _READING_WINDOW_MINUTES)


def _states_a_mean_or_a_maximum(evidence: str, resolution: str = "hourly") -> bool:
    """Say whether the wording states a mean over at least 10 minutes (or of the interval) or a maximum."""
    evidence = _NO_MEAN.sub("", evidence)
    if resolution not in _COARSE_RESOLUTIONS:
        evidence = _MEAN_SEA_LEVEL.sub("", evidence)
    window = _mean_window_minutes(evidence)
    mean = window > _READING_WINDOW_MINUTES if window is not None else bool(_MEAN_WORDS.search(evidence))
    return mean or bool(_STATES_A_MAXIMUM.search(evidence))


def _page_sections() -> dict[str, list[str]]:
    """Return the lines of each `## section` of the page, without the Markdown escapes of its table cells."""
    sections: dict[str, list[str]] = {}
    current = ""
    for line in TIME_REFERENCE.read_text(encoding="utf-8").replace("\\", "").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    return sections


_TABLE_CELLS = 6  # network, resolution, datasets, source time zone, reference time, verified
_NOTE_LABEL = re.compile(r"^- \*\*([^/*]+)/([^ *(]+)(?: \(([^)]*)\))?\*\*")


def _page_says(entry: InstantEvidence, resolution: str, dataset: str) -> bool:
    """Say whether the page states `entry.quote` where the entry names: the reference time of the row, or a note.

    A table row is the row of `network` and `resolution` that names the dataset, and the quote must be in its
    `reference time` cell (the fifth), not in its notes of the time zone. A note is the one of `network/resolution`,
    and of the dataset where the note names datasets.
    """
    lines = _page_sections().get(entry.section, [])
    for line in lines:
        if entry.note:
            label = _NOTE_LABEL.match(line)
            if not label or (label.group(1), label.group(2)) != (entry.network, resolution):
                continue
            named = label.group(3)
            if (named is None or dataset in {name.strip() for name in named.split(",")}) and entry.quote in line:
                return True
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) < _TABLE_CELLS or (cells[0], cells[1]) != (entry.network, resolution):
            continue
        if entry.quote in cells[4] and (cells[2] == "all" or dataset in {name.strip() for name in cells[2].split(",")}):
            return True
    return False


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


def _parameter(metadata: str, resolution: str, dataset: str, original: str) -> ParameterModel:
    """Return the parameter of the row the source calls `original`."""
    (parameter,) = (
        row[3] for row in _rows() if row[:3] == (metadata, resolution, dataset) and row[3].name_original == original
    )
    return parameter


def test_the_effective_aggregation_of_three_kinds_of_row() -> None:
    """A name the table decides, a plain row a provider declares, and a plain row it does not."""
    # `tmk` is `temperature_air_mean_2m`: the table says mean, the row declares nothing
    decided = _parameter("DwdObservationMetadata", "daily", "climate_summary", "tmk")
    assert decided.name == "temperature_air_mean_2m"
    assert decided.aggregation is None
    assert decided.effective_aggregation == "mean"
    # `tt_10` is the plain `temperature_air_2m`, whose DWD sheet says instant: declared
    declared = _parameter("DwdObservationMetadata", "10_minutes", "temperature_air", "tt_10")
    assert declared.name == "temperature_air_2m"
    assert PARAMETERS[declared.name].aggregation is None
    assert declared.aggregation == "instant"
    assert declared.effective_aggregation == "instant"
    # `pp_10` is the plain `pressure_air_site`, which the same page leaves unqualified: not stated
    undeclared = _parameter("DwdObservationMetadata", "10_minutes", "temperature_air", "pp_10")
    assert undeclared.name == "pressure_air_site"
    assert undeclared.aggregation is None
    assert undeclared.effective_aggregation is None


def _evidence_of(row: tuple[str, str, str, ParameterModel, str]) -> str | None:
    """Return how the declared `instant` of a row is backed: `text`, `entry`, or None."""
    metadata, resolution, dataset, parameter, evidence = row
    # a wording that states a reading and, in the same row, a mean or a maximum ("the highest of the 60 instantaneous
    # values", ECCC's wind "average of the one-, two- or ten-minute period ending at the time of observation") is no
    # evidence of a reading
    if _states_a_reading(evidence) and not _states_a_mean_or_a_maximum(evidence, resolution):
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
    """An entry quotes the page row (or note) or the descriptions of the rows it covers, and a declared row needs it."""
    declared = _declared()
    problems = []
    for entry in INSTANT_BY_REFERENCE_TIME:
        label = f"{entry.provider} {sorted(entry.resolutions)} {sorted(entry.datasets or [])} {sorted(entry.originals)}"
        assert entry.source in {"page", "description"}, label
        covered = [row for row in declared if entry.covers(row[0], row[1], row[2], row[3].name_original)]
        if not covered:
            problems.append(f"{label}: no declared row uses it")
        if entry.source == "page" and not (entry.section and entry.network):
            problems.append(f"{label}: a page entry names its section and network")
        for metadata, resolution, dataset, parameter, _evidence in covered:
            if entry.source == "page" and not _page_says(entry, resolution, dataset):
                problems.append(
                    f"{_site(metadata, resolution, dataset, parameter)}: the page has no {entry.quote!r} in the "
                    f"{'note' if entry.note else 'row'} of {entry.network}/{resolution} under '## {entry.section}'"
                )
            if entry.source == "description" and entry.quote not in (parameter.description or ""):
                problems.append(f"{_site(metadata, resolution, dataset, parameter)}: its description does not say it")
        # an entry names the fields it speaks for: a name that matches no row is a typo
        for original in entry.originals:
            if not any(row[0] == entry.provider and row[3].name_original == original for row in _rows()):
                problems.append(f"{label}: no row has the field {original!r}")
    assert not problems, "\n".join(problems)


def test_a_page_quote_is_tied_to_its_row() -> None:
    """The check of the quote reads the section, the network, the resolution, the dataset and the cell or note."""
    knmi = next(entry for entry in INSTANT_BY_REFERENCE_TIME if entry.provider == "KnmiObservationMetadata")
    assert _page_says(knmi, "hourly", "data")
    assert not _page_says(knmi, "daily", "data")
    assert not _page_says(knmi, "hourly", "other_dataset")
    assert not _page_says(InstantEvidence(**{**knmi.__dict__, "network": "poi"}), "hourly", "data")
    assert not _page_says(InstantEvidence(**{**knmi.__dict__, "section": "dwd"}), "hourly", "data")
    # a quote of a note is not found in a table row, and a quote of the time zone cell is no reference time
    assert not _page_says(InstantEvidence(**{**knmi.__dict__, "note": True}), "hourly", "data")
    assert not _page_says(InstantEvidence(**{**knmi.__dict__, "quote": "UTC"}), "hourly", "data")
    # a note that names its datasets speaks for those only
    note = InstantEvidence(**{**knmi.__dict__, "section": "dwd", "network": "observation", "note": True})
    subdaily = InstantEvidence(**{**note.__dict__, "quote": "Parsed as UTC"})
    assert _page_says(subdaily, "subdaily", "moisture")
    assert not _page_says(subdaily, "subdaily", "temperature_air")


def test_a_plain_name_left_null_does_not_state_a_mean_or_a_maximum() -> None:
    """A row without a statistic is one whose source states none: a stated mean (10 minutes or more) or maximum is read.

    A source that says "mean" or "maximum" of a plain name is a naming defect for the table (a `_mean` name, as the
    renames of GH-3134 did for DWD POI and NWS), not a reason for the row to say nothing. The few rows whose wording
    only looks like it are in `ALLOWED_UNDECLARED` with the reason.
    """
    used = set()
    wrong = []
    for metadata, resolution, dataset, parameter, evidence in _rows():
        if parameter.effective_aggregation is not None or not _states_a_mean_or_a_maximum(evidence, resolution):
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
        ("1-minute mean, averaged to 10 minutes", False, True),
        ("Wind speed. Mean over 10 minutes.", False, True),
        ("Air temperature 2 m above ground; hourly mean", False, True),
        ("Mittelwert der Stunde", False, True),
        ("moyenne horaire", False, True),
        ("velocidad media del viento", False, True),
        ("valor máximo de las 24 horas", False, True),
        ("the maximum gust of the hour", False, True),
        ("the highest gust", False, True),
        ("daily mean sea level pressure", False, True),
        ("Air pressure reduced to mean sea level", False, False),
        ("the highest of the 60 instantaneous values", True, True),
        ("The source's largest value (15 statute miles) can stand for a larger visibility.", False, False),
        ("it publishes the 10 minute maximum and minimum separately, as TMA and TMI", False, False),
        # the bare noun is wetterdienst's paraphrase, not a spot wording of the source
        ("Each value is dated by the instant it occurred; the source states no mean or interval.", False, False),
        ("Air temperature 2 m above ground.", False, False),
    ],
)
def test_the_wordings_are_read_as_they_are_meant(*, evidence: str, reading: bool, long_mean_or_maximum: bool) -> None:
    """Pin the two readers on the wordings of the sources, so that a change to a pattern is read here."""
    assert _states_a_reading(evidence) is reading
    assert _states_a_mean_or_a_maximum(evidence) is long_mean_or_maximum


def test_mean_sea_level_is_a_mean_only_in_a_daily_or_coarser_row() -> None:
    """KNMI daily `PG` says "Mean sea level pressure" for the mean of the day; an hourly row names the datum."""
    assert _states_a_mean_or_a_maximum("Mean sea level pressure", "daily")
    assert not _states_a_mean_or_a_maximum("Mean sea level pressure", "hourly")
