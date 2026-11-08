# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the blocks of the hourly air temperature that both methods find in MEZ (GH-3776).

The table is `mez_blocks.csv`: the station-months that the ISD fit and the diurnal-phase test both call MEZ under every
variant of the constants of the scan, less the months the library shifted before (`MEZ_BY_COMPARISON`, GH-3029).
"""

import datetime as dt
import math
import zipfile
from io import BytesIO
from itertools import pairwise

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Options, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation import download as dwd_observation_download
from wetterdienst.provider.dwd.observation.download import (
    _MEZ_COMPARED_WITH_ISD,
    MEZ_BATCH_SPANS,
    MEZ_BY_COMPARISON,
)
from wetterdienst.provider.dwd.observation.mez_blocks import ZONE_MEZ, ZONE_MEZ_BATCH, mez_block_spans, mez_blocks
from wetterdienst.util.network import File

_HEADER = (
    "Stations_ID;Von_Datum;Bis_Datum;Stationsname;Parameter;Parameterbeschreibung;Einheit;"
    "Datenquelle (Strukturversion=SV);Zusatz-Info;Besonderheiten;Literaturhinweis;eor;\n"
)
_FOOTER = "Legende: FT  = Folgetag; GZ = Gesetzliche Zeit\ngenerierte: 22.04.2026 --  Deutscher Wetterdienst  --\n"


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=dt.UTC)


def _stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y%m%d%H")


def _tt(moment: dt.datetime) -> float:
    """Make a smooth air temperature that tells the stamp it was written under (to the tenth of a degree)."""
    return round(10 * math.sin(moment.timestamp() / 3600 / 37), 1)


def _rf(moment: dt.datetime) -> float:
    return round(60 + 30 * math.sin(moment.timestamp() / 3600 / 53), 1)


def _hours(first: dt.datetime, last: dt.datetime) -> list[dt.datetime]:
    return [first + dt.timedelta(hours=i) for i in range(int((last - first).total_seconds() // 3600) + 1)]


def _next_day(day: str) -> str:
    return (dt.datetime.strptime(day, "%Y%m%d") + dt.timedelta(days=1)).strftime("%Y%m%d")  # noqa: DTZ007


def _serve(
    monkeypatch: pytest.MonkeyPatch, station: str, stamps: list[dt.datetime], label_to: str = "19951231"
) -> None:
    """Serve the archive of a station whose plain MEZ label runs from 1949 to `label_to`, then UTC."""
    number = int(station)
    metadata = _HEADER + "".join(
        f"{number};{first};{last};Station;{parameter};x;x;Daten der Temperatur;Stundenwerte in {info};;;eor;\n"
        for parameter in ("RF_TU", "TT_TU")
        for first, last, info in (("19490101", label_to, "MEZ"), (_next_day(label_to), "20010401", "UTC"))
    )
    product = "STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor\n" + "".join(
        f"{number:>12};{_stamp(moment)};    3;{_tt(moment):>6.1f};{_rf(moment):>6.1f};eor\n" for moment in stamps
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"Metadaten_Parameter_tu_stunde_{station}.txt", (metadata + _FOOTER).encode("latin-1"))
        archive.writestr(f"produkt_tu_stunde_19490101_20251231_{station}.txt", product.encode("latin-1"))
    url = f"https://example.invalid/stundenwerte_TU_{station}_hist.zip"
    monkeypatch.setattr(
        dwd_observation_api, "create_file_list_for_climate_observations", lambda *_, **__: pl.Series([url])
    )
    monkeypatch.setattr(
        dwd_observation_download,
        "download_files",
        lambda **_kwargs: [File(url=url, content=BytesIO(buffer.getvalue()), status=200)],
    )


def _values(station: str, start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air")],
        periods={Period.HISTORICAL},
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    return (
        stations_result(request, "hourly", "temperature_air", station).values().all().df.sort("parameter", "timestamp")
    )


def _air_temperature(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("parameter") == "temperature_air_2m").select("timestamp", "value", "quality_flags")


# the table


def test_the_table_has_the_blocks_of_the_robust_core() -> None:
    """Test the size of the table: 854 station-months of the scan, less the 46 the library shifted already."""
    blocks = mez_blocks()
    assert len(blocks) == 84
    assert sum(block.n_months for block in blocks) == 808
    assert len({block.station_id for block in blocks}) == 26
    assert all(len(block.station_id) == 5 and block.station_id.isdigit() for block in blocks)
    assert {block.confidence for block in blocks} == {"high", "medium", "low"}


def test_the_months_of_a_block_are_counted_and_its_stamps_are_whole_utc_days() -> None:
    """Test that a block runs from the stamp 01 of its first day to the stamp 00 after its last month."""
    for block in mez_blocks():
        first = _at(int(block.start[:4]), int(block.start[5:]), 1)
        last = _at(int(block.end[:4]), int(block.end[5:]), 1)
        months = (last.year - first.year) * 12 + last.month - first.month + 1
        assert months == block.n_months
        assert block.first_stamp == first + dt.timedelta(hours=1)
        assert block.last_stamp.day == 1
        assert block.last_stamp.hour == 0
        assert block.last_stamp - dt.timedelta(hours=1) >= last
        # the last month's last day: the stamp 00 of the day after it
        assert (block.last_stamp - dt.timedelta(days=1)).month == last.month


def test_a_station_has_no_two_blocks_that_touch_in_the_same_month_or_overlap() -> None:
    """Test that the blocks of a station are apart, or meet at the stamp 00 / 01 of a batch edge."""
    for station, spans in mez_block_spans().items():
        ordered = sorted(spans)
        for (_, last), (first, _) in pairwise(ordered):
            assert last <= first, station
            # a block that begins where another ends: the stamp 00 and the stamp 01 of one day
            assert first - last >= dt.timedelta(hours=1), station


def test_no_block_reaches_into_the_blocks_the_library_shifted_before() -> None:
    """Test that the table of GH-3776 and the comparison with ISD of GH-3029 shift no stamp twice."""
    for station, (first, last) in _MEZ_COMPARED_WITH_ISD.items():
        for block_first, block_last in mez_block_spans().get(station, ()):
            assert block_last < first or block_first > last, station


def test_the_batch_of_1973_to_1975_is_the_months_of_13_stations_inside_the_three_years() -> None:
    """Test that the batch note is on the rows inside 1973-01 to 1975-12 of 13 stations, and on no others."""
    batch = [block for block in mez_blocks() if block.batch_1973_75]
    assert len({block.station_id for block in batch}) == 13
    assert all("1973-01" <= block.start <= block.end <= "1975-12" for block in batch)
    for block in mez_blocks():
        if not block.batch_1973_75:
            assert not ("1973-01" <= block.start <= block.end <= "1975-12" and block.station_id in MEZ_BATCH_SPANS)
    assert set(MEZ_BATCH_SPANS) == {block.station_id for block in batch}


def test_the_comparison_table_holds_the_blocks_of_both_sources() -> None:
    """Test that Nürnberg has its block of GH-3029 and the ones of GH-3776 under both parameters."""
    nuernberg = MEZ_BY_COMPARISON["03668"]
    assert nuernberg["tt_tu"] == nuernberg["rf_tu"]
    assert (_at(1986, 1, 1, 1), _at(1988, 11, 1, 0)) in nuernberg["tt_tu"]
    assert (_at(1973, 1, 1, 1), _at(1976, 1, 1, 0)) in nuernberg["tt_tu"]
    assert (_at(1976, 1, 1, 1), _at(1976, 12, 1, 0)) in nuernberg["tt_tu"]


# the values of a station


def test_a_month_inside_a_block_is_shifted_and_flagged_and_one_outside_is_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Regensburg 04104, block 1978-09 to 1979-03 (and 1978-05 to 06 before, 1979-12 to 1985-10 after).

    1979-01 is inside, 1979-06 lies between the two blocks. Both parameters, `zone:mez`.
    """
    written = _hours(_at(1979, 1, 10), _at(1979, 1, 10, 5)) + _hours(_at(1979, 6, 10), _at(1979, 6, 10, 5))
    _serve(monkeypatch, "04104", written)
    df = _values("04104", _at(1979, 1, 1), _at(1979, 7, 1))
    for parameter, signal in (("temperature_air_2m", _tt), ("humidity_relative", _rf)):
        part = df.filter(pl.col("parameter") == parameter).select("timestamp", "value", "quality_flags")
        rows = part.rows()
        # the row written at the hour t is the reading of t - 1 h inside the block and of t outside
        assert rows[:6] == [
            (moment - dt.timedelta(hours=1), signal(moment), f"3,zone:{ZONE_MEZ}") for moment in written[:6]
        ]
        assert rows[6:] == [(moment, signal(moment), "3") for moment in written[6:]]


def test_the_edges_of_a_block_take_the_row_that_was_moved_and_leave_the_hour_after_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Kiel-Kronshagen 02565, whose block (1973-01 to 1975-09) is of the batch of 1973 to 1975.

    The first stamp is 1973-01-01 01, the report of 00 UTC: it lands on the stamp 00 the file has, which is dropped (the
    row that was moved is kept, as in the blocks of GH-3029). The last stamp is 1975-10-01 00, the 24 of the day, at
    23 UTC; the stamps after it are UTC and none of them is 00 UTC, as the file has no row for that hour.
    """
    written = [
        *_hours(_at(1972, 12, 31, 22), _at(1973, 1, 1, 2)),
        *_hours(_at(1975, 9, 30, 22), _at(1975, 10, 1, 2)),
    ]
    _serve(monkeypatch, "02565", written)
    tt = _air_temperature(_values("02565", _at(1972, 12, 1), _at(1975, 11, 1))).rows()
    batch = f"3,zone:{ZONE_MEZ_BATCH}"
    assert tt == [
        (_at(1972, 12, 31, 22), _tt(_at(1972, 12, 31, 22)), "3"),
        (_at(1972, 12, 31, 23), _tt(_at(1972, 12, 31, 23)), "3"),
        # the stamp 00 as written (UTC, dropped) and the stamp 01 (moved onto 00): the moved row is kept
        (_at(1973, 1, 1, 0), _tt(_at(1973, 1, 1, 1)), batch),
        (_at(1973, 1, 1, 1), _tt(_at(1973, 1, 1, 2)), batch),
        (_at(1975, 9, 30, 21), _tt(_at(1975, 9, 30, 22)), batch),
        (_at(1975, 9, 30, 22), _tt(_at(1975, 9, 30, 23)), batch),
        (_at(1975, 9, 30, 23), _tt(_at(1975, 10, 1, 0)), batch),
        (_at(1975, 10, 1, 1), _tt(_at(1975, 10, 1, 1)), "3"),
        (_at(1975, 10, 1, 2), _tt(_at(1975, 10, 1, 2)), "3"),
    ]


def test_the_batch_of_1973_to_1975_carries_its_own_note_and_the_rest_of_the_station_the_plain_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Nürnberg 03668: `zone:mez` to 1971-11, `zone:mez-1973-75` for 1973-01 to 1975-12, `zone:mez` from 1976-01.

    The batch ends at the stamp 1976-01-01 00 and the next block begins at the stamp 01, so the two meet without a
    gap or a second row at one stamp.
    """
    written = [
        *_hours(_at(1971, 11, 30, 22), _at(1971, 12, 1, 3)),
        *_hours(_at(1972, 6, 1), _at(1972, 6, 1, 2)),
        *_hours(_at(1975, 12, 31, 22), _at(1976, 1, 1, 3)),
    ]
    _serve(monkeypatch, "03668", written)
    tt = _air_temperature(_values("03668", _at(1971, 11, 1), _at(1976, 2, 1))).rows()
    assert tt == [
        # 1971-11 is the last month of its block: the stamp 1971-12-01 00 is its last
        (_at(1971, 11, 30, 21), _tt(_at(1971, 11, 30, 22)), "3,zone:mez"),
        (_at(1971, 11, 30, 22), _tt(_at(1971, 11, 30, 23)), "3,zone:mez"),
        (_at(1971, 11, 30, 23), _tt(_at(1971, 12, 1, 0)), "3,zone:mez"),
        (_at(1971, 12, 1, 1), _tt(_at(1971, 12, 1, 1)), "3"),
        (_at(1971, 12, 1, 2), _tt(_at(1971, 12, 1, 2)), "3"),
        (_at(1971, 12, 1, 3), _tt(_at(1971, 12, 1, 3)), "3"),
        # 1972 is between the blocks, as written
        (_at(1972, 6, 1, 0), _tt(_at(1972, 6, 1, 0)), "3"),
        (_at(1972, 6, 1, 1), _tt(_at(1972, 6, 1, 1)), "3"),
        (_at(1972, 6, 1, 2), _tt(_at(1972, 6, 1, 2)), "3"),
        (_at(1975, 12, 31, 21), _tt(_at(1975, 12, 31, 22)), f"3,zone:{ZONE_MEZ_BATCH}"),
        (_at(1975, 12, 31, 22), _tt(_at(1975, 12, 31, 23)), f"3,zone:{ZONE_MEZ_BATCH}"),
        (_at(1975, 12, 31, 23), _tt(_at(1976, 1, 1, 0)), f"3,zone:{ZONE_MEZ_BATCH}"),
        (_at(1976, 1, 1, 0), _tt(_at(1976, 1, 1, 1)), "3,zone:mez"),
        (_at(1976, 1, 1, 1), _tt(_at(1976, 1, 1, 2)), "3,zone:mez"),
        (_at(1976, 1, 1, 2), _tt(_at(1976, 1, 1, 3)), "3,zone:mez"),
    ]


def test_a_station_that_is_in_no_block_is_returned_as_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the table of a station does not shift another's stamps (Hamburg-Fuhlsbüttel 01975 in 1973)."""
    written = _hours(_at(1973, 6, 1), _at(1973, 6, 1, 3))
    _serve(monkeypatch, "01975", written)
    tt = _air_temperature(_values("01975", _at(1973, 5, 1), _at(1973, 7, 1))).rows()
    assert tt == [(moment, _tt(moment), "3") for moment in written]


def test_a_block_is_returned_as_written_where_the_metadata_does_not_call_the_period_plain_mez_any_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a block inside a period DWD relabels as UTC is not shifted on the strength of an older comparison."""
    written = _hours(_at(1979, 1, 10), _at(1979, 1, 10, 2))
    _serve(monkeypatch, "04104", written, label_to="19781231")
    tt = _air_temperature(_values("04104", _at(1979, 1, 1), _at(1979, 2, 1))).rows()
    assert tt == [(moment, _tt(moment), "3") for moment in written]


def test_a_run_through_the_blocks_of_a_station_has_no_second_row_at_a_stamp_and_loses_one_where_a_block_lands_on_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Nürnberg 1967-06 to 1977-01 hour by hour, every reading checked against the stamp it was written under.

    Every row inside a block is the reading of the stamp an hour later, every other row its own; the stamp a block's
    first row is moved onto holds the moved row, so a block that follows an unshifted stamp 00 costs one row.
    """
    first, last = _at(1967, 6, 30, 22), _at(1977, 1, 2, 23)
    written = _hours(first, last)
    _serve(monkeypatch, "03668", written)
    df = _values("03668", _at(1967, 6, 1), _at(1977, 2, 1))
    tt = _air_temperature(df)
    assert tt.get_column("timestamp").is_unique().all()
    spans = MEZ_BY_COMPARISON["03668"]["tt_tu"]
    hour = dt.timedelta(hours=1)
    # a block start moved onto the stamp 00 that the file has leaves one row less; where that stamp is the last of the
    # block before (the batch ends at 1976-01-01 00 and the next block begins at 01) it is moved itself, and none goes
    lands_on_a_row = [
        span_first
        for span_first, _ in spans
        if span_first - hour >= first
        and span_first <= last
        and not any(other_first <= span_first - hour <= other_last for other_first, other_last in spans)
    ]
    assert len(lands_on_a_row) == 4
    assert tt.height == len(written) - len(lands_on_a_row)
    by_stamp = {moment: _tt(moment) for moment in written}
    for timestamp, value, flags in tt.iter_rows():
        shifted = flags is not None and "zone:" in flags
        assert value == by_stamp[timestamp + dt.timedelta(hours=1) if shifted else timestamp]
        assert shifted == any(
            span_first <= timestamp + dt.timedelta(hours=1) <= span_last for span_first, span_last in spans
        )
