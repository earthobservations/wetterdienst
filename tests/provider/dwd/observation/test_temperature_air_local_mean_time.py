# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the months of the East German hourly air temperature whose `MEZ (MD)` stamps are mean local time (GH-3910).

The table is `local_mean_time_blocks.csv`: 1,321 station-months at 17 stations, mostly 1952 to 1961, which the shift of
-1 h leaves 0.2 to 0.5 h early. The values and the stamps are those of any `MEZ (MD)` period; the rows carry
`zone:mez-local-mean-time` instead of `zone:mez`.
"""

import datetime as dt
import zipfile
from io import BytesIO
from itertools import pairwise

import polars as pl
import pytest

from tests.provider.dwd.observation.test_temperature_air_mez_blocks import (
    _FOOTER,
    _HEADER,
    _air_temperature,
    _at,
    _hours,
    _rf,
    _serve,
    _tt,
    _values,
)
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation import download as dwd_observation_download
from wetterdienst.provider.dwd.observation.download import LOCAL_MEAN_TIME_SPANS
from wetterdienst.provider.dwd.observation.local_mean_time_blocks import (
    ZONE_LOCAL_MEAN_TIME,
    local_mean_time_blocks,
    local_mean_time_spans,
)
from wetterdienst.provider.dwd.observation.mez_blocks import ZONE_MEZ, mez_block_spans
from wetterdienst.util.network import File

#: the first and last day of the `MEZ (MD)` periods of the 17 stations, `Von_Datum` and `Bis_Datum` of
#: `Metadaten_Parameter_tu_stunde_<id>.txt` of the historical archives (TT_TU, read 2026-11-09); Fichtelberg has two
_MD_PERIODS = {
    "00722": ((dt.date(1951, 1, 1), dt.date(1991, 11, 1)),),
    "00853": ((dt.date(1951, 1, 1), dt.date(1991, 11, 1)),),
    "01358": ((dt.date(1951, 1, 1), dt.date(1991, 5, 2)), (dt.date(1991, 5, 11), dt.date(1991, 11, 1))),
    "01544": ((dt.date(1951, 1, 1), dt.date(1991, 10, 31)),),
    "01957": ((dt.date(1953, 1, 1), dt.date(1991, 10, 31)),),
    "02503": ((dt.date(1951, 1, 1), dt.date(1991, 11, 1)),),
    "02925": ((dt.date(1956, 1, 1), dt.date(1991, 11, 1)),),
    "02928": ((dt.date(1951, 1, 1), dt.date(1972, 5, 1)),),
    "03126": ((dt.date(1955, 1, 1), dt.date(1991, 11, 1)),),
    "03946": ((dt.date(1951, 1, 1), dt.date(1991, 10, 31)),),
    "03987": ((dt.date(1893, 1, 1), dt.date(1991, 11, 1)),),
    "04271": ((dt.date(1947, 1, 1), dt.date(1991, 11, 1)),),
    "04625": ((dt.date(1950, 1, 1), dt.date(1991, 11, 1)),),
    "04752": ((dt.date(1951, 6, 1), dt.date(1991, 11, 1)),),
    "05419": ((dt.date(1951, 1, 1), dt.date(1983, 1, 1)),),
    "05490": ((dt.date(1951, 1, 1), dt.date(1991, 10, 31)),),
    "05629": ((dt.date(1951, 1, 1), dt.date(1991, 11, 1)),),
}

_MD = (("19490101", "19911031", "MEZ (MD)"), ("19911101", "20010401", "UTC"))
_LMT = f"3,zone:{ZONE_LOCAL_MEAN_TIME}"
_MEZ = f"3,zone:{ZONE_MEZ}"


# the table


def test_the_table_has_the_months_of_the_research() -> None:
    """Test the size of the table: 1,321 station-months in 26 blocks at 17 stations."""
    blocks = local_mean_time_blocks()
    assert len(blocks) == 26
    assert sum(block.n_months for block in blocks) == 1321
    assert {block.station_id for block in blocks} == set(_MD_PERIODS)
    assert all(len(block.station_id) == 5 and block.station_id.isdigit() for block in blocks)


def test_a_block_counts_its_months_and_its_stamps_are_whole_utc_days() -> None:
    """Test that a block runs from the stamp 01 of its first day to the stamp 00 after its last month."""
    for block in local_mean_time_blocks():
        assert len(block.start) == len(block.end) == 7
        first = _at(int(block.start[:4]), int(block.start[5:]), 1)
        last = _at(int(block.end[:4]), int(block.end[5:]), 1)
        assert (last.year - first.year) * 12 + last.month - first.month + 1 == block.n_months
        assert block.first_stamp == first + dt.timedelta(hours=1)
        assert block.last_stamp.day == 1
        assert block.last_stamp.hour == 0
        assert (block.last_stamp - dt.timedelta(days=1)).month == last.month


def test_the_blocks_of_a_station_are_apart_and_in_order() -> None:
    """Test that no two blocks of a station touch or overlap, which would be a second block of one run."""
    for station, spans in local_mean_time_spans().items():
        for (_, last), (first, _) in pairwise(spans):
            assert first - last > dt.timedelta(days=28), station


def test_the_months_lie_in_the_years_the_research_covers_and_inside_the_md_periods() -> None:
    """Test 1952-01 to 1961-12 (ISD 10xxxx begins in 1952, the regime ends 1962-01-01) and Potsdam."""
    for block in local_mean_time_blocks():
        if block.station_id == "03987":
            assert (block.start, block.end) == ("1973-01", "1975-05")
        else:
            assert "1952-01" <= block.start <= block.end <= "1961-12", block
        periods = _MD_PERIODS[block.station_id]
        # the stamps as written lie inside one `MEZ (MD)` period of the station
        assert any(first <= block.first_stamp.date() and block.last_stamp.date() <= last for first, last in periods), (
            block
        )


def test_the_values_of_a_block_are_what_the_research_found() -> None:
    """Test the numbers of a row: the offset to ISD -0.5 to -0.8 h (Gardelegen 1952 -1.0), the lag 0 to 0.5 h."""
    blocks = local_mean_time_blocks()
    for block in blocks:
        # west and centre of the old DDR, and Potsdam at 13.06
        assert 10.1 <= block.longitude <= 13.1, block
        assert -1.0 <= block.isd_delta <= -0.5, block
        assert 0.0 <= block.early_by <= 0.5, block
        assert -1.0 <= block.phase_vs_mez <= 0.5, block
    assert sum(1 for block in blocks if block.isd_delta == -1.0) == 1


def test_the_months_are_in_no_block_of_the_table_of_gh_3776_or_the_comparison_with_isd() -> None:
    """Test that the plain MEZ periods of the other table and the East German MD periods shift no stamp twice."""
    other = mez_block_spans()
    for station, spans in local_mean_time_spans().items():
        for first, last in spans:
            for other_first, other_last in other.get(station, ()):
                assert last < other_first or first > other_last, station


def test_the_table_is_the_one_the_download_reads() -> None:
    """Test that the spans the download uses are those of the table, by station."""
    assert local_mean_time_spans() == LOCAL_MEAN_TIME_SPANS
    assert LOCAL_MEAN_TIME_SPANS["00722"] == ((_at(1952, 1, 1, 1), _at(1962, 1, 1, 0)),)


# the values of a station


@pytest.mark.parametrize(
    ("station", "first_month", "last_month"),
    [("00722", (1952, 1), (1961, 12)), ("03987", (1973, 1), (1975, 5))],
)
def test_a_month_inside_a_block_is_flagged_and_the_one_before_and_after_are_not(
    monkeypatch: pytest.MonkeyPatch, station: str, first_month: tuple[int, int], last_month: tuple[int, int]
) -> None:
    """Test Brocken 00722 (1952-01 to 1961-12) and Potsdam 03987 (1973-01 to 1975-05) at both ends of the block.

    The stamp 01 of the first day of the first month is the reading of 00 UTC of it: the first row of the block. The
    stamp 00 before it is the 23 UTC of the month before and is `zone:mez`, as is every row a `MEZ (MD)` period shifts.
    The stamp 00 after the last month (the 24 of its last day, 23 UTC) is the last row of the block, the stamp 01 after
    it the first row that is not. Both parameters.
    """
    year, month = first_month
    last_year, last_mon = last_month
    end_year, end_month = (last_year + last_mon // 12, last_mon % 12 + 1)
    written = [
        *_hours(_at(year, month, 1) - dt.timedelta(hours=2), _at(year, month, 1, 2)),
        *_hours(_at(end_year, end_month, 1) - dt.timedelta(hours=2), _at(end_year, end_month, 1, 2)),
    ]
    _serve(monkeypatch, station, written, labels=_MD)
    df = _values(station, _at(year, month, 1) - dt.timedelta(days=1), _at(end_year, end_month, 2))
    first_stamp = _at(year, month, 1, 1)
    last_stamp = _at(end_year, end_month, 1, 0)
    for parameter, signal in (("temperature_air_2m", _tt), ("humidity_relative", _rf)):
        rows = df.filter(pl.col("parameter") == parameter).select("timestamp", "value", "quality_flags").rows()
        assert rows == [
            (moment - dt.timedelta(hours=1), signal(moment), _LMT if first_stamp <= moment <= last_stamp else _MEZ)
            for moment in written
        ]
        flagged = [timestamp + dt.timedelta(hours=1) for timestamp, _, flags in rows if flags == _LMT]
        assert min(flagged) == first_stamp
        assert max(flagged) == last_stamp


def test_the_gap_between_two_blocks_of_a_station_is_zone_mez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Magdeburg 03126: block 1955-01 to 1958-06, then 1958-07 to 1959-01 (a MEZ month by ISD), then 1959-02 on."""
    written = [
        *_hours(_at(1958, 6, 30, 22), _at(1958, 7, 1, 2)),
        *_hours(_at(1959, 1, 31, 22), _at(1959, 2, 1, 2)),
    ]
    _serve(monkeypatch, "03126", written, labels=_MD)
    tt = _air_temperature(_values("03126", _at(1958, 6, 1), _at(1959, 3, 1))).rows()
    assert tt == [
        (_at(1958, 6, 30, 21), _tt(_at(1958, 6, 30, 22)), _LMT),
        (_at(1958, 6, 30, 22), _tt(_at(1958, 6, 30, 23)), _LMT),
        # the stamp 1958-07-01 00 is the last of June
        (_at(1958, 6, 30, 23), _tt(_at(1958, 7, 1, 0)), _LMT),
        (_at(1958, 7, 1, 0), _tt(_at(1958, 7, 1, 1)), _MEZ),
        (_at(1958, 7, 1, 1), _tt(_at(1958, 7, 1, 2)), _MEZ),
        (_at(1959, 1, 31, 21), _tt(_at(1959, 1, 31, 22)), _MEZ),
        (_at(1959, 1, 31, 22), _tt(_at(1959, 1, 31, 23)), _MEZ),
        (_at(1959, 1, 31, 23), _tt(_at(1959, 2, 1, 0)), _MEZ),
        (_at(1959, 2, 1, 0), _tt(_at(1959, 2, 1, 1)), _LMT),
        (_at(1959, 2, 1, 1), _tt(_at(1959, 2, 1, 2)), _LMT),
    ]


def test_a_station_that_is_in_no_block_keeps_zone_mez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Angermünde 00164 (east of 13.5 degrees: stamps MEZ throughout) in 1957 and Brocken 00722 in 1962."""
    _serve(monkeypatch, "00164", [_at(1957, 6, 1, 12)], labels=_MD)
    assert _air_temperature(_values("00164", _at(1957, 6, 1), _at(1957, 7, 1))).rows() == [
        (_at(1957, 6, 1, 11), _tt(_at(1957, 6, 1, 12)), _MEZ)
    ]
    _serve(monkeypatch, "00722", [_at(1962, 6, 1, 12)], labels=_MD)
    assert _air_temperature(_values("00722", _at(1962, 6, 1), _at(1962, 7, 1))).rows() == [
        (_at(1962, 6, 1, 11), _tt(_at(1962, 6, 1, 12)), _MEZ)
    ]


def test_a_month_of_a_block_in_a_utc_period_is_returned_as_written_without_a_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that only a row a `MEZ (MD)` period shifts is flagged: Brocken 1957-06 labelled UTC has no token."""
    written = _hours(_at(1957, 6, 1, 10), _at(1957, 6, 1, 12))
    _serve(monkeypatch, "00722", written, labels=(("19490101", "20010401", "UTC"),))
    tt = _air_temperature(_values("00722", _at(1957, 6, 1), _at(1957, 7, 1))).rows()
    assert tt == [(moment, _tt(moment), "3") for moment in written]


def test_the_zone_stands_before_the_text_of_a_sentinel_which_stays_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Brocken 1957-06-01 12 MEZ (MD) with `-999` in TT_TU: `3,zone:mez-local-mean-time,raw:-999`."""
    metadata = _HEADER + "".join(
        f"722;19490101;19911031;Brocken;{parameter};x;x;Daten der Temperatur;Stundenwerte in MEZ (MD);;;eor;\n"
        for parameter in ("RF_TU", "TT_TU")
    )
    product = "STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor\n" + f"{722:>12};1957060112;    3;  -999;  55.0;eor\n"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Metadaten_Parameter_tu_stunde_00722.txt", (metadata + _FOOTER).encode("latin-1"))
        archive.writestr("produkt_tu_stunde_19490101_20251231_00722.txt", product.encode("latin-1"))
    url = "https://example.invalid/stundenwerte_TU_00722_hist.zip"
    monkeypatch.setattr(
        dwd_observation_api, "create_file_list_for_climate_observations", lambda *_, **__: pl.Series([url])
    )
    monkeypatch.setattr(
        dwd_observation_download,
        "download_files",
        lambda **_kwargs: [File(url=url, content=BytesIO(buffer.getvalue()), status=200)],
    )
    tt = _air_temperature(_values("00722", _at(1957, 6, 1), _at(1957, 7, 1))).rows()
    assert tt == [(_at(1957, 6, 1, 11), None, f"3,zone:{ZONE_LOCAL_MEAN_TIME},raw:-999")]
