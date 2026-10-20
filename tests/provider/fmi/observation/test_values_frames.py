# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for FMI's daily values, its windows and its empty answers (GH-2627).

The hourly frame is held by the stub of `test_value_stubs.py`. These cover what it leaves out: the daily stored query,
the windows of a long range that share their boundary stamp, and the answers that hold no reading (a station FMI does
not know, an empty collection, an exception report). The responses are the shapes FMI writes, served through the
provider's own reader, and `tests/provider/frames.snapshot.json` records what the core made of each: the net under
moving the shaping of the frame out of the provider.
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.fmi.observation import FmiObservationRequest
from wetterdienst.provider.fmi.observation import api as fmi_api
from wetterdienst.util.network import File

STATION = "100971"
UTC = dt.UTC

_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">'
)
_TAIL = "</wfs:FeatureCollection>"


def _element(time: str, name: str, value: str) -> str:
    return (
        "<wfs:member><BsWfs:BsWfsElement>"
        f"<BsWfs:Time>{time}</BsWfs:Time><BsWfs:ParameterName>{name}</BsWfs:ParameterName>"
        f"<BsWfs:ParameterValue>{value}</BsWfs:ParameterValue></BsWfs:BsWfsElement></wfs:member>"
    )


def _collection(*elements: str) -> bytes:
    return (_HEAD + "".join(elements) + _TAIL).encode()


_EXCEPTION_REPORT = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1" version="2.0.0">'
    b'<ows:Exception exceptionCode="OperationProcessingFailed"><ows:ExceptionText>Too many requests</ows:ExceptionText>'
    b"</ows:Exception></ows:ExceptionReport>"
)


def _serve(monkeypatch: pytest.MonkeyPatch, answer: bytes | Exception, *, status: int = 200) -> list[str]:
    asked: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        url = url or args[0]
        asked.append(url)
        content = answer if isinstance(answer, Exception) else BytesIO(answer)
        return File(url=url, content=content, status=status)

    monkeypatch.setattr(fmi_api, "download_file", download_file)
    return asked


def _values(resolution: str, start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    request = FmiObservationRequest(
        parameters=[(resolution, "data")],
        start=start,
        end=end,
        settings=_settings(),
        options=_options(drop_nulls=False),
    )
    return stations_result(request, resolution, "data", STATION).values().all().df


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["station_id"].unique().to_list() == [STATION]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


def test_fmi_daily_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The daily stored query: a `-1.0` of the precipitation is 0.0 and a `NaN` is null, each beside its text."""
    body = _collection(
        _element("2024-01-01T00:00:00Z", "tday", "-3.5"),
        _element("2024-01-01T00:00:00Z", "rrday", "-1.0"),
        _element("2024-01-01T00:00:00Z", "snow", "12.0"),
        _element("2024-01-02T00:00:00Z", "tday", "NaN"),
        _element("2024-01-02T00:00:00Z", "rrday", "1.4"),
    )
    asked = _serve(monkeypatch, body)
    df = _values("daily", dt.datetime(2024, 1, 1, tzinfo=UTC), dt.datetime(2024, 1, 2, tzinfo=UTC))
    _assert_the_long_form(df, resolution="daily")
    assert df.height == 5
    assert len(asked) == 1
    assert "daily%3A%3Asimple" in asked[0]
    precipitation = df.filter(pl.col("parameter").eq("precipitation_amount")).sort("timestamp")
    assert precipitation["value"].to_list() == [0.0, 1.4]
    assert precipitation["quality_flags"].to_list() == ["raw:-1.0", None]
    assert df.filter(pl.col("value").is_null())["quality_flags"].to_list() == ["raw:NaN"]


def test_fmi_hourly_windows_that_share_a_boundary_come_out_as_one_row_per_stamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A range of eight days is two windows, whose shared boundary stamp is kept once (the earlier window's copy)."""
    asked = _serve(monkeypatch, _collection(_element("2024-01-08T00:00:00Z", "t2m", "-1.5")))
    df = _values("hourly", dt.datetime(2024, 1, 1, tzinfo=UTC), dt.datetime(2024, 1, 9, tzinfo=UTC))
    _assert_the_long_form(df, resolution="hourly")
    assert len(asked) == 2
    assert df.height == 1
    assert df["timestamp"].to_list() == [dt.datetime(2024, 1, 8, tzinfo=UTC)]


@pytest.mark.parametrize(
    ("answer", "status"),
    [
        pytest.param(_collection(), 200, id="empty-collection"),
        pytest.param(_EXCEPTION_REPORT, 200, id="exception-report"),
        pytest.param(OSError("Unknown 'fmisid' value!"), 400, id="unknown-station"),
    ],
)
def test_fmi_without_a_reading_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch, answer: bytes | Exception, status: int
) -> None:
    """A station that reports nothing for the window, one FMI does not know (a 400) and a refusal are no rows."""
    _serve(monkeypatch, answer, status=status)
    df = _values("hourly", dt.datetime(2024, 1, 1, tzinfo=UTC), dt.datetime(2024, 1, 1, 1, tzinfo=UTC))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()


def test_fmi_hourly_without_a_date_range_comes_out_as_the_empty_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The WFS is asked for a window, so a request with no bounds asks for nothing."""
    asked = _serve(monkeypatch, _collection(_element("2024-01-01T00:00:00Z", "t2m", "-1.5")))
    request = FmiObservationRequest(parameters=[("hourly", "data")], settings=_settings())
    df = stations_result(request, "hourly", "data", STATION).values().all().df
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
    assert asked == []
