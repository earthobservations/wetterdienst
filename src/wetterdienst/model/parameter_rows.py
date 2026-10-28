# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Which of the parameters a request names the source held no values for (GH-3539).

A request for a parameter at a station that has none of it is answered with a header and no rows, which is what the
source holds (Los Angeles has no `TX` in MOSMIX, Paris no `tx24` in the synop reports) and reads exactly like a
request that failed. `ParameterRows` watches the walk of `TimeseriesValues.query` and, when it is over, says so by a
`parameter-without-rows` warning that names the parameter and the stations, so that a caller knows that the request
did not fail and that what it asked for is not in the source at the moment.

When it fires, for each parameter of the request:

- a parameter asked for by its name (`resolution/dataset/parameter`) has a warning when no station of the answer has a
  row of it in the window, and not when any one has. The stations named are the ones the walk read.
- a dataset asked for whole (`resolution/dataset`) has a warning only when no station has a row of any parameter of it.
  A dataset that has rows is not told parameter by parameter: that would be dozens of lines about what the source
  does not hold for one of its stations.
- one warning for each parameter or dataset, with all its stations, not one for each station.

A row is a row of the answer, so a parameter whose readings were all null and left with `drop_nulls` has none. A station
counts only for the datasets its index lists it for, and only if the window reaches its record (`start_timestamp`),
and one skipped for having too few readings (`skip_empty`) had rows.

It is not told where it would say what is not so:

- the walk was not read to its end, or the request failed and raised;
- a station whose file the provider let go (`note_skipped_download`) is not one of the stations it names, as its
  missing values may be missing for that: the other stations still count, and where none is left nothing is said;
- a parameter another warning already names (`parameter-ended`).

What it says is limited to what is known: the window, what narrowed the request (`periods`, a run, a lead time, for the
datasets they narrowed), and that the source may not have published a window that reaches the present yet. A window
that a narrowing explains gets no such note.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, cast

from wetterdienst.model.metadata import ParameterModel
from wetterdienst.util.response_warnings import (
    PARAMETER_WITHOUT_ROWS,
    collecting,
    recorded_warnings,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextlib import AbstractContextManager

    import polars as pl

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.options import Options

log = logging.getLogger(__name__)

#: how many stations the warning lists; a request for a whole network that holds none of a parameter has hundreds
MAX_STATIONS_LISTED = 10


def _window(start: dt.datetime | None, end: dt.datetime | None) -> str:
    """Write the window as days where it is whole days of UTC, else as the minutes of its ends, and nothing if none."""
    if start is None or end is None:
        return ""
    start, end = start.astimezone(dt.UTC), end.astimezone(dt.UTC)
    if (start.hour, start.minute) == (0, 0) and (end.hour, end.minute) == (23, 59):
        if start.date() == end.date():
            return f" on {start:%Y-%m-%d}"
        return f" from {start:%Y-%m-%d} to {end:%Y-%m-%d}"
    return f" from {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC"


class ParameterRows:
    """What a walk over the stations of a request read, to tell what of the request has no rows in it."""

    def __init__(
        self,
        request: TimeseriesRequest,
        start: dt.datetime | None,
        end: dt.datetime | None,
        *,
        enabled: bool = True,
    ) -> None:
        """Hold the request's parameters and the window of the walk; `enabled` False reads nothing and says nothing."""
        self._request = request
        self._enabled = enabled
        self._start = start
        self._end = end
        #: the stations whose file the provider let go, which are no evidence that the source holds nothing
        self._skipped: set[str] = set()
        #: whether the provider let go a file that every station of the request is read from
        self._skipped_all = False
        #: the stations the walk read, by the dataset they were read for, in the order they came
        self._examined: dict[tuple[str, str], list[str]] = {}
        #: `(resolution, dataset, parameter)` of every row the walk found in the window
        self._with_rows: set[tuple[str, str, str]] = set()

    def examine(self, station_id: str, datasets: Iterator[DatasetModel] | list[DatasetModel]) -> None:
        """Note that the station is read for these datasets, which the station index lists it for."""
        if not self._enabled:
            return
        for dataset in datasets:
            stations = self._examined.setdefault((dataset.resolution.name, dataset.name), [])
            if station_id not in stations:
                stations.append(station_id)

    def collecting(self, station_id: str) -> AbstractContextManager[None]:
        """Watch the collection of one station for a file the provider lets go (`note_skipped_download`)."""

        def skipped(whole_request: bool) -> None:  # noqa: FBT001
            if whole_request:
                self._skipped_all = True
            else:
                self._skipped.add(station_id)

        return collecting(skipped)

    def note(self, df: pl.DataFrame) -> None:
        """Note the parameters that a station's rows of the answer are of, in the long form the provider handed over."""
        if not self._enabled or df.is_empty():
            return
        self._with_rows.update(df.select("resolution", "dataset", "parameter").unique().iter_rows())

    def warn(self) -> None:
        """Tell each parameter and dataset of the request that no station read had a row of, once."""
        if not self._enabled or self._skipped_all:
            return
        request = self._request
        named = request._requested_named  # noqa: SLF001
        whole = request._requested_whole  # noqa: SLF001
        named_datasets = {key[:2] for key in named}
        # a parameter another warning already names (`parameter-ended`) is explained, and not told again
        explained = {warning.get("parameter") for warning in recorded_warnings()}
        told_whole: set[tuple[str, str]] = set()
        for parameter in request.parameters:
            if not isinstance(parameter, ParameterModel):
                continue
            key = (parameter.dataset.resolution.name, parameter.dataset.name)
            # a station whose file was let go says nothing of what the source holds
            stations = [station for station in self._examined.get(key, []) if station not in self._skipped]
            if not stations:
                continue
            if (*key, parameter.name_original) in named:
                if (*key, parameter.name_original) not in self._with_rows:
                    name = f"{key[0]}/{key[1]}/{parameter.name}"
                    if name not in explained:
                        self._tell(name, name, stations, parameter.dataset)
            elif key in whole and key not in told_whole and key not in named_datasets:
                told_whole.add(key)
                if not any(row[:2] == key for row in self._with_rows):
                    name = f"{key[0]}/{key[1]}"
                    self._tell(name, f"any parameter of {name}", stations, parameter.dataset)

    def _tell(self, parameter: str, subject: str, stations: list[str], dataset: DatasetModel) -> None:
        """Say that the source has no values for `subject` at `stations`, in the window and as the request narrows."""
        count = len(stations)
        listed = stations[:MAX_STATIONS_LISTED]
        if count == 1:
            where = f"station {listed[0]}"
        elif count <= MAX_STATIONS_LISTED:
            where = f"stations {', '.join(listed)}"
        else:
            where = f"{count} stations, the first {MAX_STATIONS_LISTED} of them {', '.join(listed)}"
        narrowed = self._request._narrowed_by(dataset)  # noqa: SLF001
        narrow = f" in {' and in '.join(phrase for phrase, _ in narrowed)}" if narrowed else ""
        hints = [hint for _, hint in narrowed if hint]
        if hints:
            advice = f"{' or '.join(hints).capitalize()}."
        elif self._reaches_the_present(dataset.resolution.name):
            advice = "The source may not have published this window yet; try again later."
        else:
            advice = "Leave it out, or try another station or window."
        warn_response(
            log,
            PARAMETER_WITHOUT_ROWS,
            f"The source has no values for {subject} at {where}{_window(self._start, self._end)}{narrow}. {advice}",
            parameter=parameter,
            stations=listed,
        )

    def _reaches_the_present(self, resolution: str) -> bool:
        """Tell whether the window ends where the source may not have published yet: within the lag of its resolution.

        The lag is the one a station's published end is allowed (`end_lag`): how late a source is known to be.
        A forecast has no such lag: its window lies ahead by design, and it has the run that was asked for.
        """
        from wetterdienst.model.request import end_lag  # noqa: PLC0415

        if self._end is None or hasattr(self._request, "issue"):
            return False
        buffer = cast("Options", self._request.options).station_window_end_buffer
        lag = end_lag(resolution, buffer)
        return self._end > dt.datetime.now(dt.UTC) - lag
