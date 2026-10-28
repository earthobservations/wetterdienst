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
- a download failed and the provider went on without it (`downloads_failed`): what is missing may be missing for that,
  which is no statement about the source, and asking again may answer;
- a parameter another warning already names (`parameter-ended`).

What it says is limited to what is known. It does not say that asking again gives the same answer: a window that
reaches the present may be ahead of what the source has published (`It may not have published the latest of them yet`),
and a request that narrowed itself by `periods` or by a run (`issue`) says that it did, and that another period or run
may hold values.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, cast

from wetterdienst.model.metadata import ParameterModel
from wetterdienst.util.response_warnings import (
    PARAMETER_WITHOUT_ROWS,
    downloads_failed,
    recorded_warnings,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    import polars as pl

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.options import Options

log = logging.getLogger(__name__)

#: how many stations the warning lists; a request for a whole network that holds none of a parameter has hundreds
MAX_STATIONS_LISTED = 10


def _utc(moment: dt.datetime) -> str:
    """Write a moment of the window as the minute of its UTC time."""
    return moment.astimezone(dt.UTC).strftime("%Y-%m-%d %H:%M")


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
        #: how many downloads had failed and been let go when the walk began, to tell one that fails in it
        self._failures_before = downloads_failed() if enabled else 0
        #: the stations the walk read, by the dataset they were read for, in the order they came
        self._examined: dict[tuple[str, str], list[str]] = {}
        #: `(resolution, dataset, parameter)` of every row the walk found in the window
        self._with_rows: set[tuple[str, str, str]] = set()

    def examine(self, station_id: str, datasets: Iterable[DatasetModel]) -> None:
        """Note that the station is read for these datasets, which the station index lists it for."""
        if not self._enabled:
            return
        for dataset in datasets:
            stations = self._examined.setdefault((dataset.resolution.name, dataset.name), [])
            if station_id not in stations:
                stations.append(station_id)

    def note(self, df: pl.DataFrame) -> None:
        """Note the parameters that a station's rows of the answer are of, in the long form the provider handed over."""
        if not self._enabled or df.is_empty():
            return
        self._with_rows.update(df.select("resolution", "dataset", "parameter").unique().iter_rows())

    def warn(self) -> None:
        """Tell each parameter and dataset of the request that no station read had a row of, once."""
        # what is missing after a download that failed and was let go may be missing for that
        if not self._enabled or downloads_failed() > self._failures_before:
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
            stations = self._examined.get(key)
            if not stations:
                continue
            if (*key, parameter.name_original) in named:
                if (*key, parameter.name_original) not in self._with_rows:
                    name = f"{key[0]}/{key[1]}/{parameter.name}"
                    if name not in explained:
                        self._tell(name, name, stations)
            elif key in whole and key not in told_whole and key not in named_datasets:
                told_whole.add(key)
                if not any(row[:2] == key for row in self._with_rows):
                    name = f"{key[0]}/{key[1]}"
                    self._tell(name, f"any parameter of {name}", stations)

    def _tell(self, parameter: str, subject: str, stations: list[str]) -> None:
        """Say that the source has no values for `subject` at `stations`, in the window and the periods asked for."""
        count = len(stations)
        listed = stations[:MAX_STATIONS_LISTED]
        if count == 1:
            where = f"station {listed[0]}"
        elif count <= MAX_STATIONS_LISTED:
            where = f"stations {', '.join(listed)}"
        else:
            where = f"{count} stations, the first {MAX_STATIONS_LISTED} of them {', '.join(listed)}"
        window = f" between {_utc(self._start)} and {_utc(self._end)} UTC" if self._start and self._end else ""
        narrowed = self._request._narrowed_by()  # noqa: SLF001
        narrow = f" in {' and in '.join(phrase for phrase, _ in narrowed)}" if narrowed else ""
        if narrowed:
            options = " or ".join(f"`{option}`" for _, option in narrowed)
            advice = (
                f"The request succeeded and this is all the source holds in them: ask without {options}, or for "
                "another one, which may hold values, or for another station or window, or leave it out."
            )
        else:
            advice = (
                "The request succeeded and this is what the source holds now: leave it out, or ask for another "
                "station or window."
            )
        late = " It may not have published the latest of them yet." if self._reaches_the_present(parameter) else ""
        warn_response(
            log,
            PARAMETER_WITHOUT_ROWS,
            f"The source has no values for {subject} at {where}{window}{narrow}. {advice}{late}",
            parameter=parameter,
            stations=listed,
        )

    def _reaches_the_present(self, parameter: str) -> bool:
        """Tell whether the window ends where the source may not have published yet: within the lag of its resolution.

        The lag is the one a station's published end is allowed (`end_lag`): how late a source is known to be.
        A forecast has no such lag: its window lies ahead by design, and it has the run that was asked for.
        """
        from wetterdienst.model.request import end_lag  # noqa: PLC0415

        if self._end is None or hasattr(self._request, "issue"):
            return False
        buffer = cast("Options", self._request.options).station_window_end_buffer
        lag = end_lag(parameter.split("/", maxsplit=1)[0], buffer)
        return self._end > dt.datetime.now(dt.UTC) - lag
