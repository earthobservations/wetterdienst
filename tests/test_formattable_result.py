# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What every result can do, `FormattableResult`, and the formats of the history and the alerts result (GH-3449).

The history has `to_format` for JSON alone, and the alerts result takes the format in any case, `indent` as a number
or a flag, and `with_metadata`, as the other results do. Whether each of them satisfies the protocol is held here, at
run time; `tests/typed_caller.py` holds it for a type checker.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.model.test_history_result import _history
from tests.model.test_results import _every_result
from tests.provider.dwd.alerts.test_api import _URL, _make_zip
from tests.provider.dwd.alerts.test_parser import CAP_XML
from wetterdienst.exceptions import RequestError, UnknownFormatError
from wetterdienst.model import result as result_module
from wetterdienst.model.result import FormattableResult, HistoryResult
from wetterdienst.provider.dwd.alerts import (
    DwdWeatherAlertGranularity,
    DwdWeatherAlertLanguage,
    DwdWeatherAlertRequest,
    DwdWeatherAlertResult,
)
from wetterdienst.ui.response_metadata import alerts_metadata, metadata_to_dict

if TYPE_CHECKING:
    from collections.abc import Callable

_SNAPSHOT = dt.datetime(2026, 7, 26, 8, 0, tzinfo=ZoneInfo("UTC"))


def _alerts() -> DwdWeatherAlertResult:
    alerts = DwdWeatherAlertRequest._parse_archive(_make_zip(CAP_XML), _URL)  # noqa: SLF001
    df = DwdWeatherAlertRequest._build_dataframe(alerts)  # noqa: SLF001
    return DwdWeatherAlertResult(df, DwdWeatherAlertGranularity.COMMUNITY, DwdWeatherAlertLanguage.ENGLISH, _SNAPSHOT)


def _results() -> dict[str, Any]:
    results = _every_result()
    stations = results["stations"]
    results["history"] = HistoryResult(stations=stations, history=_history())  # ty: ignore[invalid-argument-type]
    results["alerts"] = _alerts()
    return results


_NAMES = ["stations", "values", "interpolated", "summarized", "history", "alerts"]


# --- the protocol -----------------------------------------------------------------------------------------------------


def test_the_protocol_is_public_where_the_results_are() -> None:
    """It is importable from `wetterdienst.model.result` and listed in its `__all__`, as the results are."""
    assert "FormattableResult" in result_module.__all__
    assert result_module.FormattableResult is FormattableResult


@pytest.mark.parametrize("name", _NAMES)
def test_every_result_satisfies_the_protocol(name: str) -> None:
    """The five results of the library and the alerts result have `to_dict`, `to_json` and `to_format`."""
    assert isinstance(_results()[name], FormattableResult)


@pytest.mark.parametrize("value", [object(), "json", {"to_dict": 1}, pl.DataFrame()])
def test_what_is_no_result_does_not_satisfy_the_protocol(value: object) -> None:
    """An object that lacks one of the three methods is no `FormattableResult`."""
    assert not isinstance(value, FormattableResult)


@pytest.mark.parametrize("name", _NAMES)
def test_every_result_answers_the_protocol_the_same_way(name: str) -> None:
    """A function written against the protocol gets a dictionary, JSON and a format by name from any result."""

    def write(result: FormattableResult) -> tuple[Any, str, str | bytes]:
        return result.to_dict(), result.to_json(), result.to_format("JSON")

    data, text, formatted = write(_results()[name])
    assert isinstance(text, str)
    assert isinstance(formatted, str)
    assert json.loads(text) == json.loads(formatted)
    assert isinstance(data, dict)


@pytest.mark.parametrize("name", _NAMES)
def test_every_result_puts_the_metadata_block_first_for_with_metadata(name: str) -> None:
    """`with_metadata=True` adds the block of the provider, the producer and the date, ahead of the data."""
    data = _results()[name].to_dict(with_metadata=True)
    assert next(iter(data)) == "metadata"
    assert list(data["metadata"]) == ["provider", "producer", "data_updated_at"]
    assert data["metadata"]["provider"]["name_english"] == "German Weather Service"
    assert "metadata" not in _results()[name].to_dict()


# --- the history ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["json", "JSON", "Json"])
def test_a_history_has_json_by_name_in_any_case(fmt: str) -> None:
    """`to_format("json")` is `to_json`, whatever the case of the name."""
    result = _results()["history"]
    assert result.to_format(fmt) == result.to_json()


def test_a_history_is_given_the_arguments_of_to_json_it_takes() -> None:
    """The one set of arguments of a caller is cut down to `to_json`'s, and `sections` is among them."""
    result = _results()["history"]
    everything = {"with_metadata": True, "with_stations": True, "sections": {"name"}, "indent": 2, "width": 3}
    assert result.to_format("json", **everything) == result.to_json(
        with_metadata=True, with_stations=True, sections={"name"}, indent=2
    )
    assert result.to_format("json", indent=False).count("\n") == 0


@pytest.mark.parametrize("fmt", ["csv", "geojson", "ndjson", "png", "xml"])
def test_a_history_has_no_other_format_and_names_json_as_the_only_one(fmt: str) -> None:
    """CSV is refused, as is every format the registry has: a history is no table, and has no features or chart."""
    result = _results()["history"]
    with pytest.raises(UnknownFormatError) as error:
        result.to_format(fmt)
    assert error.value.fmt == fmt
    assert error.value.supported == ("json",)
    assert str(error.value) == f"Unknown output format {fmt!r}: use one of json"
    assert isinstance(error.value, RequestError)
    for kind in (KeyError, ValueError):
        with pytest.raises(kind):
            result.to_format(fmt)


def test_a_history_refuses_an_argument_that_no_format_takes() -> None:
    """A typo is an error, as for the other results, and the message lists `sections` with the others."""
    result = _results()["history"]
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'sectoins'.*sections"):
        result.to_format("json", sectoins={"name"})


def test_a_history_names_the_format_before_the_argument() -> None:
    """A format that is unknown is the error, whatever else was passed."""
    with pytest.raises(UnknownFormatError):
        _results()["history"].to_format("csv", separator=";")


# --- the alerts result ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("fmt", "method"), [("json", "to_json"), ("geojson", "to_geojson"), ("csv", "to_csv")])
@pytest.mark.parametrize("spelling", [str.lower, str.upper, str.title])
def test_the_alerts_result_takes_the_format_in_any_case(fmt: str, method: str, spelling: Callable[[str], str]) -> None:
    """`to_format("JSON")` was refused, `to_format("json")` is what it was."""
    result = _alerts()
    assert result.to_format(spelling(fmt)) == getattr(result, method)()


@pytest.mark.parametrize("method", ["to_json", "to_geojson"])
@pytest.mark.parametrize(("indent", "expected"), [(True, 4), (4, 4), (2, 2), (False, None), (None, None), (0, 0)])
def test_the_alerts_indent_is_a_number_a_flag_or_nothing_as_for_the_other_results(
    method: str,
    indent: int | bool | None,  # noqa: FBT001
    expected: int | None,
) -> None:
    """`True` is 4 spaces, `False` and `None` one line and a number that many, in `to_format` and in the formatter."""
    result = _alerts()
    fmt = method.removeprefix("to_")
    data = json.loads(getattr(result, method)())
    written = json.dumps(data, indent=expected, ensure_ascii=False)
    assert getattr(result, method)(indent=indent) == written
    assert result.to_format(fmt, indent=indent) == written


def test_the_alerts_indent_defaults_to_one_line_as_it_did() -> None:
    """The default of the alerts result is unchanged: a compact document, where the other results indent by 4."""
    result = _alerts()
    assert "\n" not in result.to_json()
    assert "\n" not in result.to_format("json")
    assert result.to_json(True) == result.to_json(indent=4)  # noqa: FBT003
    assert result.to_geojson(True) == result.to_geojson(indent=4)  # noqa: FBT003


def test_the_alerts_with_metadata_is_the_block_of_the_other_results_first() -> None:
    """`provider`, `producer` and `data_updated_at`, the newest `sent` of the warnings, and before the alerts."""
    result = _alerts()
    for fmt in ("json", "JSON"):
        data = json.loads(result.to_format(fmt, with_metadata=True))
        assert list(data) == ["metadata", "snapshot", "alerts"]
        assert list(data["metadata"]) == ["provider", "producer", "data_updated_at"]
        assert data["metadata"]["data_updated_at"].startswith("2026-07-26T07:23:00")
        assert data["alerts"] == result.to_dict()["alerts"]
    assert json.loads(result.to_format("json")) == result.to_dict()
    assert result.to_format("json", with_metadata=False) == result.to_json()


def test_the_alerts_with_metadata_is_a_foreign_member_of_the_feature_collection() -> None:
    """GeoJSON carries the block after `type`, where the REST API puts it (RFC 7946, 6.1)."""
    result = _alerts()
    data = json.loads(result.to_format("GeoJSON", with_metadata=True))
    assert list(data) == ["type", "metadata", "snapshot", "features"]
    assert data["metadata"] == result.to_dict(with_metadata=True)["metadata"]
    assert data == result.to_ogc_feature_collection(with_metadata=True)
    assert list(result.to_ogc_feature_collection()) == ["type", "snapshot", "features"]


def test_the_alerts_with_metadata_says_what_the_rest_api_says_of_the_provider() -> None:
    """The licence and the credit line are those of the REST API's block, which is built from the same terms."""
    result = _alerts()
    rest = metadata_to_dict(alerts_metadata(DwdWeatherAlertRequest, result.df.height, result.data_updated_at))
    block = result.to_dict(with_metadata=True)["metadata"]
    for key in ("name_english", "license", "attribution", "url"):
        assert block["provider"][key] == rest["provider"][key], key
    assert block["data_updated_at"] == rest["data_updated_at"]
    assert block["producer"] == rest["producer"]


def test_the_alerts_csv_has_no_place_for_the_block_and_is_given_none() -> None:
    """As for the other results, CSV is given no argument: it is the same with or without `with_metadata`."""
    result = _alerts()
    assert result.to_format("csv", with_metadata=True, indent=2) == result.to_csv()


def test_the_alerts_result_is_given_the_arguments_it_takes() -> None:
    """The one set of arguments of a caller is cut down to each format's: `with_stations` and `width` are dropped."""
    result = _alerts()
    everything = {"with_metadata": True, "indent": 2, "with_stations": True, "width": 3}
    assert result.to_format("json", **everything) == result.to_json(indent=2, with_metadata=True)
    assert result.to_format("geojson", **everything) == result.to_geojson(indent=2, with_metadata=True)


def test_the_alerts_result_refuses_an_argument_that_no_format_takes() -> None:
    """A typo is a `TypeError` listing the arguments there are, not a silently different document."""
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'with_metdata'"):
        _alerts().to_format("json", with_metdata=True)


def test_the_alerts_result_names_the_formats_it_has_for_one_it_has_not() -> None:
    """A format of the registry that alerts do not render is as unknown to them as one that does not exist."""
    for fmt in ("ndjson", "png", "xml"):
        with pytest.raises(UnknownFormatError) as error:
            _alerts().to_format(fmt)
        assert error.value.supported == ("json", "geojson", "csv")
