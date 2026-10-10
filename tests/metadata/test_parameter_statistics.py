# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that a provider parameter carries the statistic its source says the value is.

The canonical name says what a number is -- a maximum, the mean of the daily maxima, a total over the
last 12 hours -- and `tests/test_api.py::test_metadata_parameter_table` can only check that the name
is a key of the table, not that it is the right one. What can be checked mechanically is where the
source's own description, which every parameter carries from `metadata.source_descriptions`, states
the statistic or the window in words the name has a slot for. Each rule below reads one such statement
and asks the name to carry it. They hold for every provider today, so a new one is held to them
without listing exceptions; a statement the source does not make (most do not say whether a reading is
spot or mean) is out of their reach and is a question for review, see GH-2614.
"""

import re
from collections.abc import Iterator

import pytest

from tests.test_api import ALL_METADATA
from wetterdienst.model.metadata import ParameterModel

# a dataset whose own interval is one of these needs no qualifier for a window of that many hours
_RESOLUTION_HOURS = {"hourly": 1, "6_hour": 6, "12_hour": 12, "daily": 24}

_WINDOW = re.compile(
    r"\b(?:within|during|over|in|for|of) the (?:last|previous|preceding|past) (\d+)[ -]?(?:hours?|h)\b",
    re.IGNORECASE,
)
# "mean of the daily maximum", "monthly mean of the maximum temperatures", "average minimum"
_MEAN_OF_EXTREMES = re.compile(
    r"\b(?:mean|average) of (?:the )?(?:daily )?(?:maximum|minimum|max|min)\b"
    r"|\b(?:mean|average) (?:daily )?(?:maximum|minimum)\b",
    re.IGNORECASE,
)
_MULTIDAY = re.compile(r"multi-?day|several days", re.IGNORECASE)
_PREVIOUS_DAY = re.compile(r"previous day|yesterday|day before", re.IGNORECASE)
_NORMAL = re.compile(r"\bnormals?\b", re.IGNORECASE)


def _parameters() -> Iterator[tuple[str, str, ParameterModel]]:
    """Yield `(site, resolution, parameter)` for every declared parameter of every provider."""
    for metadata in ALL_METADATA:
        for resolution in metadata:
            for dataset in resolution:
                for parameter in dataset.parameters:
                    site = f"{metadata.name} {resolution.name}/{dataset.name}/{parameter.name} [{parameter.name_original}]"
                    yield site, resolution.name, parameter


def test_a_window_the_source_states_is_in_the_name() -> None:
    """A value the source says covers the last N hours is named `_last_<N>h`, unless N is the dataset's own interval.

    DWD MOSMIX and DMO `TX` and `TN` are "within the last 12 hours" in an hourly dataset and were
    named plain `temperature_air_max_2m` and `temperature_air_min_2m`, which every other provider
    reads as the maximum over the dataset's own interval -- the name DWD POI's own 12-hour extremes
    already carried is `temperature_air_max_2m_last_12h`. In a daily dataset "the last 24 hours" is the
    day itself and takes the plain name.
    """
    wrong = []
    for site, resolution, parameter in _parameters():
        match = _WINDOW.search(parameter.description or "")
        if not match:
            continue
        hours = int(match.group(1))
        # one hour is every hourly dataset's own interval and no name carries it for the hourly datasets
        if hours == 1 or hours == _RESOLUTION_HOURS.get(resolution):
            continue
        if f"_last_{hours}h" not in parameter.name:
            wrong.append(f"{site}: {parameter.description!r} but the name has no `_last_{hours}h`")
    assert not wrong, "\n".join(wrong)


def test_a_mean_of_daily_extremes_is_named_a_mean() -> None:
    """A value the source calls the mean of the daily maxima or minima is `_max_..._mean` or `_min_..._mean`.

    The period's extreme and the mean of its daily extremes differ by ten degrees or more over a
    month, and the table keeps them apart. The CHMI monthly and annual files hold the mean (MDFUNCTION
    `AVG`) and were named for the extreme. The converse holds as well: a name ending `_mean` after a
    `_max_` or `_min_` says the source averaged something, and a description that never says so is
    a name the source does not support.
    """
    wrong = []
    for site, _, parameter in _parameters():
        description = parameter.description or ""
        says_mean_of_extremes = bool(_MEAN_OF_EXTREMES.search(description))
        named_mean_of_extremes = parameter.name.endswith("_mean") and ("_max_" in parameter.name or "_min_" in parameter.name)
        if says_mean_of_extremes and not named_mean_of_extremes:
            wrong.append(f"{site}: {description!r} but the name is not a `_max_..._mean` or `_min_..._mean`")
        if named_mean_of_extremes and not re.search(r"\b(?:mean|average)\b", description, re.IGNORECASE):
            wrong.append(f"{site}: named a mean of extremes, described {description!r}")
    assert not wrong, "\n".join(wrong)


def test_the_special_statistics_in_a_name_are_the_ones_the_source_states() -> None:
    """`_multiday`, `_yesterday` and `_normal` are only for a source that says it is one.

    `_multiday` is a total or extreme a station reports over several days where it did not report
    daily (NOAA GHCN's `MDTX`, `MDPR`); AEMET's monthly and annual absolute extremes took it because
    they arrive with the date they occurred on, and are plain `temperature_air_max_2m`. `_yesterday`
    and `_normal` are the previous day's value and the climatological normal.
    """
    wrong = []
    for site, _, parameter in _parameters():
        text = f"{parameter.description or ''} {parameter.name_original}"
        for token, pattern in (("_multiday", _MULTIDAY), ("_yesterday", _PREVIOUS_DAY), ("_normal", _NORMAL)):
            if token in parameter.name and not pattern.search(text):
                wrong.append(f"{site}: named `{token}`, but the source says {parameter.description!r}")
    assert not wrong, "\n".join(wrong)
