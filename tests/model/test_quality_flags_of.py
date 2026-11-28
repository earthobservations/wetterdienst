# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A parameter belongs to the quality column before it in DWD's file, and `quality_flags_of` follows that (GH-4507)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wetterdienst.api import Wetterdienst
from wetterdienst.model.metadata import DatasetModel, is_quality_flag, quality_flags_of
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata

FILES: dict[str, list[dict]] = json.loads((Path(__file__).parent / "dwd_qn_file_headers.json").read_text("utf-8"))[
    "files"
]

#: the columns of a file that identify a row and are neither a quality column nor a parameter
_INDEX_COLUMNS = ("stations_id", "mess_datum", "mess_datum_beginn", "mess_datum_ende")


def _dataset(key: str) -> DatasetModel:
    resolution, name = key.split("/")
    return DwdObservationMetadata[resolution][name]


def _quality_column_of_each_parameter(key: str) -> dict[str, str]:
    """Read the files' headers as the parser does and tell each parameter's quality column (`name_original`)."""
    belongs: dict[str, str] = {}
    for file in FILES[key]:
        current = None
        for column in (c.lower() for c in file["columns"]):
            if column in _INDEX_COLUMNS:
                continue
            if column.startswith("qn"):
                # `DwdObservationParser` renames the QN of the extreme wind's two files after the file's gust
                current = column
                for gust in ("fx3", "fx6"):
                    if key == "subdaily/wind_extreme" and gust in file["file"].lower():
                        current = f"{column}_{gust[-1]}"
            else:
                assert current is not None, f"{column} comes before any quality column in {file['file']}"
                belongs[column] = current
    return belongs


@pytest.mark.parametrize("key", sorted(FILES))
def test_the_metadata_order_gives_the_quality_column_the_file_does(key: str) -> None:
    """For each parameter of each product with several quality columns the helper names the column the file has."""
    dataset = _dataset(key)
    in_the_file = _quality_column_of_each_parameter(key)
    parameters = [p for p in dataset.parameters if not is_quality_flag(p)]

    assert {p.name_original for p in parameters} == set(in_the_file), "the metadata declares the columns of the file"
    for parameter in parameters:
        assert [flag.name_original for flag in quality_flags_of(dataset, [parameter])] == [
            in_the_file[parameter.name_original]
        ], parameter.name_original
    # and the quality columns of the metadata are the ones of the file
    assert {flag.name_original for flag in dataset.parameters if is_quality_flag(flag)} == set(in_the_file.values())


@pytest.mark.parametrize(
    ("key", "parameter", "flags"),
    [
        ("daily/climate_summary", "wind_gust_max", ["qn_3"]),
        ("daily/climate_summary", "wind_speed_mean", ["qn_3"]),
        ("daily/climate_summary", "temperature_air_mean_2m", ["qn_4"]),
        ("subdaily/wind_extreme", "wind_gust_max_last_6h", ["qn_8_6"]),
        ("monthly/climate_summary", "precipitation_amount", ["qn_6"]),
        ("monthly/climate_summary", "temperature_air_mean_2m", ["qn_4"]),
    ],
)
def test_one_parameter_has_the_quality_column_before_it(key: str, parameter: str, flags: list[str]) -> None:
    """The wind of the daily summary has `qn_3`, its other parameters `qn_4`, each gust of the extreme wind its own."""
    dataset = _dataset(key)
    assert [f.name_original for f in quality_flags_of(dataset, [dataset[parameter]])] == flags


def test_several_parameters_have_each_quality_column_once_in_the_order_of_the_dataset() -> None:
    """Parameters that share a column give it once, and the columns come in the order of the dataset."""
    dataset = DwdObservationMetadata.daily.climate_summary
    read = [dataset.temperature_air_mean_2m, dataset.wind_gust_max, dataset.wind_speed_mean]
    assert [f.name_original for f in quality_flags_of(dataset, read)] == ["qn_3", "qn_4"]


def test_a_whole_dataset_has_all_its_quality_columns() -> None:
    """Without parameters, or with all of them, every column of the dataset."""
    dataset = DwdObservationMetadata.daily.climate_summary
    assert [f.name_original for f in quality_flags_of(dataset)] == ["qn_3", "qn_4"]
    assert [f.name_original for f in quality_flags_of(dataset, list(dataset))] == ["qn_3", "qn_4"]


def test_a_dataset_without_a_quality_column_has_none() -> None:
    """A network that has no source flag in a dataset lists none."""
    dataset = DwdMosmixMetadata.hourly.small
    assert [p for p in dataset.parameters if is_quality_flag(p)] == [], "the dataset has a quality column now"
    assert quality_flags_of(dataset, [next(iter(dataset))]) == []


def _datasets_with_quality_flags() -> list[tuple[str, DatasetModel]]:
    found = []
    for provider in Wetterdienst.get_provider_names():
        for network in Wetterdienst.get_network_names(provider):
            if Wetterdienst.is_standalone(provider, network):
                continue
            request = Wetterdienst.resolve(provider, network)
            for resolution in request.metadata:
                found.extend(
                    (f"{provider}/{network}/{resolution.name}/{dataset.name}", dataset)
                    for dataset in resolution
                    if any(is_quality_flag(p) for p in dataset.parameters)
                )
    return found


@pytest.mark.parametrize(
    ("key", "dataset"), _datasets_with_quality_flags(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_a_dataset_with_one_quality_column_has_it_for_every_parameter(key: str, dataset: DatasetModel) -> None:
    """The datasets of the other products and networks (dwd/derived's QN_952, the single QN) are told as before."""
    flags = [p for p in dataset.parameters if is_quality_flag(p)]
    if len(flags) > 1:
        pytest.skip("several quality columns: held to the files above")
    for parameter in dataset:
        assert quality_flags_of(dataset, [parameter]) == flags, key
