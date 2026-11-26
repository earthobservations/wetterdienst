# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The error of an unknown resolution, dataset or parameter name names the closest names, in 1,000 characters (GH-4466).

fastmcp cuts the text of an error at 1,000 characters, and the error of an unknown parameter of `noaa/ghcn` was 8,148
characters long: the first names of an alphabetical list, which are rarely the one that was meant. A model that wrote
the form of another provider (`daily/climate_summary/temperature_air_mean_2m` at SMHI, whose dataset is `data`) read
"Available datasets: data" and wrote the second try wrong as well.
"""

import re

import pytest

from wetterdienst.api import Wetterdienst
from wetterdienst.exceptions import InvalidParameterError, MetadataNotFoundError
from wetterdienst.model.metadata import (
    UNKNOWN_NAME_LIMIT,
    parse_parameters,
)
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.provider.noaa.ghcn.metadata import NoaaGhcnMetadata
from wetterdienst.provider.smhi.observation.metadata import SmhiObservationMetadata

#: what a request adds to the text where other parameters of it resolve (`TimeseriesRequest.__post_init__`)
ON_UNKNOWN_SUFFIX = ". Pass on_unknown='warn' to skip these and read the others."


def _error(parameters: str | list[str], metadata: object) -> str:
    with pytest.raises(InvalidParameterError) as raised:
        parse_parameters(parameters, metadata)  # ty: ignore[invalid-argument-type]
    return str(raised.value)


def _listed(text: str) -> list[str]:
    """Give the names an error lists, whole (`Available parameters: ...`) or cut (`Closest parameters: ...`)."""
    listed = re.split(r"(?:Available|Closest) (?:parameters|datasets|resolutions): ", text, maxsplit=1)[1]
    return [name.split("/")[0] for name in listed.split(" (", 1)[0].split(", ")]


def _timeseries_networks() -> list[tuple[str, str]]:
    return [
        (provider, network)
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
    ]


def _probes(metadata: object) -> list[str]:
    """Name what a caller gets wrong in every resolution and dataset: the name, the dataset, the resolution.

    The parameters that are probed are the two with the longest names of a dataset, as they take most of the text:
    a probe of every parameter of every network is 10,000 texts, which says no more.
    """
    probes = ["zzz/zzz", "zzz/zzz/zzz"]
    for resolution in metadata.resolutions:  # ty: ignore[unresolved-attribute]
        probes.append(f"{resolution.name}/zzz")
        probes.append(f"{resolution.name}/zzz/zzz")
        for dataset in resolution.datasets:
            probes += [f"{resolution.name}/{dataset.name}x", f"{resolution.name}/{dataset.name}/zzz"]
            longest = sorted(dataset.parameters, key=lambda p: -(len(p.name) + len(p.name_original)))[:2]
            for parameter in longest:
                probes += [
                    # a typo, the same name asked for in the source's own form, and the parameter in a dataset the
                    # resolution does not have, which every dataset that has it is offered for
                    f"{resolution.name}/{dataset.name}/{parameter.name}x",
                    f"{resolution.name}/{dataset.name}/{parameter.name_original}x",
                    f"{resolution.name}/{dataset.name}x/{parameter.name}",
                    f"{resolution.name}/zzz/{parameter.name_original}",
                ]
    return probes


def _several(metadata: object) -> list[list[str]]:
    """Name several wrong names in one request, in the biggest dataset of every resolution: 10 of them, and 4 typos."""
    probes = []
    for resolution in metadata.resolutions:  # ty: ignore[unresolved-attribute]
        dataset = max(resolution.datasets, key=lambda d: sum(len(p.name) + len(p.name_original) for p in d.parameters))
        probes.append([f"{resolution.name}/{dataset.name}/z{n}" for n in range(10)])
        longest = sorted(dataset.parameters, key=lambda p: -(len(p.name) + len(p.name_original)))[:4]
        probes.append([f"{resolution.name}/{dataset.name}/{p.name}x" for p in longest])
        probes.append([f"{resolution.name}/{dataset.name}x/{p.name}" for p in longest])
    return probes


def _texts_of_network(request: type) -> list[tuple[str, str]]:
    """Give every text an unknown name of the network is told in, with what was asked, offline from the metadata."""
    metadata = request.metadata  # ty: ignore[unresolved-attribute]
    texts = []
    for probe in [*_probes(metadata), *_several(metadata)]:
        try:
            parse_parameters(probe, metadata)
        except InvalidParameterError as e:
            # the text of a request that has other parameters, which adds the hint to pass `on_unknown`
            texts.append((str(probe), f"{e}{ON_UNKNOWN_SUFFIX}"))
    for kwargs in ({"resolutions": "zzz"}, {"datasets": "zzz"}, {"datasets": "zzz", "resolutions": "zzz"}):
        try:
            request.discover(**kwargs)  # ty: ignore[unresolved-attribute]
        except MetadataNotFoundError as e:
            texts.append((f"discover({kwargs})", str(e)))
    return texts


def test_every_unknown_name_of_every_network_is_told_in_under_1000_characters() -> None:
    """The longest text of an unknown name or of several, on every provider and network."""
    longest: tuple[int, str, str] = (0, "", "")
    measured = 0
    for provider, network in _timeseries_networks():
        try:
            request = Wetterdienst.resolve(provider, network)
        except ImportError:
            continue
        for asked, text in _texts_of_network(request):
            measured += 1
            longest = max(longest, (len(text), f"{provider}/{network}: {asked}", text), key=lambda found: found[0])
    assert measured > 1000
    assert longest[0] < UNKNOWN_NAME_LIMIT, longest


def test_the_suffix_the_limit_allows_for_is_the_one_a_request_adds() -> None:
    """A request with other parameters that resolve ends the text with `ON_UNKNOWN_SUFFIX`, which the limit counts."""
    with pytest.raises(InvalidParameterError) as raised:
        DwdObservationRequest(parameters=["daily/climate_summary/temperature_air_mean_2m", "daily/kl/zzz"])
    text = str(raised.value)
    assert text.endswith(ON_UNKNOWN_SUFFIX)
    assert len(ON_UNKNOWN_SUFFIX) <= 65


def test_a_name_in_the_form_of_another_provider_is_answered_with_the_whole_corrected_string() -> None:
    """The four Stockholm runs of #4413 wrote DWD's form at SMHI, whose dataset is `data`."""
    text = _error("daily/climate_summary/temperature_air_mean_2m", SmhiObservationMetadata)
    assert text == (
        "daily/climate_summary/temperature_air_mean_2m not found in SmhiObservationMetadata: 'climate_summary'. "
        "Did you mean 'daily/data/temperature_air_mean_2m'? Available datasets: data"
    )


def test_the_whole_string_is_offered_for_a_parameter_the_dataset_does_not_have_but_a_sibling_does() -> None:
    """`daily/climate_summary` has no soil temperature: the dataset of the resolution that has it is named whole."""
    text = _error("daily/climate_summary/temperature_soil_mean_0_05m", DwdObservationMetadata)
    assert "'temperature_soil_mean_0_05m'. Did you mean 'daily/temperature_soil/temperature_soil_mean_0_05m'? " in text
    assert "Available parameters: temperature_air_min_0_05m/tgk" in text


def test_a_dataset_that_is_a_typo_is_answered_with_the_whole_string_of_the_datasets_that_have_the_parameter() -> None:
    """The datasets that have the parameter come first, in the order of how close their name is, both hint and list."""
    text = _error("daily/kll/precipitation_amount", DwdObservationMetadata)
    assert "Did you mean 'daily/climate_summary/precipitation_amount' or 'daily/precipitation_more/" in text
    assert "Available datasets: climate_summary, precipitation_more, solar, " in text


def test_the_whole_string_is_of_the_same_resolution_only() -> None:
    """A dataset of another resolution is no answer: it would read other values."""
    text = _error("hourly/climate_summary/precipitation_amount", DwdObservationMetadata)
    hint = text.split("Did you mean ", 1)[1].split("? ", 1)[0]
    offered = [name.strip("'") for name in hint.split(" or ")]
    assert offered == [
        "hourly/precipitation/precipitation_amount",
        "hourly/urban_precipitation/precipitation_amount",
    ]
    assert not any(name.startswith("daily/") for name in offered)


def test_mosmix_names_the_closest_parameters_and_how_many_there_are() -> None:
    """`hourly/large/zzz` was 5,011 characters, and the first names of an alphabetical list."""
    text = _error("hourly/large/temperatur_air_2m", DwdMosmixMetadata)
    assert len(text) < 700
    assert (
        "'temperatur_air_2m'. Did you mean 'temperature_air_2m'? Closest parameters: temperature_air_2m/ttt, " in text
    )
    names = text.split("Closest parameters: ", 1)[1].split(" (", 1)[0].split(", ")
    assert names[0].startswith("temperature_air")
    assert len(names) == 10
    total = len(DwdMosmixMetadata.hourly.large.parameters)
    assert text.endswith(f"({total} in all; `coverage` lists them all)")


def test_ghcn_names_the_closest_parameters_and_how_many_there_are() -> None:
    """`daily/data/zzz` was 8,148 characters."""
    text = _error("daily/data/temperature_air_max_2", NoaaGhcnMetadata)
    assert len(text) < 700
    names = text.split("Closest parameters: ", 1)[1].split(" (", 1)[0].split(", ")
    assert names[0].startswith("temperature_air_max_2m")
    total = len(list(NoaaGhcnMetadata.daily.data))
    assert text.endswith(f"({total} in all; `coverage` lists them all)")


@pytest.mark.parametrize(
    ("typo", "first"),
    [
        ("temperature_air_mean_2", "temperature_air_mean_2m"),
        ("temperatur_air_mean_2m", "temperature_air_mean_2m"),
        ("precipitaton_amount", "precipitation_amount"),
        ("wind_speed_mean_", "wind_speed_mean"),
        ("sunshine_duraton", "sunshine_duration"),
    ],
)
def test_a_typo_is_answered_with_the_name_it_is_closest_to_first(typo: str, first: str) -> None:
    """The names follow closest first, the one the hint names at their head, and the whole text is short."""
    text = _error(f"daily/kl/{typo}", DwdObservationMetadata)
    assert f"Did you mean '{first}'?" in text
    assert _listed(text)[0] == first
    assert len(text) < 600


def test_a_name_that_was_renamed_keeps_its_text_and_leads_the_names() -> None:
    """The rename texts are as they were: a client and a model read them."""
    text = _error("daily/kl/precipitation_height", DwdObservationMetadata)
    assert (
        "'precipitation_height'. It was renamed to 'precipitation_amount'. Available parameters: precipitation_amount/"
        in text
    )
    text = _error("hourly/temperature_air/temperature_air_mean_2m", DwdObservationMetadata)
    assert "It is named 'temperature_air_2m' here, a reading at one moment, not a mean." in text


def test_a_short_list_is_told_whole_closest_first() -> None:
    """Few names that fit are all of them, as they were, but in the order of the closeness."""
    text = _error("dayly/kl", DwdObservationMetadata)
    assert text.endswith(
        "Available resolutions: daily, subdaily, annual, hourly, monthly, 10_minutes, 1_minute, 5_minutes"
    )
    assert "'dayly'. Did you mean 'daily'?" in text


def test_the_closest_names_are_the_same_every_time() -> None:
    """Ties are broken by the name, so that the same wrong name is always told the same way."""
    first = _error("daily/data/zzz", NoaaGhcnMetadata)
    assert [_error("daily/data/zzz", NoaaGhcnMetadata) for _ in range(3)] == [first] * 3


def _fits(text: str) -> bool:
    """Whether the text of a request with other parameters that resolve is read whole through a tool."""
    return len(text) + len(ON_UNKNOWN_SUFFIX) < UNKNOWN_NAME_LIMIT


def test_several_unknown_names_share_the_limit_and_lose_their_lists_first() -> None:
    """Four realistic names at mosmix were 1,043 characters: the lists go, the hints stay, `coverage` is said once."""
    names = ["temperatur_air_2m", "wind_sped", "precip", "cloud_cover"]
    text = _error([f"hourly/large/{name}" for name in names], DwdMosmixMetadata)
    assert _fits(text)
    for name in names:
        assert f"hourly/large/{name} not found in DwdMosmixMetadata: '{name}'." in text
    assert "Did you mean 'temperature_air_2m'?" in text
    assert "Closest" not in text
    assert text.endswith("; `coverage` lists all the names")
    assert text.count("`coverage`") == 1


def test_five_old_names_of_a_dataset_are_told_each_with_its_rename() -> None:
    """Five old `daily/kl` names were 1,399 characters."""
    names = ["precipitation_height", "temperature_air_mean_200", "wind_speed", "sunshine", "pressure"]
    text = _error([f"daily/kl/{name}" for name in names], DwdObservationMetadata)
    assert _fits(text)
    assert "It was renamed to 'precipitation_amount'." in text
    assert "It was renamed to 'wind_speed_mean' in this dataset." in text
    assert "Available" not in text


def test_four_wrong_datasets_with_a_parameter_each_keep_their_whole_strings() -> None:
    """Four `hourly/temperature/...` were 1,348 characters: the second whole string of a hint goes, the first stays."""
    names = ["temperature_air_2m", "humidity_relative", "temperature_air_mean_2m", "pressure_air_site"]
    text = _error([f"hourly/temperature/{name}" for name in names], DwdObservationMetadata)
    assert _fits(text)
    assert "Did you mean 'hourly/temperature_air/temperature_air_2m'" in text
    assert "Available" not in text


def test_ten_wrong_names_keep_the_first_problems_and_count_the_others() -> None:
    """Where even the hints do not fit, the first problems stay, with how many more there are (10 names were 1,913)."""
    text = _error([f"hourly/large/z{n}" for n in range(30)], DwdMosmixMetadata)
    assert _fits(text)
    assert "hourly/large/z0 not found in DwdMosmixMetadata: 'z0'." in text
    assert re.search(r"; and [1-9]\d* more unknown names; `coverage` lists all the names$", text)
    shown = len(re.findall(r"hourly/large/z\d+ not found", text))
    assert text.count(" more unknown names") == 1
    assert f"and {30 - shown} more unknown names" in text
    assert shown >= 5


def test_unknown_names_that_fit_keep_their_lists() -> None:
    """Two names of a short dataset are told as one is."""
    text = _error(["daily/kl/zzz", "daily/kl/yyy"], DwdObservationMetadata)
    assert text.count("Available parameters:") == 2
    assert "`coverage` lists all the names" not in text


def test_a_dataset_that_is_unknown_to_coverage_is_told_as_a_parameter_is() -> None:
    """`discover()` (`coverage` on every surface) lists the closest datasets, not the 40 there are."""
    with pytest.raises(MetadataNotFoundError) as raised:
        DwdObservationRequest.discover(datasets="climate_sumary")
    text = str(raised.value)
    assert text.startswith(
        "Dataset 'climate_sumary' not found in DwdObservationMetadata. Did you mean 'climate_summary'?"
    )
    assert "Closest datasets: climate_summary, climate_indices, " in text
    assert text.endswith("`coverage` lists them all)")
    assert len(text) < 600


def test_the_name_the_hint_offers_leads_the_list_where_two_are_as_close() -> None:
    """`temperatur` is as close to the minimum as to the maximum: the hint takes one, and the list starts with it."""
    text = _error("daily/kl/temperatur", DwdObservationMetadata)
    hint = text.split("Did you mean '", 1)[1].split("'", 1)[0]
    assert _listed(text)[0] == hint


@pytest.mark.parametrize(
    ("provider", "network", "asked", "hint"),
    [
        # DWD's form at a provider whose dataset is `data`, with the name of before 1.0 or the mean of a reading
        ("smhi", "observation", "daily/kl/precipitation_height", "daily/data/precipitation_amount"),
        ("smhi", "observation", "hourly/climate_summary/temperature_air_mean_2m", "hourly/data/temperature_air_2m"),
        # the daily mean is `temperature_air_mean_minmax_2m` at ECCC
        (
            "eccc",
            "observation",
            "daily/climate_summary/temperature_air_mean_2m",
            "daily/data/temperature_air_mean_minmax_2m",
        ),
        # at DWD the hourly temperature is in a dataset of its own, and `climate_summary` is daily
        (
            "dwd",
            "observation",
            "hourly/climate_summary/temperature_air_mean_2m",
            "hourly/temperature_air/temperature_air_2m",
        ),
        # a parameter written in the place of the dataset
        ("smhi", "observation", "daily/temperature_air_mean_2m", "daily/data/temperature_air_mean_2m"),
        ("noaa", "ghcn", "daily/precipitation_amount", "daily/data/precipitation_amount"),
        ("dwd", "mosmix", "hourly/temperature_air_2m", "hourly/large/temperature_air_2m"),
        ("eccc", "observation", "daily/temperature_air_mean_2m", "daily/data/temperature_air_mean_minmax_2m"),
        ("dwd", "observation", "daily/temperature_air_mean_2m", "daily/climate_summary/temperature_air_mean_2m"),
    ],
)
def test_the_mistakes_of_the_transcripts_are_answered_with_the_whole_string(
    provider: str, network: str, asked: str, hint: str
) -> None:
    """The name another provider's form, an old name or a parameter in the dataset's place gets the string to write."""
    text = _error(asked, Wetterdienst.resolve(provider, network).metadata)
    offered = re.search(r"Did you mean ((?:'[^']+'(?: or )?)+)\?", text)
    assert offered, text
    assert f"'{hint}'" in offered.group(1).split(" or ")[0] or hint in offered.group(1), text


def test_a_dataset_slot_that_is_a_parameter_is_not_guessed_at_by_spelling() -> None:
    """`air_temperature` is an hourly dataset of DWD: `soil_temperature` is a spelling and no air temperature."""
    text = _error("daily/air_temperature", DwdObservationMetadata)
    assert "Did you mean" not in text


def test_the_names_of_the_quantity_come_before_names_of_one_word() -> None:
    """`visibility` and `weather` are one token, which any name may be taken for: they follow the temperatures."""
    names = _listed(_error("hourly/large/temperatur_air_2m", DwdMosmixMetadata))
    assert names[0] == "temperature_air_2m"
    assert "visibility" not in names[:6]
    assert all(name.startswith(("temperature", "error_absolute_temperature")) for name in names[:8]), names


def test_a_list_that_fits_is_told_whole() -> None:
    """The 14 parameters of `daily/kl` are 355 characters: no reason to cut them to 10."""
    text = _error("daily/kl/zzz", DwdObservationMetadata)
    assert len(_listed(text)) == 14
    assert "Closest" not in text


def test_a_dataset_is_listed_by_its_name_and_not_as_a_path() -> None:
    """The source's name of a dataset is a path (`climate_indices/kl`) that read as part of the name."""
    text = _error("daily/zzz", DwdObservationMetadata)
    assert "climate_summary/kl" not in text
    assert "climate_summary" in text


def test_a_second_whole_string_goes_before_a_problem_does() -> None:
    """Parameters written in the place of the dataset have two answers at mosmix (`large` and `small`)."""
    names = [
        p.name for p in DwdMosmixMetadata.hourly.small if p.name in {q.name for q in DwdMosmixMetadata.hourly.large}
    ]
    four = _error([f"hourly/{name}" for name in names[:4]], DwdMosmixMetadata)
    assert _fits(four)
    assert four.count("' or '") == 4
    five = _error([f"hourly/{name}" for name in names[:5]], DwdMosmixMetadata)
    assert _fits(five)
    assert "' or '" not in five
    assert "more unknown names" not in five
    assert all(f"'hourly/large/{name}'" in five for name in names[:5])
