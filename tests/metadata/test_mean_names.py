# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that the word `mean` in a canonical parameter name follows what the source says (GH-3151).

The rule is the one temperature has had since GH-2657, for every intensive quantity (one that has a value at a
moment): the plain name is a reading at one moment or a source that states no statistic, `_mean` is the mean of the
row's own interval, stated by the source in its own words or its own field name, and a mean over a window shorter
than the interval keeps the window (`_mean_last_10min`). Accumulations (`precipitation_amount`, `sunshine_duration`)
are totals by nature and carry no word, and `_max` / `_min` are extremes.

`MEAN_NAMED` lists the quantities the rule has been applied to, one family per change; the others are named as they
were and are not held to it yet. The evidence is what `test_parameter_statistics` reads: the source's description
(not a canonical or a derived one) and the source's field name, which also counts in German (`*_mittel`), Polish
(`średni*`), Spanish (`*media`), French (`moyen`), Dutch (`gemiddeld`) and Swedish (`medel`).
"""

import re
from collections.abc import Iterator

from tests.metadata.test_parameter_statistics import _source_description, _states_a_mean
from tests.test_api import ALL_METADATA

# the plain names of the quantities named by the rule so far, each with its `_mean` beside it
MEAN_NAMED = (
    "cloud_cover_total",
    "humidity_relative",
    "precipitation_intensity",
    "pressure_air_sea_level",
    "pressure_air_site",
    "pressure_vapor",
    "radiation_global_intensity",
    "radiation_sky_long_wave_intensity",
    "radiation_sky_short_wave_diffuse_intensity",
    "snow_depth",
    "visibility",
    "wind_direction",
    "wind_force_beaufort",
    "wind_speed",
)
# a family of quantities by the start of the plain name: one per ground cover, soil type and layer
MEAN_NAMED_PREFIXES = ("soil_moisture_",)
# quantities of which every row states a mean, so that no plain name is left
_NO_PLAIN_ROW = {"radiation_sky_long_wave_intensity"}

_MEAN_IN_THE_FIELD_NAME = re.compile(r"mittel|średni|media\b|moyen|gemiddeld|medel", re.IGNORECASE)

# rows whose source states a mean and whose name is plain on purpose
_PLAIN_ON_PURPOSE = {
    # the BUFR template of the road messages states -10, -15 and 0 minutes in different station groups, so no one window
    # is right for the merged dataset (GH-3010)
    ("DwdRoadMetadata", "15_minutes", "data", "windSpeed"),
    ("DwdRoadMetadata", "15_minutes", "data", "windDirection"),
    # the glossary says "the one-, two- or ten-minute period ending at the time of observation", so no one window
    # fits the column (GH-2837); its direction states two minutes and is named for them
    ("EcccObservationMetadata", "hourly", "data", "wind_speed"),
}
# a provider whose "average" is not evidence yet: PEGELONLINE publishes raw data at the equidistance of each station and
# the audit of GH-2614 doubts the descriptions, so its rows wait for WSV's confirmation (GH-3151)
_NOT_EVIDENCE = {"WsvPegelMetadata"}


def _quantity(name: str) -> str:
    """Return the plain name a name is made from: `wind_speed_mean` and `cloud_cover_total_mean_sunrise_to_sunset`."""
    return re.sub(r"_mean(?=_|$)", "", name, count=1)


def _is_named(base: str) -> bool:
    """Say whether the rule has been applied to the quantity of a plain name."""
    return base in MEAN_NAMED or base.startswith(MEAN_NAMED_PREFIXES)


def _rows() -> Iterator[tuple[str, str, str, str, str, bool]]:
    """Yield `(metadata, resolution, dataset, name, name_original, states_a_mean)` for the rows of `MEAN_NAMED`."""
    for metadata in ALL_METADATA:
        for resolution in metadata:
            for dataset in resolution:
                for parameter in dataset.parameters:
                    base = _quantity(parameter.name)
                    if not _is_named(base) or "_mean_last_" in parameter.name:
                        # the means of a window shorter than the interval are held by test_parameter_statistics
                        continue
                    description = _source_description(metadata.name, resolution.name, dataset.name, parameter)
                    evidence = f"{description} {parameter.name_original}".strip()
                    states = _states_a_mean(evidence, resolution.name) or bool(
                        _MEAN_IN_THE_FIELD_NAME.search(parameter.name_original)
                    )
                    yield metadata.name, resolution.name, dataset.name, parameter.name, parameter.name_original, states


def test_a_source_that_states_a_mean_gets_the_mean_name() -> None:
    """A row of a named quantity whose source states a mean of its interval is `<quantity>_mean`, not the plain name."""
    wrong = [
        f"{metadata} {resolution}/{dataset}/{name} [{original}]: the source states a mean, the name is plain"
        for metadata, resolution, dataset, name, original, states in _rows()
        if states
        and _quantity(name) == name
        and metadata not in _NOT_EVIDENCE
        and (metadata, resolution, dataset, original) not in _PLAIN_ON_PURPOSE
    ]
    assert not wrong, "\n".join(wrong)


def test_a_mean_name_needs_a_source_that_states_a_mean() -> None:
    """A `<quantity>_mean` row is one the source calls a mean (or an average): the name claims no more than it says."""
    wrong = [
        f"{metadata} {resolution}/{dataset}/{name} [{original}]: named a mean, but the source states none"
        for metadata, resolution, dataset, name, original, states in _rows()
        if _quantity(name) != name and not states
    ]
    assert not wrong, "\n".join(wrong)


def test_the_plain_name_of_a_named_quantity_is_where_the_source_states_none() -> None:
    """At least one row keeps each plain name, so the description of the plain name has a row to describe."""
    plain = {name for _, _, _, name, _, _ in _rows() if _quantity(name) == name}
    assert set(MEAN_NAMED) - plain == _NO_PLAIN_ROW
