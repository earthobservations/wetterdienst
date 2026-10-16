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

The rules about spot and mean names read only what the source says: a description that comes from
`DERIVED_DESCRIPTIONS`, or the canonical sentence a parameter reads when no table describes it, is
written from the row's canonical name, so it would agree with whatever name the row has, and is left
out (`_source_description`, GH-2660). The field's own name counts, as RMI's
`temp_dry_shelter_avg` does. A mean over a window shorter than the row's interval, KNMI's
"1 Min Mean" in a 10-minute row, is a reading at one moment (`_states_a_mean`). What this leaves out
is a generated description that disagrees with its row's name: nothing reads it any more.
"""

import re
from collections.abc import Iterator

from tests.test_api import ALL_METADATA
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.metadata.source_descriptions import DERIVED_DESCRIPTIONS, SOURCE_DESCRIPTIONS
from wetterdienst.model.metadata import ParameterModel
from wetterdienst.provider.aemet.observation import AemetObservationMetadata
from wetterdienst.provider.dwd.derived import DwdDerivedMetadata
from wetterdienst.provider.dwd.dmo import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix import DwdMosmixMetadata
from wetterdienst.provider.dwd.observation import DwdObservationMetadata
from wetterdienst.provider.dwd.poi import DwdPoiMetadata
from wetterdienst.provider.dwd.road import DwdRoadMetadata
from wetterdienst.provider.dwd.swsmos import DwdSwsmosMetadata
from wetterdienst.provider.eccc.observation import EcccObservationMetadata
from wetterdienst.provider.fmi.observation import FmiObservationMetadata
from wetterdienst.provider.knmi.observation import KnmiObservationMetadata
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationMetadata
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopMetadata
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationMetadata
from wetterdienst.provider.metno.frost.api import MetnoFrostMetadata
from wetterdienst.provider.metoffice.observation import MetOfficeObservationMetadata
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata
from wetterdienst.provider.nws.observation import NwsObservationMetadata
from wetterdienst.provider.rmi.observation import RmiObservationMetadata
from wetterdienst.provider.smhi.observation import SmhiObservationMetadata

# a dataset whose own interval is one of these needs no qualifier for a window of that many hours
_RESOLUTION_HOURS = {"hourly": 1, "6_hours": 6, "daily": 24}

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


def _names_a_window(name: str, hours: int) -> bool:
    """Say whether `name` carries the window `_last_<hours>h`, as a whole token.

    A substring test finds `_last_1h` in `_last_1hx`; this one asks for the token to end there.
    """
    return re.search(rf"_last_{hours}h(?:_|$)", name) is not None


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


def _source_description(metadata_name: str, resolution: str, dataset: str, parameter: ParameterModel) -> str:
    """Return the parameter's description, or "" where it is `DERIVED_DESCRIPTIONS`' or the canonical one.

    A derived description is written from the canonical name of the row, so reading a statistic out of
    it asks the name whether it is right (GH-2660): "Mean temperature of the ground surface." for
    SWSMOS `TS` was generated from `temperature_surface_mean`, and the source says "Temperatur der
    Fahrbahnoberfläche". What a provider module declares and what `SOURCE_DESCRIPTIONS` holds count as
    the source's, which `build_metadata_model` fills in before the derived text. The canonical sentence a
    parameter reads when no table describes it (GH-1979) is written from the quantity as a derived one is,
    and is left out the same way.
    """
    key = (resolution, dataset, parameter.name_original)
    if (
        key not in SOURCE_DESCRIPTIONS.get(metadata_name, {})
        and key not in DERIVED_DESCRIPTIONS.get(metadata_name, {})
        and parameter.description == PARAMETERS[parameter.name].description
    ):
        return ""
    derived = DERIVED_DESCRIPTIONS.get(metadata_name, {}).get(key)
    if (
        derived is not None
        and key not in SOURCE_DESCRIPTIONS.get(metadata_name, {})
        and parameter.description == derived
    ):
        return ""
    return parameter.description or ""


def _sourced_parameters() -> Iterator[tuple[str, str, ParameterModel, str]]:
    """Yield `(site, resolution, parameter, evidence)` for every parameter, `evidence` being what the source says.

    That is the source's description (see `_source_description`) and the name the source gives the field,
    which is where RMI says `temp_dry_shelter_avg` and DMI `mean_temp`.
    """
    for metadata in ALL_METADATA:
        for resolution in metadata:
            for dataset in resolution:
                for parameter in dataset.parameters:
                    site = (
                        f"{metadata.name} {resolution.name}/{dataset.name}/{parameter.name} [{parameter.name_original}]"
                    )
                    description = _source_description(metadata.name, resolution.name, dataset.name, parameter)
                    yield site, resolution.name, parameter, f"{description} {parameter.name_original}".strip()


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
        if not _names_a_window(parameter.name, hours):
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
# `temperature_air_mean_2m`, `temperature_soil_mean_0_05m`, `temperature_surface_mean`: the interval's mean,
# and `error_absolute_temperature_air_mean_2m`, the error of a temperature of that name (GH-2659)
_MEAN_NAME = re.compile(r"^(?:error_absolute_)?temperature_[a-z_]+?_mean(?:_\d+(?:_\d+)?m)?$")
# `temperature_air_2m`, `temperature_dew_point_2m`, `temperature_soil_0_05m`, `temperature_surface`: a
# reading at one moment
_SPOT_NAME = re.compile(r"^temperature_(?:(?:air|dew_point|wet|soil|radiant)_\d+(?:_\d+)?m|surface)$")
# daily and coarser: the resolutions from which a source that says nothing about the statistic keeps the
# `_mean_` name; below them it is named for a reading at one moment (GH-2657)
_COARSE_RESOLUTIONS = {"daily", "monthly", "annual"}
# a mean or an average, in a description ("hourly mean", "Average ...") or in the source's field name
# (`temp_dry_shelter_avg`, `mean_temp`, where `_` separates words); "mean sea level" is not one
_MEAN_WORD = re.compile(r"(?<![a-z])(?:mean(?!(?:\s+|_)sea(?![a-z]))|averag\w*|avg)(?![a-z])", re.IGNORECASE)
# a mean over a stated number of minutes: KNMI "1 Min Mean", FMI "Mean over 1 minute", and DWD's urban
# hourly sheets, which give the mean value of the 1 minute interval ending ten minutes before the hour
_MEAN_WINDOW = re.compile(
    r"(?<![\d.])(\d+)[ -]?min(?:ute)?s?\b[ -]*(?:mean|average)|\b(?:mean|average) over (\d+)[ -]?min(?:ute)?s?\b"
    r"|\b(?:mean|average) value of the (\d+)[ -]?min(?:ute)?s? interval\b",
    re.IGNORECASE,
)
# the minutes a value of the resolution covers, for the resolutions that are a fixed number of them
_INTERVAL_MINUTES = {
    "1_minute": 1,
    "5_minutes": 5,
    "6_minutes": 6,
    "10_minutes": 10,
    "15_minutes": 15,
    "hourly": 60,
    # the shortest step of a subdaily dataset (Météo-France SYNOP is three-hourly)
    "subdaily": 180,
    "6_hours": 360,
    "daily": 1440,
}


def _states_a_mean(evidence: str, resolution: str) -> bool:
    """Say whether `evidence` states the mean of the row's own interval.

    A mean over a window shorter than the interval, as FMI's "Mean over 1 minute" in an hourly row
    and KNMI's "1 Min Mean" in a 10-minute one, is a reading taken at one moment and not the mean of
    the interval (GH-2660), so it does not count.
    """
    if not _MEAN_WORD.search(evidence):
        return False
    interval = _INTERVAL_MINUTES.get(resolution)
    for match in _MEAN_WINDOW.finditer(evidence):
        if interval is not None and int(match.group(1) or match.group(2) or match.group(3)) < interval:
            return False
    return True


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
    for site, _, parameter, evidence in _sourced_parameters():
        if _MEAN_NAME.match(parameter.name) and _SPOT_VALUE.search(evidence):
            wrong.append(f"{site}: {evidence!r} but the name is a mean, not a spot name")
    assert not wrong, "\n".join(wrong)


def test_a_spot_name_does_not_carry_a_description_that_states_a_mean() -> None:
    """A source that says the value is a mean or an average keeps the `_mean_` name, at every resolution.

    Below daily resolution a source that says nothing about the statistic takes the spot name
    (GH-2657), but one that says a mean of the row's own interval (MeteoSwiss `tre200h0` "hourly
    mean", IPMA "média da hora", RMI `temp_dry_shelter_avg`) would have the name claim the opposite of
    what it states. A mean over a shorter window (FMI "Mean over 1 minute" in an hourly row, KNMI
    "1 Min Mean" in a 10-minute one) is a reading at one moment and takes the spot name (GH-2660).
    """
    wrong = []
    for site, resolution, parameter, evidence in _sourced_parameters():
        if _SPOT_NAME.match(parameter.name) and _states_a_mean(evidence, resolution):
            wrong.append(f"{site}: named a spot value, but the source says {evidence!r}")
    assert not wrong, "\n".join(wrong)


def test_a_sub_daily_mean_name_needs_a_description_that_states_a_mean() -> None:
    """Below daily resolution a `_mean_` temperature name is for a source that says it is a mean.

    A source that says nothing about the statistic there takes the spot name (GH-2657), so a
    `_mean_` name on such a row would promise a mean the source does not state. Windowed names
    (`temperature_air_mean_2m_last_24h`) are not `_MEAN_NAME`s and are not this rule's.
    """
    wrong = []
    for site, resolution, parameter, evidence in _sourced_parameters():
        if (
            resolution not in _COARSE_RESOLUTIONS
            and _MEAN_NAME.match(parameter.name)
            and not _states_a_mean(evidence, resolution)
        ):
            wrong.append(f"{site}: named a mean, but the source says {evidence!r}")
    assert not wrong, "\n".join(wrong)


def test_a_spot_name_at_daily_or_coarser_resolution_needs_a_spot_description() -> None:
    """From daily on, a spot name needs the source to say it is a reading at one moment.

    Below daily resolution a source that says nothing takes the spot name, but from daily on it keeps
    the `_mean_` name, so a spot name on such a row would claim more than the source states (NOAA GHCN
    daily `tobs`, "at the time of observation", is the one that says it).
    """
    wrong = []
    for site, resolution, parameter, evidence in _sourced_parameters():
        if resolution in _COARSE_RESOLUTIONS and _SPOT_NAME.match(parameter.name) and not _SPOT_VALUE.search(evidence):
            wrong.append(f"{site}: named a spot value, but the source says {evidence!r}")
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
    for description, resolution in (
        ("Air temperature 2 m above ground; hourly mean", "hourly"),
        ("Average air temperature in 2m", "hourly"),
        ("Air Temperature 10 cm Mean", "10_minutes"),
        ("Mean over 10 minutes", "10_minutes"),
        ("Air Temperature 10 Min Mean", "10_minutes"),
        ("Air temperature recorded at 1.5 m height, hourly mean. temperatura", "hourly"),
        ("temp_dry_shelter_avg", "hourly"),
        ("mean_temp", "hourly"),
    ):
        assert _states_a_mean(description, resolution), description
    for description, resolution in (
        ("Air temperature 2 m above ground.", "hourly"),
        ("Soil temperature in 10 cm depth.", "hourly"),
        ("Instant value", "hourly"),
        # a window shorter than the row's interval
        ("Air temperature. Mean over 1 minute.", "hourly"),
        ("Air Temperature 1 Min Mean", "10_minutes"),
        ("Air temperature. Mean over 1 minute.", "subdaily"),
        # DWD urban hourly: the mean of the 1 minute interval ending ten minutes before the hour
        ("2m air temperature, at UTC 11 the mean value of the 1 minute interval ending UTC 10:50", "hourly"),
        ("Dew Point Temperature 1 Min Mean", "10_minutes"),
        # a mean that is not a statistic of the value
        ("Air pressure reduced to mean sea level", "hourly"),
        ("Pressure above mean sea level", "10_minutes"),
        ("mean_sea_level_pressure", "hourly"),
        ("meaning", "hourly"),
    ):
        assert not _states_a_mean(description, resolution), description
    for name in (
        "temperature_air_mean_2m",
        "temperature_soil_mean_0_05m",
        "temperature_surface_mean",
        "error_absolute_temperature_air_mean_2m",
        "error_absolute_temperature_dew_point_mean_2m",
    ):
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
    for name in (
        "temperature_air_max_2m_mean",
        "temperature_air_mean_2m_last_24h",
        "temperature_soil_max_0_1m",
        "error_absolute_temperature_air_2m",
        "error_absolute_wind_speed",
    ):
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


def test_a_derived_description_is_not_evidence_of_a_statistic() -> None:
    """A description written from the canonical name says nothing about the source, and is left out.

    RMI's "Mean air temperature at 2 m above ground." is the canonical sentence the model falls back to
    (GH-1979), and Météo-France SYNOP `td` is in `DERIVED_DESCRIPTIONS`, so neither is read (the field
    name `temp_dry_shelter_avg` still is), whereas MeteoSwiss' "hourly mean" is the source's.
    """
    rmi = next(m for m in ALL_METADATA if m.name == "RmiObservationMetadata")
    swiss = next(m for m in ALL_METADATA if m.name == "MeteoswissObservationMetadata")
    derived = next(p for p in rmi["hourly"]["data"] if p.name_original == "temp_dry_shelter_avg")
    sourced = next(p for p in swiss["hourly"]["data"] if p.name_original == "tre200h0")
    assert derived.description == "Mean air temperature at 2 m above ground."
    assert _source_description(rmi.name, "hourly", "data", derived) == ""
    synop = next(m for m in ALL_METADATA if m.name == "MeteoFranceSynopMetadata")
    dew_point = next(p for p in synop["subdaily"]["data"] if p.name_original == "td")
    assert dew_point.description
    assert _source_description(synop.name, "subdaily", "data", dew_point) == ""
    assert "hourly mean" in sourced.description
    assert _source_description(swiss.name, "hourly", "data", sourced) == sourced.description


def test_a_window_name_must_end_where_the_window_does() -> None:
    """`_last_1h` is a whole token of a name, not a prefix of `_last_1hx` or of `_last_12h`."""
    assert _names_a_window("temperature_air_max_2m_last_12h", 12)
    assert _names_a_window("precipitation_amount_last_1h", 1)
    assert _names_a_window("temperature_air_max_2m_last_1h_mean", 1)
    assert not _names_a_window("temperature_air_max_2m_last_12h", 1)
    assert not _names_a_window("temperature_air_max_2m_last_1hx", 1)
    assert not _names_a_window("temperature_air_max_2m", 12)


# a mean over a stated number of minutes, in the words the wind rows use: DWD "10-minute mean" and
# "10-Min-Mittel", POI "Mean wind speed over the last 10 minutes", AEMET "Mean wind speed ... over the 10
# minutes preceding 'fint'", FMI and SMHI "Mean over 10 minutes", Météo-France "averaged over 10 minutes",
# MET Norway "over the last ten minutes", NWS "the 2-minute average of the ASOS" and ECCC "the average of the
# two minutes ending at the time of observation". "the average of the six 10-minute intervals" of DWD's urban
# hourly sheets is the mean of the whole hour, not of a window in it
_WIND_MEAN_WINDOW = re.compile(
    # the window follows the mean in the same sentence
    r"\b(?:mean|average|averaged)\b(?:(?!\.\s).){0,100}?"
    r"\b(?P<before>\d+|one|two|ten)[ -]?min(?:ute)?s?\b(?![ -]*intervals\b)"
    r"|\b(?P<after>\d+|one|two|ten)[ -]?min(?:ute)?s?\b[ -]*(?:mean|average|mittel)",
    re.IGNORECASE,
)
_NUMBER_WORDS = {"one": 1, "two": 2, "ten": 10}
_TEN_MINUTES = re.compile(r"\b(?:10|ten)[ -]?min(?:ute)?s?\b", re.IGNORECASE)
_WIND_MEAN_NAMES = {"wind_speed": "wind_speed_last_10min", "wind_direction": "wind_direction_last_10min"}
_TWO_MINUTES = re.compile(r"\b(?:2|two)[ -]?min(?:ute)?s?\b", re.IGNORECASE)
_TWO_MINUTE_WIND_NAMES = {"wind_speed_last_2min", "wind_direction_last_2min"}
_GUST_LAST_10MIN = "wind_gust_max_last_10min"

# Rows named `wind_speed` or `wind_direction` below daily resolution whose source states a mean over a window
# shorter than the row's interval, found by the rule below and left as they are by the change that found them.
# GH-2697 moved DWD wind_synoptic, DWD POI and AEMET hourly, GH-2707 FMI, MET Norway, SMHI and Météo-France hourly,
# so none is left. A row the rule finds in a provider added later goes here until its pass of GH-2688; the test
# also fails when an entry no longer matches, so the list only shrinks.
_WIND_MEAN_WINDOW_NOT_YET_NAMED: dict[str, str] = {}


def _states_a_shorter_wind_mean(evidence: str, resolution: str) -> bool:
    """Say whether `evidence` states a mean over fewer minutes than a sub-daily row's interval.

    From daily on the mean of readings that are each a 10-minute mean (Météo-France `FFM`, "Daily mean of
    the wind force averaged over 10 minutes") is the mean of the interval and takes the plain name.
    """
    interval = _INTERVAL_MINUTES.get(resolution)
    if interval is None or resolution in _COARSE_RESOLUTIONS:
        return False
    for match in _WIND_MEAN_WINDOW.finditer(evidence):
        window = (match.group("before") or match.group("after")).lower()
        if _NUMBER_WORDS.get(window, int(window) if window.isdigit() else interval) < interval:
            return True
    return False


def _shorter_wind_mean_sites() -> list[str]:
    return [
        site
        for site, resolution, parameter, evidence in _sourced_parameters()
        if parameter.name in _WIND_MEAN_NAMES and _states_a_shorter_wind_mean(evidence, resolution)
    ]


def test_a_wind_mean_over_a_shorter_window_is_not_named_the_interval_mean() -> None:
    """`wind_speed` and `wind_direction` state no window shorter than the row's interval.

    A source that does state one takes `_last_10min` (`_last_2min` for two minutes). The table's `wind_speed` is
    the "mean speed of the wind over the period", so DWD's hourly `ff`
    ("10-Min-Mittel der Windgeschwindigkeit"), DWD POI's "Mean wind speed over the last 10 minutes" and
    AEMET's "over the 10 minutes preceding 'fint'" handed a caller the 10 minutes before the hour as though
    it were the hour's mean (GH-2697). The rule is the one for temperatures (GH-2660): a mean over a window
    shorter than the interval is not the interval's mean. Rows found by it in other providers are listed in
    `_WIND_MEAN_WINDOW_NOT_YET_NAMED`.
    """
    found = _shorter_wind_mean_sites()
    wrong = [site for site in found if site not in _WIND_MEAN_WINDOW_NOT_YET_NAMED]
    assert not wrong, "\n".join(
        f"{site}: the source states a mean over a window shorter than the interval, the name is the interval's mean"
        for site in wrong
    )
    stale = [site for site in _WIND_MEAN_WINDOW_NOT_YET_NAMED if site not in found]
    assert not stale, f"no longer found by the rule, remove from the list: {stale}"


def test_the_ten_minute_wind_names_are_for_a_window_the_source_states() -> None:
    """`wind_speed_last_10min` and `wind_direction_last_10min` are only for a stated 10 minutes in a longer row."""
    wrong = []
    for site, resolution, parameter, evidence in _sourced_parameters():
        if parameter.name not in _WIND_MEAN_NAMES.values():
            continue
        if not _TEN_MINUTES.search(evidence):
            wrong.append(f"{site}: named a 10-minute mean, but the source says {evidence!r}")
        elif _INTERVAL_MINUTES.get(resolution, 0) <= 10:
            wrong.append(f"{site}: named for a window shorter than the interval, but the interval is {resolution}")
    assert not wrong, "\n".join(wrong)


def test_the_two_minute_wind_names_are_for_a_window_the_source_states() -> None:
    """`wind_speed_last_2min` and `wind_direction_last_2min` are only for a stated 2 minutes in a longer row."""
    seen = set()
    wrong = []
    for site, resolution, parameter, evidence in _sourced_parameters():
        if parameter.name not in _TWO_MINUTE_WIND_NAMES:
            continue
        seen.add(parameter.name)
        if not _TWO_MINUTES.search(evidence):
            wrong.append(f"{site}: named a 2-minute mean, but the source says {evidence!r}")
        elif _INTERVAL_MINUTES.get(resolution, 0) <= 2:
            wrong.append(f"{site}: named for a window shorter than the interval, but the interval is {resolution}")
    assert not wrong, "\n".join(wrong)
    assert seen == _TWO_MINUTE_WIND_NAMES


def test_the_ten_minute_gust_name_is_for_a_window_the_source_states() -> None:
    """`wind_gust_max_last_10min` is only for a stated 10 minutes in a longer row, and `wind_gust_max` is not one.

    FMI "Maximum over 10 minutes", Météo-France SYNOP "rafales sur les 10 dernières minutes", Met Office "10
    minute maximum gust speed" and the NWS reportable gust, "the highest gust stored in memory for the past 10
    minutes", are not the strongest gust of the hour or of the three hours they sit in, which is what the plain
    name says (GH-2836). Other providers' `wind_gust_max` rows are held to the same: none states a 10-minute
    window in a row longer than that.
    """
    seen = 0
    wrong = []
    for site, resolution, parameter, evidence in _sourced_parameters():
        if parameter.name not in (_GUST_LAST_10MIN, "wind_gust_max"):
            continue
        says_ten = bool(_TEN_MINUTES.search(evidence))
        longer = _INTERVAL_MINUTES.get(resolution, 0) > 10
        if parameter.name == _GUST_LAST_10MIN:
            seen += 1
            if not says_ten:
                wrong.append(f"{site}: named a 10-minute gust, but the source says {evidence!r}")
            elif not longer:
                wrong.append(f"{site}: named for a window shorter than the interval, but the interval is {resolution}")
        elif says_ten and longer:
            wrong.append(f"{site}: the source states 10 minutes ({evidence!r}), the name is the interval's gust")
    assert not wrong, "\n".join(wrong)
    assert seen == 4


def test_nws_eccc_and_the_gust_rows_name_their_windows() -> None:
    """The rows GH-2836 and GH-2837 name, and the ones they leave.

    NWS `windspeed` and `winddirection` are the ASOS's 2-minute averages and `windgust` its 10-minute peak. ECCC's
    hourly direction is "the average direction during the two minute period ending at the time of observation",
    where its speed is the average of "the one-, two- or ten-minute period" and keeps `wind_speed`, as
    `noaa/ghcn` does, for which the GHCNh documentation states no window.
    """
    nws = {p.name_original: p.name for p in NwsObservationMetadata["hourly"]["data"]}
    assert nws["windspeed"] == "wind_speed_last_2min"
    assert nws["winddirection"] == "wind_direction_last_2min"
    assert nws["windgust"] == "wind_gust_max_last_10min"
    eccc = {p.name_original: p.name for p in EcccObservationMetadata["hourly"]["data"]}
    assert eccc["wind_direction"] == "wind_direction_last_2min"
    assert eccc["wind_speed"] == "wind_speed"
    fmi = {p.name_original: p.name for p in FmiObservationMetadata["hourly"]["data"]}
    assert fmi["wg_10min"] == "wind_gust_max_last_10min"
    metoffice = {p.name_original: p.name for p in MetOfficeObservationMetadata["hourly"]["weather"]}
    assert metoffice["q10mnt_mxgst_spd"] == "wind_gust_max_last_10min"
    # the hourly weather wind says no window of its own (the WM page says the SYNOP and METAR winds are kept here,
    # which no data could be checked against without a CEDA login), and the whole-hour gust of the wind table is plain
    assert metoffice["wind_speed"] == "wind_speed"
    assert metoffice["wind_direction"] == "wind_direction"
    metoffice_wind = {p.name_original: p.name for p in MetOfficeObservationMetadata["hourly"]["wind"]}
    assert metoffice_wind["max_gust_speed"] == "wind_gust_max"


def test_dwd_road_wind_keeps_the_names_of_its_interval() -> None:
    """DWD road wind has no `_last_10min` name: the template's averaging period is not one for the dataset (GH-2838).

    The BUFR template of the road messages puts a time significance and a period before the wind: of the 23 station
    groups read on 2026-10-15, FN, ER, HL, HV, JO, KA, KO, MC, NI, RH, RP and SD say a mean over the last 10 minutes,
    HJ, KK and SH a mean over 15 (and some subsets of KK and SH none), and DD, JA, KM, LH, ND, RB, SP and WW a time
    averaged value over a period of 0. The dataset merges the groups under one name, so none of the three can
    state the window of every row.
    """
    road = {p.name_original: p.name for p in DwdRoadMetadata["15_minutes"]["data"]}
    assert road["windSpeed"] == "wind_speed"
    assert road["windDirection"] == "wind_direction"
    assert road["maximumWindGustSpeed"] == "wind_gust_max"


def test_pppp_is_sea_level_pressure_and_the_altimeter_setting_is_not() -> None:
    """MOSMIX and DMO `pppp` are `pressure_air_sea_level`; NWS `barometricpressure` is `pressure_air_site_reduced`.

    DWD's "Surface pressure, reduced" reads 1022.6 hPa at Hamburg (16 m) and 1027.2 at Munich (515 m) in the
    MOSMIX_L run of 13 October 2026, 04 UTC, where Munich's own pressure at 515 m would be tens of hPa lower, and
    it follows the sea-level pressure of the POI reports of the same hours (GH-2842). The NWS
    endpoint's `barometricPressure` is the altimeter setting of the METAR (A#### x 33.86389 Pa, KATL at 315 m reads
    101829 Pa), reduced with the standard atmosphere; its `seaLevelPressure` holds the name `pppp` has elsewhere,
    so it takes `pressure_air_site_reduced`, as `noaa/ghcn`'s `altimeter` does (GH-2840).
    """
    for metadata, datasets in ((DwdMosmixMetadata, ("small", "large")), (DwdDmoMetadata, ("icon", "icon_eu"))):
        for dataset in datasets:
            names = {p.name_original: p.name for p in metadata["hourly"][dataset]}
            assert names["pppp"] == "pressure_air_sea_level"
            assert "pressure_air_site_reduced" not in names.values()
    nws = {p.name_original: p.name for p in NwsObservationMetadata["hourly"]["data"]}
    assert nws["barometricpressure"] == "pressure_air_site_reduced"
    assert nws["sealevelpressure"] == "pressure_air_sea_level"
    assert "altimeter setting" in PARAMETERS["pressure_air_site_reduced"].description


def test_the_renamed_names_of_the_audit_are_each_a_row() -> None:
    """GH-2843 to GH-2847: the rows the audit of GH-2614 renamed, each by the source's own field."""
    mosmix = {p.name_original: p.name for p in DwdMosmixMetadata["hourly"]["large"]}
    # RRad1, "Global irradiance within the last hour" in %, never exceeds 80 and follows the clearness index
    assert mosmix["rrad1"] == "radiation_global_relative_last_1h"
    assert "probability_radiation_global_last_1h" not in PARAMETERS
    poi = {p.name_original: p.name for p in DwdPoiMetadata["hourly"]["data"]}
    assert poi["past_weather_1"] == "weather_past"
    assert poi["past_weather_2"] == "weather_secondary_past"
    assert "weather_last_3h" not in PARAMETERS
    assert "weather_secondary_last_3h" not in PARAMETERS
    swsmos = {p.name_original: p.name for p in DwdSwsmosMetadata["hourly"]["data"]}
    assert swsmos["RR6"] == "precipitation_amount_liquid_last_6h"
    assert swsmos["RRL1c"] == "precipitation_amount_liquid"
    for resolution in ("10_minutes", "hourly", "daily"):
        rmi = {p.name_original: p.name for p in RmiObservationMetadata[resolution]["data"]}
        assert rmi["temp_grass_pt100_avg"] == "temperature_surface_mean"
        assert "temperature_air_mean_0_05m" not in rmi.values()
    swiss = {p.name_original: p.name for p in MeteoswissObservationMetadata["daily"]["data"]}
    assert swiss["erefaod0"] == "evapotranspiration_potential_grass_fao"
    derived = {p.name_original: p.name for p in DwdDerivedMetadata["daily"]["soil"]}
    assert derived["vpgfao"] == "evapotranspiration_potential_grass_fao"
    assert derived["vpgh"] == "evapotranspiration_potential_grass_haude"
    # the monthly totals of the same fields were never windowed
    monthly = {p.name_original: p.name for p in DwdDerivedMetadata["monthly"]["soil"]}
    assert monthly["summe von vpgfao"] == "evapotranspiration_potential_grass_fao"
    assert monthly["summe von vpgh"] == "evapotranspiration_potential_grass_haude"


def test_the_metar_precipitation_group_is_named_for_the_report_it_is() -> None:
    """GHCNh `precipitation` and NWS `precipitationLastHour` are the amount since the last routine report (GH-2841).

    The group of a METAR is a running total: a routine report holds the whole hour, a SPECI the part that had fallen
    when it was filed. Neither is named `precipitation_amount`, which every other hourly dataset reads as the amount
    of its own interval, and `precipitation_amount` stays the name in GHCN daily.
    """
    name = "precipitation_amount_since_last_routine_report"
    ghcn = {p.name_original: p for p in NoaaGhcnMetadata["hourly"]["data"]}
    nws = {p.name_original: p for p in NwsObservationMetadata["hourly"]["data"]}
    assert ghcn["precipitation"].name == name
    assert nws["precipitationlasthour"].name == name
    assert name in PARAMETERS
    for parameter in (ghcn["precipitation"], nws["precipitationlasthour"]):
        assert "running total" in parameter.description
    assert nws["precipitationlast3hours"].name == "precipitation_amount_last_3h"
    assert {p.name_original: p.name for p in NoaaGhcnMetadata["daily"]["data"]}["prcp"] == "precipitation_amount"


def test_dwd_poi_and_aemet_hourly_and_dwd_synoptic_wind_name_their_ten_minutes() -> None:
    """The rows GH-2697 names: DWD wind_synoptic `ff`, DWD POI and AEMET hourly `vv` / `dv`.

    DWD wind_synoptic `dd` stays `wind_direction`: the sheet and `Metadaten_Parameter_*.txt` call it
    "Windrichtung" and state no window, unlike `FF` ("10-Min-Mittel der Windgeschwindigkeit").
    """
    synoptic = {p.name_original: p.name for p in DwdObservationMetadata["hourly"]["wind_synoptic"]}
    assert synoptic["ff"] == "wind_speed_last_10min"
    assert synoptic["dd"] == "wind_direction"
    # the sibling dataset's sheet says "hourly mean"
    hourly = {p.name_original: p.name for p in DwdObservationMetadata["hourly"]["wind"]}
    assert hourly["f"] == "wind_speed"
    assert hourly["d"] == "wind_direction"
    poi = {p.name_original: p.name for p in DwdPoiMetadata["hourly"]["data"]}
    assert poi["mean_wind_speed_during last_10_min_at_10_meters_above_ground"] == "wind_speed_last_10min"
    assert poi["mean_wind_direction_during_last_10 min_at_10_meters_above_ground"] == "wind_direction_last_10min"
    aemet = {p.name_original: p.name for p in AemetObservationMetadata["hourly"]["data"]}
    assert aemet["vv"] == "wind_speed_last_10min"
    assert aemet["dv"] == "wind_direction_last_10min"
    # the daily mean is the day's, whatever the readings it is made of
    assert {p.name_original: p.name for p in AemetObservationMetadata["daily"]["data"]}["velmedia"] == "wind_speed"


def test_fmi_metno_and_smhi_hourly_wind_name_their_ten_minutes() -> None:
    """The rows GH-2707 names: FMI `ws_10min` / `wd_10min`, MET Norway `wind_speed` / `wind_from_direction`, SMHI.

    Their daily and monthly (MET Norway) and 1-minute (SMHI `47` / `48`) siblings are the mean of their own
    interval and keep the plain names.
    """
    fmi = {p.name_original: p.name for p in FmiObservationMetadata["hourly"]["data"]}
    assert fmi["ws_10min"] == "wind_speed_last_10min"
    assert fmi["wd_10min"] == "wind_direction_last_10min"
    metno = {p.name_original: p.name for p in MetnoFrostMetadata["hourly"]["data"]}
    assert metno["wind_speed"] == "wind_speed_last_10min"
    assert metno["wind_from_direction"] == "wind_direction_last_10min"
    assert {p.name_original: p.name for p in MetnoFrostMetadata["daily"]["data"]}[
        "mean(wind_speed P1D)"
    ] == "wind_speed"
    smhi = {p.name_original: p.name for p in SmhiObservationMetadata["hourly"]["data"]}
    assert smhi["4"] == "wind_speed_last_10min"
    assert smhi["3"] == "wind_direction_last_10min"
    one_minute = {p.name_original: p.name for p in SmhiObservationMetadata["1_minute"]["data"]}
    assert one_minute["47"] == "wind_speed"
    assert one_minute["48"] == "wind_direction"


def test_meteofrance_hourly_wind_names_its_ten_minutes() -> None:
    """The rows GH-2707 names: Météo-France `FF` and, with it, `DD`.

    `FF` is the "force du vent moyenné sur 10 mn"; `DD`, "direction de FF", states no window of its own, so it
    moves with `FF` and the speed and the direction of the dataset do not end up under mismatched names. The
    daily and monthly `FFM` are a mean of the day's or month's values and keep `wind_speed`.
    """
    hourly = {p.name_original: p.name for p in MeteoFranceObservationMetadata["hourly"]["core"]}
    assert hourly["FF"] == "wind_speed_last_10min"
    assert hourly["DD"] == "wind_direction_last_10min"
    assert {p.name_original: p.name for p in MeteoFranceObservationMetadata["daily"]["core"]}["FFM"] == "wind_speed"
    assert {p.name_original: p.name for p in MeteoFranceObservationMetadata["monthly"]["data"]}["FFM"] == "wind_speed"


def test_meteofrance_synop_wind_names_its_ten_minutes() -> None:
    """The rows GH-2733 names: SYNOP `dd` and `ff`, "direction du vent moyen 10 min" and "vitesse du vent moyen 10 min".

    The sheet states the 10 minutes for both, and the files agree: `dd` equals the hourly `DD` and `ff` the hourly
    `FF` cut to the integer at the same stamp. The gust `raf10`, "rafales sur les 10 dernières minutes", is
    no mean, and is `wind_gust_max_last_10min` (GH-2836).
    """
    subdaily = {p.name_original: p.name for p in MeteoFranceSynopMetadata["subdaily"]["data"]}
    assert subdaily["dd"] == "wind_direction_last_10min"
    assert subdaily["ff"] == "wind_speed_last_10min"
    assert subdaily["raf10"] == "wind_gust_max_last_10min"


def test_knmi_hourly_wind_direction_names_its_ten_minutes() -> None:
    """The row GH-2835 names: KNMI hourly `DD`.

    The NetCDF says "Past 10 minute mean wind direction, representative for 10 meters" and the legacy hourly
    file "Mean wind direction (in degrees) for the 10-minute period preceding the observation time stamp"; the
    hourly mean speed `FH` ("Hourly mean wind speed") keeps `wind_speed`. The 10-minute `dd` is the mean of its
    own interval and keeps `wind_direction`.
    """
    hourly = {p.name_original: p for p in KnmiObservationMetadata["hourly"]["data"]}
    assert hourly["DD"].name == "wind_direction_last_10min"
    assert "10 minute mean wind direction" in hourly["DD"].description
    assert hourly["FH"].name == "wind_speed"
    assert {p.name_original: p.name for p in KnmiObservationMetadata["10_minutes"]["data"]}["dd"] == "wind_direction"


def test_meteofrance_hourly_fxy_is_the_highest_ten_minute_mean_not_a_gust() -> None:
    """The row GH-2834 names: the hourly `FXY`, "valeur maximale de FF dans l'heure", FF being the 10-minute mean.

    The hour's highest 10-minute mean is no gust: in the hourly files of department 31 (2020 to 2026) `FXY` is
    at least `FF` in 99.9993 % of the rows and its mean (3.69 m/s) lies between that of `FF` (2.91 m/s) and those
    of the 3-second gust `FXI3S` (5.61 m/s) and the instantaneous gust `FXI` (6.03 m/s). The hourly gusts `FXI` and
    `FXI3S` stay unmapped; `DXY`, "direction de FXY", is the direction of that mean and no gust's, no canonical
    name says so, and it is not read (GH-2836). The daily `FXI` is a gust and keeps its name.
    """
    hourly = {p.name_original: p.name for p in MeteoFranceObservationMetadata["hourly"]["core"]}
    assert hourly["FXY"] == "wind_speed_rolling_mean_max"
    assert "DXY" not in hourly
    assert "wind_direction_gust_max" not in hourly.values()
    assert "FXI" not in hourly
    assert "FXI3S" not in hourly
    assert "wind_gust_max" not in hourly.values()
    assert {p.name_original: p.name for p in MeteoFranceObservationMetadata["daily"]["core"]}["FXI"] == "wind_gust_max"


def test_the_wind_mean_window_regex_reads_the_sources_wording() -> None:
    """The wordings of a mean over a window match; a mean of a whole interval and a window equal to it do not."""
    for evidence, resolution in (
        ('10-minute mean of the wind speed (DWD: "10-Min-Mittel der Windgeschwindigkeit"). ff', "hourly"),
        ("Mean wind speed over the last 10 minutes, at 10 m above ground.", "hourly"),
        ("Mean wind direction over the 10 minutes preceding the time given by 'fint' (degrees). dv", "hourly"),
        (
            "Mean wind speed, the scalar mean of the samples taken every 1 second over the 10 minutes preceding",
            "hourly",
        ),
        ("Wind speed. Mean over 10 minutes, once per hour. 4", "hourly"),
        ("Wind force averaged over 10 minutes, measured at 10 m. FF", "hourly"),
        ("Speed of the mean wind over 10 minutes, in whole m/s (the mean cut to the integer). ff", "subdaily"),
        ("Mean wind direction over the last ten minutes before the observation time.", "hourly"),
        ("Past 10 minute mean wind direction, representative for 10 meters. DD", "hourly"),
        ("Wind speed. One minute mean, every minute.", "10_minutes"),
        ("wind speed, the 2-minute average of the ASOS", "hourly"),
        ("wind direction, the average of the two minutes ending at the time of observation", "hourly"),
    ):
        assert _states_a_shorter_wind_mean(evidence, resolution), evidence
    for evidence, resolution in (
        ("Mean wind direction during the previous 10 minutes. dd_10", "10_minutes"),
        ("Wind speed scalar; ten minutes mean in m/s fkl010z0", "10_minutes"),
        ("Wind speed. One minute mean, every minute. 47", "1_minute"),
        (
            "Mean wind speed, the average of the six 10-minute intervals of the previous hour. windgeschwindigkeit",
            "hourly",
        ),
        ("Wind speed scalar; hourly mean in m/s fkl010h0", "hourly"),
        ("Mean wind speed. f", "hourly"),
        ("Daily mean of the wind force averaged over 10 minutes, at 10 m. FFM", "daily"),
        ("Monthly mean of the daily mean wind force averaged over 10 minutes (FFM), at 10 m. FFM", "monthly"),
        ('Wind direction (DWD: "Windrichtung uml.,windstill DD=00"). dd', "hourly"),
    ):
        assert not _states_a_shorter_wind_mean(evidence, resolution), evidence


def test_the_wind_mean_window_regex_stays_within_a_sentence_and_a_whole_hour() -> None:
    """A window in the next sentence is not the mean's, and the singular "interval" is a window."""
    assert not _states_a_shorter_wind_mean("Mean wind speed. Reported every 10 minutes.", "hourly")
    assert _states_a_shorter_wind_mean("Mean wind speed of the 10-minute interval before the full hour.", "hourly")
    assert not _TEN_MINUTES.search("Maximum 10 minimum")
