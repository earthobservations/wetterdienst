# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The ids of a Frost source: the WMO number padded from an integer, the WIGOS id, the first ICAO code (GH-4070).

Read live 2026-11-15 with the request of the catalogue (4,183 sources): `wmoId` an integer on 1,029 (4 digits on 863, 5
on 166, never 0), `wigosId` a text on 1,621, `icaoCodes` a list on 164 (one code on 163, two on one).
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl
import pytest

from tests.provider.metno.frost import catalogue_rows as frost_rows
from wetterdienst import Settings
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.provider.metno.frost.api import _source_ids
from wetterdienst.util.network import File


def _read(df: dict[str, list[Any]]) -> dict[str, list[Any]]:
    return _source_ids(pl.DataFrame(df)).select("wmo_id", "wigos_id", "icao_id").to_dict(as_series=False)


def test_a_wmo_id_that_is_an_integer_is_padded_to_five_digits() -> None:
    """Frost gives 1492 for 01492: the number loses its zero as an integer, and the padding puts it back."""
    ids = _read({"wmoId": [1492, 18700, 99, None]})
    assert ids["wmo_id"] == ["01492", "18700", "00099", None]


def test_a_wmo_id_that_is_digits_in_a_text_is_read_and_anything_else_is_null() -> None:
    """A text of digits is a number as well; 0, a decimal, a word and a number of six digits are none."""
    assert _read({"wmoId": ["01466", "1466", "0", "abc", "123456"]})["wmo_id"] == ["01466", "01466", None, None, None]
    assert _read({"wmoId": [0, 1492]})["wmo_id"] == [None, "01492"]
    assert _read({"wmoId": [1492.5]})["wmo_id"] == [None]


def test_an_icao_id_is_the_first_of_a_list_and_a_text_is_no_list() -> None:
    """`icaoCodes` is a list: the first code is read, and a column that is not a list is no ICAO code."""
    assert _read({"icaoCodes": [["ENGM"], ["ESNZ", "ESPC"], None]})["icao_id"] == ["ENGM", "ESNZ", None]
    assert _read({"icaoCodes": ["ENGM"]})["icao_id"] == [None]


def test_a_wigos_id_is_read_only_as_a_text_and_a_column_no_source_has_is_null() -> None:
    """The WSI is kept as written (the issuer is not read out of it); an absent column is null."""
    assert _read({"wigosId": ["0-20000-0-01492", None], "id": ["a", "b"]})["wigos_id"] == ["0-20000-0-01492", None]
    assert _read({"id": ["a"]}) == {"wmo_id": [None], "wigos_id": [None], "icao_id": [None]}


def test_the_sources_request_asks_for_the_ids() -> None:
    """The ids are in the answer only if the request names them in `fields`."""
    for name in ("wmoId", "wigosId", "icaoCodes"):
        assert name in MetnoFrostRequest._sources_url  # noqa: SLF001
        assert name not in MetnoFrostRequest._sources_url_without_ids  # noqa: SLF001


def test_a_400_for_the_ids_is_asked_again_without_them_and_warned_about(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Frost refuses a field it does not know with a 400 for the whole list: ask once more without the ids."""
    asked: list[str] = []
    # the answer to the list asked without the ids has none
    without_ids = {
        "data": [
            {key: value for key, value in source.items() if key not in ("wmoId", "wigosId", "icaoCodes")}
            for source in frost_rows.SOURCES["data"]
        ]
    }
    served = frost_rows.Upstream(monkeypatch, sources=without_ids)
    answer = frost_api.download_file

    def download_file(*, url: str, **kwargs: Any) -> File:  # noqa: ANN401
        asked.append(url)
        if frost_rows.is_sources_listing(url) and "wmoId" in url:
            return File(url=url, content=OSError("400 Bad Request"), status=400)
        return answer(url=url, **kwargs)

    monkeypatch.setattr(frost_api, "download_file", download_file)
    request = MetnoFrostRequest(
        parameters=[("hourly", "data")],
        settings=Settings(cache_disable=True, auth={"metno_frost": ("stub-client", "stub-secret")}),
    )
    with caplog.at_level(logging.WARNING, logger=frost_api.__name__):
        stations = request.all().df
    sources = [url for url in asked if frost_rows.is_sources_listing(url)]
    assert [("wmoId" in url) for url in sources] == [True, False]
    assert "asking again without them" in caplog.text
    assert stations.height > 0
    assert stations.get_column("wmo_id").null_count() == stations.height
    assert served.calls


def test_a_400_for_a_request_without_the_ids_is_not_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """The second request is no loop: a 400 of the list without the ids is the error it always was."""
    asked: list[str] = []

    def download_file(*, url: str, **_: Any) -> File:  # noqa: ANN401
        asked.append(url)
        return File(url=url, content=OSError("400 Bad Request"), status=400)

    monkeypatch.setattr(frost_api, "download_file", download_file)
    request = MetnoFrostRequest(
        parameters=[("hourly", "data")],
        settings=Settings(cache_disable=True, auth={"metno_frost": ("stub-client", "stub-secret")}),
    )
    with pytest.raises(Exception, match="400"):
        request.all()
    assert len(asked) == 2
