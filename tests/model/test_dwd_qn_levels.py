# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The legend of `with_metadata` lists DWD's quality levels (QN) of the datasets read, in DWD's words (GH-4474)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.ui.test_restapi import _values_result_of_shape
from wetterdienst.model.dwd_qn_levels import DOCUMENTS, LEVELS, UNDOCUMENTED, qn_levels
from wetterdienst.model.metadata import is_quality_flag
from wetterdienst.model.quality_legend import LEGENDS, NO_SOURCE_FLAG, quality_legend, source_flag_note
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.ui.response_metadata import response_metadata

TRANSCRIPT = json.loads((Path(__file__).parent / "dwd_qn_documents.json").read_text(encoding="utf-8"))["documents"]


def _quality_of(parameters: list[tuple[str, str]]) -> dict:
    """Give `metadata.quality` of a `with_metadata` answer that reads the (resolution, dataset) pairs."""
    request = DwdObservationRequest(parameters=parameters)
    stations = replace(_values_result_of_shape("long").stations, request=request)
    metadata = response_metadata(stations, SimpleNamespace(provider="dwd", network="observation", with_metadata=True))
    assert metadata.quality is not None
    return metadata.quality.model_dump()


def _plain_kind(quality: dict) -> dict:
    return next(kind for kind in quality["legend"] if kind["kind"] is None)


def _levels(quality: dict) -> dict[str, str]:
    return {code["code"]: code["meaning"] for code in _plain_kind(quality)["codes"]}


def test_every_cited_list_is_the_transcript_of_the_document() -> None:
    """Each product's levels and wording are those of the document the legend cites for it."""
    assert set(TRANSCRIPT) >= {document.url for document in DOCUMENTS.values()}
    for dataset, document in DOCUMENTS.items():
        assert TRANSCRIPT[document.url] == [[level, LEVELS[level]] for level in document.levels], dataset


def test_the_transcript_holds_no_list_that_nothing_cites() -> None:
    """A document that is in the transcript is cited by the table, by DUETT or by the phenology legend."""
    cited = {document.url for document in DOCUMENTS.values()}
    cited |= {kind.documentation for kind in LEGENDS["dwd/derived"] + LEGENDS["dwd/phenology"] if kind.documentation}
    assert set(TRANSCRIPT) == cited


def test_the_levels_are_the_documented_set() -> None:
    """The table has the levels DWD lists in the hourly, daily and monthly descriptions and no other."""
    assert list(LEVELS) == ["1", "2", "3", "5", "7", "8", "9", "10"]
    listed = {level for pairs in TRANSCRIPT.values() for level, _ in pairs if len(level) < 3}
    assert listed == set(LEVELS)


def test_every_dataset_with_a_quality_level_is_documented_or_says_it_is_not() -> None:
    """A dataset added to `dwd/observation` takes a stand: DWD's description of its levels, or that DWD has none."""
    with_a_flag = {
        f"{resolution.name}/{dataset.name}"
        for resolution in DwdObservationMetadata
        for dataset in resolution
        if any(is_quality_flag(parameter) for parameter in dataset.parameters)
    }
    assert set(DOCUMENTS).isdisjoint(UNDOCUMENTED)
    assert set(DOCUMENTS) | set(UNDOCUMENTED) == with_a_flag


@pytest.mark.parametrize(
    ("dataset", "levels"),
    [
        (("daily", "climate_summary"), ["1", "2", "3", "5", "7", "8", "9", "10"]),
        (("hourly", "temperature_air"), ["1", "2", "3", "5", "7", "8", "9", "10"]),
        (("10_minutes", "temperature_air"), ["1", "2", "3"]),
        (("hourly", "urban_wind"), ["1", "2"]),
    ],
    ids=["daily", "hourly", "10-minute", "urban-hourly"],
)
def test_the_legend_lists_the_levels_of_the_product(dataset: tuple[str, str], levels: list[str]) -> None:
    """The plain flag of an answer lists the levels DWD lists for the product, with DWD's words and the document."""
    quality = _quality_of([dataset])
    plain = _plain_kind(quality)
    assert list(_levels(quality)) == levels
    assert _levels(quality) == {level: LEVELS[level] for level in levels}
    assert plain["documentation"] == DOCUMENTS["/".join(dataset)].url
    assert plain["documentation"].endswith("_en.pdf")
    assert quality["source_flag_note"] is None


def test_the_daily_levels_say_the_flag_value_nine_means_not_all_parameters_corrected() -> None:
    """The flag value `9` that no model could read in GH-4413 has DWD's meaning beside it."""
    assert _levels(_quality_of([("hourly", "temperature_air")]))["9"] == "not all parameters corrected"


def test_a_product_without_a_description_says_so_and_lists_no_level() -> None:
    """DWD publishes no description of the annual levels, so none is told, and the legend says why."""
    plain = _plain_kind(_quality_of([("annual", "climate_summary")]))
    assert plain["codes"] is None
    assert plain["documentation"] is None
    assert "DWD publishes no description of the levels of annual/climate_summary" in plain["meaning"]


def test_a_mixed_answer_lists_the_levels_it_has_and_names_the_dataset_without() -> None:
    """The levels of the described dataset are told, and the undescribed one is named, not given another's levels."""
    quality = _quality_of([("10_minutes", "temperature_air"), ("subdaily", "pressure")])
    assert list(_levels(quality)) == ["1", "2", "3"]
    assert "no description of the levels of subdaily/pressure" in _plain_kind(quality)["meaning"]


def test_the_levels_of_two_products_are_told_once() -> None:
    """A level that two products of the answer both list is one entry."""
    found = qn_levels(["daily/climate_summary", "hourly/temperature_air", "10_minutes/wind"])
    assert found.levels == list(LEVELS)
    assert len(found.urls) == 3


def test_the_legend_without_datasets_names_no_level() -> None:
    """The levels depend on the product, so a legend asked for the network alone tells none."""
    plain = next(kind for kind in quality_legend("dwd", "observation") if kind.kind is None)
    assert plain.codes is None


def test_the_legend_of_the_other_dwd_networks_with_a_level_is_dwds_wording() -> None:
    """The DUETT levels and the phenology levels are the lists of the documents that word them."""
    for network in ("derived", "phenology"):
        plain = next(kind for kind in quality_legend("dwd", network) if kind.kind is None)
        assert plain.documentation is not None
        assert [[code.code, code.meaning] for code in plain.codes or []] == TRANSCRIPT[plain.documentation]


@pytest.mark.parametrize("network", ["dwd/mosmix", "dwd/dmo", "fmi/observation", "knmi/observation", "wsv/pegel"])
def test_a_provider_without_a_flag_says_so(network: str) -> None:
    """Where the source publishes no quality flag the answer says so, instead of leaving the question open."""
    assert source_flag_note(*network.split("/")) == NO_SOURCE_FLAG
    assert "no quality flag" in NO_SOURCE_FLAG


def test_the_note_is_said_exactly_where_the_legend_has_no_flag_of_the_source() -> None:
    """A network has the note if and only if its legend has no plain kind, the source's own flag."""
    for network, legend in LEGENDS.items():
        has_flag = any(kind.kind is None for kind in legend)
        assert (source_flag_note(*network.split("/")) is None) is has_flag, network


@pytest.mark.parametrize(
    ("network", "codes"),
    [
        ("eaufrance/hubeau", {"0", "4", "8", "12", "16", "20", "30"}),
        ("metno/frost", {"0", "1", "2", "4", "5", "6", "7"}),
    ],
)
def test_a_provider_that_states_its_codes_lists_them_with_the_source(network: str, codes: set[str]) -> None:
    """Hub'Eau and Frost document a closed set of codes; the legend gives them and where they are written."""
    plain = next(kind for kind in quality_legend(*network.split("/")) if kind.kind is None)
    assert {code.code for code in plain.codes or []} == codes
    assert plain.documentation is not None
    assert plain.documentation.startswith("https://")
