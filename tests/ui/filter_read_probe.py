# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Read many long stations with a `filter` in a process of its own, and say how much memory it needed (GH-4436).

Run by `test_row_options_filter_read_memory.py`: the peak of a process (`ru_maxrss`) never goes down, so each case
needs a process of its own. Arguments: the stations, their readings, the filter, the most rows held (0 for no
limit) and the `max_rows` (0 for none). Prints one JSON line: the peak growth in MB, the rows held, the stations
read, the outcome.
"""

from __future__ import annotations

import datetime as dt
import json
import resource
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import polars as pl

from wetterdienst.model.row_selection import RowsOverLimitError
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.settings import Settings

_START = dt.datetime(1800, 1, 1, tzinfo=dt.UTC)


def _peak_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024 if sys.platform == "darwin" else 1024)


def main(stations: int, readings: int, text: str, held: int, max_rows: int) -> dict[str, object]:
    """Read `stations` stations of `readings` daily readings each, with `text` as the filter."""
    ids = [f"{number:05d}" for number in range(1, stations + 1)]
    frame = pl.DataFrame(
        {
            "resolution": ["daily"] * stations,
            "dataset": ["climate_summary"] * stations,
            "station_id": ids,
            "start_timestamp": [_START] * stations,
            "end_timestamp": [None] * stations,
            "latitude": [53.0] * stations,
            "longitude": [10.0] * stations,
            "elevation": [10.0] * stations,
            "name": ids,
            "state": ["Hamburg"] * stations,
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    DwdObservationRequest._all = lambda _self: frame.lazy()  # noqa: SLF001  # ty: ignore[invalid-assignment]
    read: list[str] = []

    def collect(self: object, station_id: str, parameter_or_dataset: object) -> pl.DataFrame:  # noqa: ARG001
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        name = next(p.name_original for p in dataset if p.name == "temperature_air_min_2m")  # ty: ignore[not-iterable]
        read.append(station_id)
        return pl.DataFrame(
            {
                "timestamp": pl.datetime_range(
                    _START, _START + dt.timedelta(days=readings - 1), "1d", time_zone="UTC", eager=True
                ),
                "parameter": [name] * readings,
                "value": [float(day % 61) / 2 - 10 for day in range(readings)],
                "quality_flags": ["1"] * readings,
                "resolution": ["daily"] * readings,
                "dataset": [dataset.name] * readings,
            },
            schema_overrides={"value": pl.Float64},
        )

    DwdObservationValues._collect_station_parameter_or_dataset = collect  # noqa: SLF001  # ty: ignore[invalid-assignment]
    request = DwdObservationRequest(
        parameters="daily/climate_summary/temperature_air_min_2m",
        start=_START,
        end=_START + dt.timedelta(days=readings),
        settings=Settings(cache_disable=True),
    ).all()
    reader = request.values()
    reader._held_rows_limit = held or None  # noqa: SLF001
    one_station = _peak_mb()
    rows = {"filter": text, **({"max_rows": max_rows} if max_rows else {})}
    outcome, held_rows = "answered", 0
    try:
        result = reader.all(**rows)
        held_rows = result.df.height
    except RowsOverLimitError as error:
        outcome, held_rows = "refused", error.rows
    return {
        "growth_mb": round(_peak_mb() - one_station, 1),
        "peak_mb": round(_peak_mb(), 1),
        "rows": held_rows,
        "stations_read": len(read),
        "outcome": outcome,
    }


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))))  # noqa: T201
