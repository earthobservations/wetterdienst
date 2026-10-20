# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The core adds ``resolution`` and ``dataset`` to the stations of a provider that has one catalogue (GH-2627)."""

from __future__ import annotations

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import ProviderContractError
from wetterdienst.model.request import add_resolution_and_dataset
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dwd.observation import DwdObservationRequest

PAIRS = [("daily", "climate_summary"), ("hourly", "temperature_air")]


def _catalogue() -> pl.DataFrame:
    return pl.DataFrame({"station_id": ["00001", "00002"], "name": ["A", "B"]})


def test_a_catalogue_without_identity_is_copied_once_per_dataset_in_the_order_of_the_pairs() -> None:
    """A station is a station of every requested dataset, and the copies follow the pairs."""
    result = add_resolution_and_dataset(_catalogue(), PAIRS, provider="TestRequest")

    assert result.columns == ["station_id", "name", "resolution", "dataset"]
    assert result.schema["resolution"] == pl.String
    assert result.schema["dataset"] == pl.String
    assert result.get_column("resolution").to_list() == ["daily", "daily", "hourly", "hourly"]
    assert result.get_column("dataset").to_list() == [
        "climate_summary",
        "climate_summary",
        "temperature_air",
        "temperature_air",
    ]
    assert result.get_column("station_id").to_list() == ["00001", "00002", "00001", "00002"]


def test_a_frame_that_carries_both_columns_is_left_alone() -> None:
    """A provider whose stations differ per dataset has said which row belongs where."""
    df = pl.DataFrame({"resolution": ["daily"], "dataset": ["climate_summary"], "station_id": ["00001"]})

    result = add_resolution_and_dataset(df, PAIRS, provider="TestRequest")

    assert_frame_equal(result, df)


@pytest.mark.parametrize("present", ["resolution", "dataset"])
def test_one_of_the_two_columns_without_the_other_is_a_contract_error(present: str) -> None:
    """The core cannot tell which half of a pair is missing, so it does not guess."""
    missing = "dataset" if present == "resolution" else "resolution"
    df = _catalogue().with_columns(pl.lit("x").alias(present))

    with pytest.raises(ProviderContractError, match=f"TestRequest returned stations without the column.*{missing}"):
        add_resolution_and_dataset(df, PAIRS, provider="TestRequest")


@pytest.mark.parametrize(
    "empty",
    [pl.DataFrame(), pl.DataFrame(schema={"station_id": pl.String}), pl.DataFrame(schema={"resolution": pl.String})],
    ids=["bare", "with a column", "one identity column"],
)
def test_a_frame_without_a_row_is_returned_as_it_is(empty: pl.DataFrame) -> None:
    """Tagging a column-less frame has one row on polars before 2.0, so a frame without a row is never tagged."""
    result = add_resolution_and_dataset(empty, PAIRS, provider="TestRequest")

    assert result.is_empty()
    assert result.columns == empty.columns


def test_a_request_without_datasets_has_no_stations() -> None:
    """There is no dataset for a station to be a station of."""
    assert add_resolution_and_dataset(_catalogue(), [], provider="TestRequest").is_empty()


def _all_with(monkeypatch: pytest.MonkeyPatch, df: pl.DataFrame, parameters: list[tuple[str, str]]) -> pl.DataFrame:
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: df.lazy())
    return DwdObservationRequest(parameters=parameters).all().df


def test_all_fans_a_catalogue_out_over_the_requested_datasets_each_once_in_request_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The datasets are the request's, deduplicated, in the order the parameters name them."""
    result = _all_with(
        monkeypatch,
        _catalogue(),
        [
            ("hourly", "temperature_air"),
            ("daily", "climate_summary"),
            ("hourly", "temperature_air"),
        ],
    )

    assert result.schema == STATIONS_SCHEMA
    assert result.select("resolution", "dataset", "station_id").rows() == [
        ("hourly", "temperature_air", "00001"),
        ("hourly", "temperature_air", "00002"),
        ("daily", "climate_summary", "00001"),
        ("daily", "climate_summary", "00002"),
    ]


def test_all_leaves_a_frame_with_the_columns_as_the_provider_wrote_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station of one dataset only stays a station of that one."""
    df = pl.DataFrame({"resolution": ["daily"], "dataset": ["climate_summary"], "station_id": ["00001"]})

    result = _all_with(monkeypatch, df, [("daily", "climate_summary"), ("hourly", "temperature_air")])

    assert result.select("resolution", "dataset", "station_id").rows() == [("daily", "climate_summary", "00001")]


@pytest.mark.parametrize("handed", [pl.DataFrame(), pl.DataFrame(schema={"station_id": pl.String})])
def test_all_answers_the_empty_stations_frame_for_a_catalogue_without_rows(
    monkeypatch: pytest.MonkeyPatch,
    handed: pl.DataFrame,
) -> None:
    """The catalogue of a provider that has no identity columns and no stations is not given a row by tagging."""
    result = _all_with(monkeypatch, handed, [("daily", "climate_summary")])

    assert result.is_empty()
    assert result.schema == STATIONS_SCHEMA
