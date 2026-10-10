# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that a provider parameter carries the statistic its source says the value is.

The canonical name says what a number is -- a maximum, the mean of the daily maxima, a total over the
last 12 hours -- and `tests/test_api.py::test_metadata_parameter_table` can only check that the name
is a key of the table, not that it is the right one. What can be checked mechanically is where the
source's own description, which every parameter carries from `metadata.source_descriptions`, states
the statistic or the window in words the name has a slot for. Each rule below reads one such statement
and asks the name to carry it. They hold for every provider today, so a new one is held to them
without listing exceptions; a statement the source does not make is out of their reach, except that
below daily resolution a temperature the source says nothing about takes the spot name (GH-2657),
and the rules for that are the ones about spot and mean names further down. See GH-2614.
"""

import re
from collections.abc import Iterator

from tests.test_api import ALL_METADATA
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.model.metadata import ParameterModel
from wetterdienst.provider.aemet.observation import AemetObservationMetadata
from wetterdienst.provider.dwd.dmo import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix import DwdMosmixMetadata

# a dataset whose own interval is one of these needs no qualifier for a window of that many hours
_RESOLUTION_HOURS = {"hourly": 1, "6_hour": 6, "daily": 24}

_WINDOW = re.compile(
    r"\b(?:within|during|over|in|for|of) the (?:last|previous|preceding|past) (\d+)[ -]?(?:hours?|h)\b",
    re.IGNORECASE,
)
# "mean of the daily maximum", "monthly mean of daily temperature maxima", "average minimum"
_MEAN_OF_EXTREMES = re.compile(
    r"\b(?:mean|average) of (?:the )?(?:daily )?(?:\w+ )?(?:maxima|minima|maximum|minimum|max|min)\b"
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
                    site = (
                        f"{metadata.name} {resolution.name}/{dataset.name}/{parameter.name} [{parameter.name_original}]"
                    )
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
        if hours == _RESOLUTION_HOURS.get(resolution):
            continue
        if f"_last_{hours}h" not in parameter.name:
            wrong.append(f"{site}: {parameter.description!r} but the name has no `_last_{hours}h`")
    assert not wrong, "\n".join(wrong)


def test_a_mean_of_daily_extremes_is_named_a_mean() -> None:
    """A value the source calls the mean of the daily maxima or minima is `_max_..._mean` or `_min_..._mean`.

    The period's extreme and the mean of its daily extremes differ by ten degrees or more over a
    month, and the table keeps them apart. The CHMI monthly and annual files hold the mean (MDFUNCTION
    `AVG`) and were named for the extreme. The converse is checked more loosely: a name ending `_mean`
    after a `_max_` or `_min_` says the source averaged something, so its description must at least
    mention a mean or an average.
    """
    wrong = []
    for site, _, parameter in _parameters():
        description = parameter.description or ""
        says_mean_of_extremes = bool(_MEAN_OF_EXTREMES.search(description))
        named_mean_of_extremes = parameter.name.endswith("_mean") and (
            "_max_" in parameter.name or "_min_" in parameter.name
        )
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


def test_the_regex_for_a_mean_of_extremes_reads_dwds_wording() -> None:
    """DWD writes "Monthly mean of daily temperature maxima", with the quantity between the words."""
    for description in (
        "Monthly mean of daily temperature maxima at 2 m above ground.",
        "Annual mean of daily temperature minima in 2m height.",
        "Monthly mean of the maximum temperatures.",
    ):
        assert _MEAN_OF_EXTREMES.search(description), description
    assert not _MEAN_OF_EXTREMES.search("Monthly maximum of daily temperature maxima in 2 m above ground.")


def test_mosmix_and_dmo_name_tx_and_tn_for_their_twelve_hours() -> None:
    """MOSMIX and DMO `TX` and `TN` are `temperature_air_{max,min}_2m_last_12h` in every dataset that has them."""
    for metadata in (DwdMosmixMetadata, DwdDmoMetadata):
        seen = 0
        for dataset in metadata["hourly"]:
            names = {parameter.name_original: parameter.name for parameter in dataset.parameters}
            if "tx" in names:
                seen += 1
                assert names["tx"] == "temperature_air_max_2m_last_12h"
                assert names["tn"] == "temperature_air_min_2m_last_12h"
        assert seen == 2


def test_aemet_names_the_absolute_period_extremes_as_extremes() -> None:
    """AEMET monthly and annual `ta_max` and `ta_min` are the month's or year's extremes, not a `_multiday` total."""
    for resolution in ("monthly", "annual"):
        names = {parameter.name_original: parameter.name for parameter in AemetObservationMetadata[resolution]["data"]}
        assert names["ta_max"] == "temperature_air_max_2m"
        assert names["ta_min"] == "temperature_air_min_2m"
        # the means of the daily extremes are a different statistic with their own names
        assert names["tm_max"] == "temperature_air_max_2m_mean"
        assert names["tm_min"] == "temperature_air_min_2m_mean"


# the wordings sources use for a reading at one moment: DWD "instant", MeteoSwiss "current value",
# SMHI "Instantaneous value", MET Norway "present value", AEMET "at the time given by 'fint'", NOAA
# GHCN "at the time of observation"
_SPOT_VALUE = re.compile(
    r"\b(?:instantaneous|instant|current value|present value|at the time (?:of|given by))\b", re.IGNORECASE
)
# `temperature_air_mean_2m`, `temperature_soil_mean_0_05m`, `temperature_surface_mean`: the interval's mean
_MEAN_NAME = re.compile(r"^temperature_[a-z_]+?_mean(?:_\d+(?:_\d+)?m)?$")
# `temperature_air_2m`, `temperature_dew_point_2m`, `temperature_soil_0_05m`, `temperature_surface`: a
# reading at one moment
_SPOT_NAME = re.compile(r"^temperature_(?:(?:air|dew_point|wet|soil|radiant)_\d+(?:_\d+)?m|surface)$")
# daily and coarser: the resolutions from which a source that says nothing about the statistic keeps the
# `_mean_` name; below them it is named for a reading at one moment (GH-2657)
_COARSE_RESOLUTIONS = {"daily", "monthly", "annual"}
# a description that states the interval's mean: "Mean air temperature", "hourly mean", "Average ..."
_MEAN_STATED = re.compile(r"\b(?:mean|averag\w*|avg)\b", re.IGNORECASE)


def test_a_spot_value_the_source_states_is_not_named_a_mean() -> None:
    """A temperature the source calls an instant or current value is `temperature_<medium>_<height>`, not `_mean_`.

    The table keeps `temperature_air_2m` for a reading at one moment and `temperature_air_mean_2m`
    for the mean over the interval, and a 10-minute or hourly dataset that said `_mean_` for
    DWD's `tt_10` ("instant"), MeteoSwiss' `tre200s0` ("current value") or SMHI's 45 ("Instantaneous
    value") handed a caller a reading as though it averaged the interval (GH-2651). Only the statement
    is held: a name other than a mean (`temperature_air_max_2m` of "the highest of the 60
    instantaneous values") is not this rule's.
    """
    wrong = []
    for site, _, parameter in _parameters():
        if _MEAN_NAME.match(parameter.name) and _SPOT_VALUE.search(parameter.description or ""):
            wrong.append(f"{site}: {parameter.description!r} but the name is a mean, not a spot name")
    assert not wrong, "\n".join(wrong)


def test_a_spot_name_does_not_carry_a_description_that_states_a_mean() -> None:
    """A source that says the value is a mean or an average keeps the `_mean_` name, at every resolution.

    Below daily resolution a source that says nothing about the statistic takes the spot name
    (GH-2657), but one that says a mean (MeteoSwiss `tre200h0` "hourly mean", FMI "Mean over 1
    minute", NWS "Average", RMI "Mean", WSV "average") would have the name claim the opposite of what
    it states.
    """
    wrong = []
    for site, _, parameter in _parameters():
        if _SPOT_NAME.match(parameter.name) and _MEAN_STATED.search(parameter.description or ""):
            wrong.append(f"{site}: named a spot value, described {parameter.description!r}")
    assert not wrong, "\n".join(wrong)


def test_a_sub_daily_mean_name_needs_a_description_that_states_a_mean() -> None:
    """Below daily resolution a `_mean_` temperature name is for a source that says it is a mean.

    A source that says nothing about the statistic there takes the spot name (GH-2657), so a
    `_mean_` name on such a row would promise a mean the source does not state. Windowed names
    (`temperature_air_mean_2m_last_24h`) are not `_MEAN_NAME`s and are not this rule's.
    """
    wrong = []
    for site, resolution, parameter in _parameters():
        if (
            resolution not in _COARSE_RESOLUTIONS
            and _MEAN_NAME.match(parameter.name)
            and not _MEAN_STATED.search(parameter.description or "")
        ):
            wrong.append(f"{site}: named a mean, described {parameter.description!r}")
    assert not wrong, "\n".join(wrong)


def test_a_spot_name_at_daily_or_coarser_resolution_needs_a_spot_description() -> None:
    """From daily on, a spot name needs the source to say it is a reading at one moment.

    Below daily resolution a source that says nothing takes the spot name, but from daily on it keeps
    the `_mean_` name, so a spot name on such a row would claim more than the source states (NOAA GHCN
    daily `tobs`, "at the time of observation", is the one that says it).
    """
    wrong = []
    for site, resolution, parameter in _parameters():
        if (
            resolution in _COARSE_RESOLUTIONS
            and _SPOT_NAME.match(parameter.name)
            and not _SPOT_VALUE.search(parameter.description or "")
        ):
            wrong.append(f"{site}: named a spot value, described {parameter.description!r}")
    assert not wrong, "\n".join(wrong)


def test_the_regexes_for_a_spot_value_read_the_sources_wording() -> None:
    """The spot wordings match, the mean wordings and the names of the other statistics do not."""
    for description in (
        "Air temperature 2 m above ground, instant.",
        "Soil temperature at 5 cm depth; hourly current value",
        "Air temperature. Instantaneous value, once per hour.",
        "Air temperature (default 2 m above ground), present value",
        "Calculated dew point temperature at the time given by 'fint' (degrees Celsius).",
        "Temperature at the time of observation  (Fahrenheit or Celsius as per user preference)",
    ):
        assert _SPOT_VALUE.search(description), description
    for description in (
        "Air temperature 2 m above ground; hourly mean",
        "Air temperature. Mean over 1 minute.",
        "Air temperature 2 m above ground.",
    ):
        assert not _SPOT_VALUE.search(description), description
    for description in (
        "Air temperature 2 m above ground; hourly mean",
        "Average air temperature in 2m",
        "Mean over 1 minute",
    ):
        assert _MEAN_STATED.search(description), description
    for description in ("Air temperature 2 m above ground.", "Soil temperature in 10 cm depth.", "Instant value"):
        assert not _MEAN_STATED.search(description), description
    for name in ("temperature_air_mean_2m", "temperature_soil_mean_0_05m", "temperature_surface_mean"):
        assert _MEAN_NAME.match(name), name
        assert not _SPOT_NAME.match(name), name
    for name in (
        "temperature_air_2m",
        "temperature_dew_point_2m",
        "temperature_soil_0_05m",
        "temperature_air_0_05m",
        "temperature_wet_2m",
        "temperature_radiant_2m",
        "temperature_soil_1m",
        "temperature_surface",
    ):
        assert _SPOT_NAME.match(name), name
        assert not _MEAN_NAME.match(name), name
    for name in ("temperature_air_max_2m_mean", "temperature_air_mean_2m_last_24h", "temperature_soil_max_0_1m"):
        assert not _MEAN_NAME.match(name), name
        assert not _SPOT_NAME.match(name), name


def test_a_spot_name_behaves_as_the_mean_name_beside_it() -> None:
    """A spot name has the unit type, interpolation and lapse rate of its `_mean_` counterpart.

    Spatially a reading at one moment is the same field as the mean over the interval, so a caller
    who interpolates `temperature_dew_point_2m` gets the radius and the elevation correction of
    `temperature_dew_point_mean_2m` (GH-2651); a spot name declared without them is silently
    skipped by the interpolation.
    """
    spot = [parameter.name for parameter in PARAMETER_TABLE if _SPOT_NAME.match(parameter.name)]
    assert spot
    wrong = []
    for name in spot:
        counterpart = (
            f"{name}_mean"
            if name == "temperature_surface"
            else re.sub(r"^(temperature_(?:air|dew_point|wet|soil|radiant))_", r"\1_mean_", name)
        )
        if counterpart not in PARAMETERS:
            wrong.append(f"{name}: has no {counterpart}")
            continue
        for field in ("unit_type", "interpolation", "zero_inflated", "lapse_rate"):
            if getattr(PARAMETERS[name], field) != getattr(PARAMETERS[counterpart], field):
                wrong.append(f"{name}: {field} differs from {counterpart}")
    assert not wrong, "\n".join(wrong)
