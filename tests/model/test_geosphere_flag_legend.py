# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The legend lists the q21 codes of GeoSphere's `<parameter>_flag` in GeoSphere's words (GH-4480)."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from tests.ui.test_restapi import _values_result_of_shape
from wetterdienst.model.quality_legend import quality_legend, source_flag_note
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest
from wetterdienst.ui.response_metadata import response_metadata

#: `code_lists["q21"]` of the metadata of klima-v2-10min, -1h, -1d and -1m, the same four times (read 2026-11-26)
Q21 = [
    (None, "undefiniert"),
    (0, "ungeprüfte Daten"),
    (10, "automatisch geprüft"),
    (11, "automatisch geprüft (verändert)"),
    (12, "automatisch geprüft (original)"),
    (20, "manuell geprüft (unbekannt)"),
    (21, "manuell geprüft (verändert)"),
    (22, "manuell geprüft (original)"),
]


def _plain() -> dict:
    plain = [kind for kind in quality_legend("geosphere", "observation") if kind.kind is None]
    assert len(plain) == 1
    return plain[0].model_dump()


def test_the_legend_lists_the_codes_of_q21_in_geospheres_words() -> None:
    """Every code of q21 but the null one is a code of the flag, with the words the metadata gives it."""
    plain = _plain()
    assert [(code["code"], code["meaning"]) for code in plain["codes"]] == [
        (str(key), value) for key, value in Q21 if key is not None
    ]
    # the null code is no token (a flag that is null is left out), and the legend says so
    assert "undefiniert" in plain["meaning"]
    assert "left out" in plain["meaning"]


def test_the_legend_names_the_metadata_that_defines_the_codes() -> None:
    """The URL is the metadata of a klima-v2 dataset, whose `code_lists` hold q21."""
    assert _plain()["documentation"] == (
        "https://dataset.api.hub.geosphere.at/v1/station/historical/klima-v2-1d/metadata"
    )


def test_the_legend_is_the_flag_first_and_then_the_tokens_of_the_core() -> None:
    """As for every network with a flag of its source: it first, `raw` last."""
    assert [kind.kind for kind in quality_legend("geosphere", "observation")] == [None, "suspect", "rejected", "raw"]
    assert source_flag_note("geosphere", "observation") is None


def test_a_with_metadata_answer_carries_the_legend_and_no_note() -> None:
    """`metadata.quality` of a GeoSphere answer lists the codes and does not say that the library carries no flag."""
    request = GeosphereObservationRequest(parameters=[("daily", "data", "temperature_air_max_2m")])
    stations = replace(_values_result_of_shape("long").stations, request=request)
    metadata = response_metadata(
        stations, SimpleNamespace(provider="geosphere", network="observation", with_metadata=True)
    )
    assert metadata.quality is not None
    quality = metadata.quality.model_dump()
    assert quality["source_flag_note"] is None
    plain = quality["legend"][0]
    assert plain["kind"] is None
    assert {code["code"] for code in plain["codes"]} == {"0", "10", "11", "12", "20", "21", "22"}
