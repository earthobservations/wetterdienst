# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The KOSTRA request and result: which tables are read, what is made of the rows, and what is refused."""

from __future__ import annotations

import csv
import io
import json
import zlib

import polars as pl
import pytest

from wetterdienst.exceptions import LocationOutOfRangeError, MetaFileFormatError, RequestError, UnknownFormatError
from wetterdienst.provider.dwd.kostra import DURATIONS, EDITION, RETURN_PERIODS, DwdKostraRequest, DwdKostraResult
from wetterdienst.provider.dwd.kostra.api import _SCHEMA
from wetterdienst.provider.dwd.kostra.metadata import KOSTRA_NOTE, table_url

from .stubs import BERLIN, FRANKFURT, HAMBURG, MUNICH, NORTH_SEA, TABLES, UPDATED, csv_name, csv_of, serve, zipped


def test_a_duration_reads_one_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lookup of one duration downloads that table and no other."""
    asked = serve(monkeypatch)

    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()

    assert asked == [table_url(60)]
    assert result.df.height == len(RETURN_PERIODS)
    assert result.df["duration_minutes"].unique().to_list() == [60]
    assert result.df["return_period_years"].to_list() == list(RETURN_PERIODS)


def test_without_a_duration_all_22_tables_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole table of a cell is 22 durations and 9 return periods, in the order of the tables."""
    asked = serve(monkeypatch)

    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1]).query()

    assert asked == [table_url(duration) for duration in DURATIONS]
    assert result.df.height == len(DURATIONS) * len(RETURN_PERIODS)
    assert result.df.schema == pl.Schema(_SCHEMA)
    assert result.df.select("duration_minutes", "return_period_years").rows() == [
        (duration, period) for duration in DURATIONS for period in RETURN_PERIODS
    ]


def test_a_return_period_keeps_that_row_of_each_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """The return period is a filter of the rows, which the tables hold as columns."""
    serve(monkeypatch)

    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], return_period=100).query()

    assert result.df["return_period_years"].unique().to_list() == [100]
    assert result.df["duration_minutes"].to_list() == list(DURATIONS)


def test_the_values_are_those_of_dwds_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Berlin, 60 minutes, once in 100 years: 48.9 mm, 135.8 l/(s ha), +-25 %, as the table of DWD has it (`48,9`)."""
    serve(monkeypatch)

    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60, return_period=100).query()

    assert result.df.to_dicts() == [
        {
            "duration_minutes": 60,
            "return_period_years": 100,
            "depth_mm": 48.9,
            "intensity_l_s_ha": 135.8,
            "uncertainty_percent": 25.0,
        }
    ]


def test_the_values_of_dwds_own_example_are_those_it_works_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Anwendungshilfe reads cell 160126 at 5 minutes as 11.2 mm for 5 a and 20.5 mm for 100 a (+-10 %, +-12 %)."""
    serve(monkeypatch)

    result = DwdKostraRequest(latitude=FRANKFURT[0], longitude=FRANKFURT[1], duration=5).query()

    rows = {row["return_period_years"]: row for row in result.df.to_dicts()}
    assert result.cell.index_rc == "160126"
    assert (rows[5]["depth_mm"], rows[5]["intensity_l_s_ha"], rows[5]["uncertainty_percent"]) == (11.2, 373.3, 10.0)
    assert (rows[100]["depth_mm"], rows[100]["intensity_l_s_ha"], rows[100]["uncertainty_percent"]) == (
        20.5,
        683.3,
        12.0,
    )


def test_the_intensity_is_the_depth_over_the_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    """A check of the columns against each other: RN is HN / D in l/(s ha), to DWD's resolution of 0.1."""
    serve(monkeypatch)

    result = DwdKostraRequest(latitude=MUNICH[0], longitude=MUNICH[1]).query()

    for row in result.df.iter_rows(named=True):
        assert row["intensity_l_s_ha"] == pytest.approx(row["depth_mm"] / row["duration_minutes"] * 10000 / 60, abs=0.1)


def test_the_cell_is_named_and_placed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer says which cell it is of, DWD's `INDEX_RC` and the centre, which is not the point asked for."""
    serve(monkeypatch)

    result = DwdKostraRequest(latitude=HAMBURG[0], longitude=HAMBURG[1], duration=60).query()

    assert result.to_dict()["cell"] == {
        "index_rc": "083144",
        "row": 83,
        "column": 144,
        "latitude": 53.550184,
        "longitude": 10.022628,
    }
    assert result.to_dict()["edition"] == EDITION == "KOSTRA-DWD-2020"


def test_the_date_of_the_data_is_the_newest_file_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """`data_updated_at` is the `Last-Modified` of the files, December 2022 for DWD's."""
    serve(monkeypatch)

    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()

    assert result.data_updated_at == UPDATED


def test_the_metadata_names_dwd_the_licence_and_what_was_done(monkeypatch: pytest.MonkeyPatch) -> None:
    """The licence and the credit line are DWD's, and the note says that the values are statistics of a cell."""
    serve(monkeypatch)
    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()

    metadata = result.to_dict(with_metadata=True)["metadata"]

    assert list(result.to_dict(with_metadata=True))[:1] == ["metadata"]
    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert metadata["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert metadata["data_updated_at"] == "2022-12-12T17:12:06.000000+00:00"
    assert metadata["processing_note"].endswith(KOSTRA_NOTE)
    assert "not measurements" in metadata["processing_note"]
    # the values are DWD's numbers, selected for the cell, no readings: not the note of an estimate
    assert "selected or calculated from the provider's readings" not in metadata["processing_note"]


def test_the_terms_of_the_provider() -> None:
    """The extent is Germany and the border DWD gives values for, and a national extent names the country."""
    terms = DwdKostraRequest.terms

    assert terms.country_code == "DE"
    assert terms.extent.country_codes == ("DE",)
    west, _, east, _ = terms.extent.bbox
    assert west < 5.8
    assert east > 15.1


def test_json_and_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON holds the cell and the table, CSV the table alone, a row each."""
    serve(monkeypatch)
    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()

    data = json.loads(result.to_json())
    rows = list(csv.DictReader(io.StringIO(result.to_csv())))

    assert list(data) == ["edition", "cell", "values"]
    assert data["values"][8]["depth_mm"] == 48.9
    assert list(rows[0]) == list(_SCHEMA)
    assert [row["depth_mm"] for row in rows][8] == "48.9"
    assert json.loads(result.to_format("JSON", with_metadata=True))["metadata"]["provider"]["name_local"]
    assert result.to_format("csv") == result.to_csv()
    with pytest.raises(UnknownFormatError):
        result.to_format("geojson")


def test_a_cell_without_values_is_an_error_and_no_empty_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """DWD writes `-99,9` for the sea and beyond its border: the answer is a refusal, not a table of nulls."""
    serve(monkeypatch)

    with pytest.raises(LocationOutOfRangeError, match=r"no KOSTRA-DWD-2020 values.*000000"):
        DwdKostraRequest(latitude=NORTH_SEA[0], longitude=NORTH_SEA[1], duration=60).query()


def test_a_cell_without_values_is_refused_in_every_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """All 22 tables hold no value for it, which is what DWD publishes (all or none of a cell, in every table)."""
    serve(monkeypatch)

    with pytest.raises(LocationOutOfRangeError):
        DwdKostraRequest(latitude=NORTH_SEA[0], longitude=NORTH_SEA[1]).query()


def test_a_point_outside_the_grid_is_refused_before_anything_is_downloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """The request knows the cell of the point from the grid alone, so no table is asked for."""
    asked = serve(monkeypatch)

    with pytest.raises(LocationOutOfRangeError):
        DwdKostraRequest(latitude=40.0, longitude=0.0, duration=60)

    assert asked == []


def test_a_cell_with_some_of_its_values_missing_is_a_format_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """DWD gives a cell all its values or none: some missing is not what it publishes, and is no table of nulls.

    The codes are read as null (the depth of the 10 year rain, the uncertainty of the 100 year rain), and a cell that
    has some of them is refused, since no text of the source would stand beside the null.
    """
    lines = []
    for line in _csv_lines(60):
        if line.startswith(b"105190;"):
            fields = line.split(b";")
            fields[5] = b"-99,9"  # HN_010A
            fields[-1] = b"-99"  # UC_100A
            line = b";".join(fields)
        lines.append(line)
    serve(monkeypatch, {f"{csv_name(60)}.zip": zipped(b"\n".join(lines) + b"\n", csv_name(60))})

    with pytest.raises(MetaFileFormatError, match=r"cell 105190 has 2 of its 27 values missing"):
        DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()


def _csv_lines(duration: int) -> list[bytes]:
    return csv_of(duration).rstrip(b"\n").split(b"\n")


@pytest.mark.parametrize(
    "arguments",
    [{"duration": 7}, {"duration": 61}, {"duration": 0}, {"return_period": 4}, {"return_period": 200}],
)
def test_a_duration_or_return_period_dwd_does_not_publish_is_refused(arguments: dict[str, int]) -> None:
    """The request lists the ones that are published, and asks DWD for nothing."""
    with pytest.raises(RequestError, match="use one of"):
        DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], **arguments)


def test_the_published_durations_and_return_periods() -> None:
    """DWD's 22 durations (5 minutes to 7 days) and 9 return periods (1 to 100 years)."""
    assert len(DURATIONS) == 22
    assert (DURATIONS[0], DURATIONS[-1]) == (5, 7 * 24 * 60)
    assert RETURN_PERIODS == (1, 2, 3, 5, 10, 20, 30, 50, 100)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"<html>Service Unavailable</html>", id="a-page-of-an-outage"),
        pytest.param(zipped(b""), id="an-empty-table"),
        pytest.param(zipped(b"INDEX_RC;HN_001A\n105190;1,0\n"), id="another-layout"),
    ],
)
def test_what_is_no_table_of_dwd_is_a_format_error(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    """A page of an outage answered with a 200, or a table that is not laid out as DWD describes it, is never data."""
    serve(monkeypatch, {f"{csv_name(60)}.zip": body})

    with pytest.raises(MetaFileFormatError):
        DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()


def test_a_table_without_the_row_of_the_cell_is_a_format_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """DWD's tables have all 90,000 rows: one that lacks the cell is cut short."""
    content = b"\n".join(line for line in _csv_lines(60) if not line.startswith(b"105190;")) + b"\n"
    serve(monkeypatch, {f"{csv_name(60)}.zip": zipped(content, csv_name(60))})

    with pytest.raises(MetaFileFormatError, match="no row for the cell 105190"):
        DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()


def test_a_value_that_is_no_number_is_a_format_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A text where DWD writes a number is a change of its format, and not a null."""
    content = b"\n".join(
        line.replace(b";48,9;", b";n/a;") if line.startswith(b"105190;") else line for line in _csv_lines(60)
    )
    serve(monkeypatch, {f"{csv_name(60)}.zip": zipped(content + b"\n", csv_name(60))})

    with pytest.raises(MetaFileFormatError, match="no number"):
        DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()


def test_a_result_is_what_the_request_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    """The request gives a `DwdKostraResult`, which names the edition."""
    serve(monkeypatch)

    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()

    assert isinstance(result, DwdKostraResult)
    assert result.edition == "KOSTRA-DWD-2020"
    assert "DwdKostraRequest(latitude=52.52" in repr(DwdKostraRequest(latitude=52.52, longitude=13.4))


def test_a_duration_given_as_a_whole_float_is_the_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    """60.0 minutes is the 60 minutes of the file `D00060`, not a format error of the name of the file."""
    asked = serve(monkeypatch)

    result = DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60.0, return_period=100.0).query()  # ty: ignore[invalid-argument-type]

    assert asked == [table_url(60)]
    assert result.df.height == 1


@pytest.mark.parametrize("offset", [40, 100, 200, 300, 400])
def test_a_real_table_with_a_byte_flipped_is_a_format_error(monkeypatch: pytest.MonkeyPatch, offset: int) -> None:
    """A copy damaged in the cache or on the way: the reader of the archive says so in its own way, and none escapes."""
    body = bytearray(TABLES[f"{csv_name(60)}.zip"])
    body[offset] ^= 0xFF
    serve(monkeypatch, {f"{csv_name(60)}.zip": bytes(body)})

    with pytest.raises(MetaFileFormatError):
        DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()


@pytest.mark.parametrize(
    "error",
    [
        zlib.error("Error -3 while decompressing"),
        EOFError("cut short"),
        NotImplementedError("compression"),
        RuntimeError("encrypted"),
    ],
)
def test_what_the_readers_of_an_archive_raise_is_a_format_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """A damaged member raises `zlib.error` or `EOFError`; an unknown compression or a password raise others."""
    serve(monkeypatch)

    def raising(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr("zipfile.ZipFile.open", raising)

    with pytest.raises(MetaFileFormatError, match="no readable zip archive") as raised:
        DwdKostraRequest(latitude=BERLIN[0], longitude=BERLIN[1], duration=60).query()

    assert raised.value.__cause__ is error
