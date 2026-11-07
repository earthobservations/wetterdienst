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

What it says is limited to what is known: the window, and what narrowed the request (`periods`, a run, a lead time,
for the datasets they narrowed). It says nothing of the source being behind for a window that reaches the present:
the library cannot tell a source that is late from one that never reports the parameter (Paris `tx24`), and a
hint of the first invites the retry the warning is there to stop.

The stations whose file the provider let go are told by a `file-skipped` warning (GH-3552), one for the request, which
does invite the retry: what is missing there may well be there later. The stations `parameter-without-rows` leaves
out are those, so it does not repeat `file-skipped`. Which stations it names:

- every station whose file was let go (every collected station for a file all of them are read from), whether the
  station came back empty or `skip_empty` dropped it below its threshold: it is missing for the failure, not for lack of
  data, and a station may carry `station-skipped` besides, for a different cause;
- except the stations a rank walk (`filter_by_rank`) passed over for the next ones, when it filled its `rank`: the
  answer holds as many stations as were asked for, and the ones replaced are not a gap in it. A rank walk that ends
  short (an outage that emptied most of the candidates) names them all.

A request that names its stations by id (`stations=`, `filter_by_station_id`) has a third warning,
`station-without-rows` (GH-3828): the ids that returned no rows while other stations of the request did.

- It is told for that selection alone (a point, a box, a name or a rank has empty stations as the ordinary case, and a
  ranked walk stops early), after a walk read to its end, so that a station never read is never named.
- The stations are in the order of the walk, capped as the other warnings cap theirs.
- A station is named when the answer holds none of its rows: the source holds no readings of it in the window (one that
  begins after the window too), or all of them were null and `drop_nulls` left them out (with `drop_nulls=False` the
  station has rows).
- It leaves out the stations another warning explains, those of `file-skipped` and `station-skipped`, and the ones with
  a row of any requested parameter (a parameter with no row at a station that has others is `parameter-without-rows`'s,
  if no station has it).
- Nothing is told where every station is empty, which `parameter-without-rows` tells where it can, nor for an id the
  network has no station for (`unknown-station`).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING

from wetterdienst.model.metadata import ParameterModel
from wetterdienst.util.response_warnings import (
    FILE_SKIPPED,
    PARAMETER_WITHOUT_ROWS,
    STATION_WITHOUT_ROWS,
    collecting,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from contextlib import AbstractContextManager

    import polars as pl

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.model.request import TimeseriesRequest

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
        asked: Sequence[str] | None = None,
    ) -> None:
        """Hold the request's parameters and the window of the walk; `enabled` False reads nothing and says nothing.

        `asked` is the stations of a request that named them by id, in the order of the walk, and None for any other
        selection (`station-without-rows`).
        """
        self._request = request
        self._enabled = enabled
        self._start = start
        self._end = end
        #: the stations the request named by id, and those the walk handed to the answer (`returned`) or told another
        #: warning of (`explained`: `station-skipped`)
        self._asked = None if asked is None else list(asked)
        self._returned: set[str] = set()
        self._explained: set[str] = set()
        #: the stations whose file the provider let go, in the order they came (a dict for the order): no evidence that
        #: the source holds nothing, and the stations `file-skipped` names
        self._skipped: dict[str, None] = {}
        #: the stations the walk collected, which a file that serves every station of the request was let go for
        self._collected: dict[str, None] = {}
        #: the candidates a rank walk passed over for the next one (an empty frame, or below `skip_threshold`)
        self._passed_over: set[str] = set()
        #: whether the provider let go a file that every station of the request is read from
        self._skipped_all = False
        #: the parameters another warning named while the walk went on (`parameter-ended`)
        self._named: set[str] = set()
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
                self._skipped[station_id] = None

        self._collected[station_id] = None
        return collecting(skipped, self._named)

    def passed_over(self, station_id: str) -> None:
        """Note that a rank walk passed the station over for the next one (an empty frame, or below the threshold).

        `file-skipped` leaves it out if the walk went on to fill its rank (`warn`); only a rank walk replaces a station.
        `parameter-without-rows` leaves it out if its file was let go all the same.
        """
        self._passed_over.add(station_id)

    def returned(self, station_id: str) -> None:
        """Note that the station has rows in the answer: the walk hands them over."""
        self._returned.add(station_id)

    def explained(self, station_id: str) -> None:
        """Note that another warning tells why the station is not in the answer (`station-skipped`)."""
        self._explained.add(station_id)

    def note(self, df: pl.DataFrame) -> None:
        """Note the parameters that a station's rows of the answer are of, in the long form the provider handed over."""
        if not self._enabled or df.is_empty():
            return
        self._with_rows.update(df.select("resolution", "dataset", "parameter").unique().iter_rows())

    def warn(self, *, rank_filled: bool = False) -> None:
        """Tell the stations whose file was let go, and each parameter and dataset that no station read had a row of.

        `rank_filled` is whether a rank walk collected as many stations as it was asked for: the candidates it passed
        over are then replaced, not missing.
        """
        if not self._enabled:
            return
        self._warn_skipped(rank_filled=rank_filled)
        if not self._skipped_all:
            self._warn_without_rows()
        self._warn_stations_without_rows()

    def _warn_stations_without_rows(self) -> None:
        """Tell the stations named by id that have no rows in the answer, once the others do (GH-3828).

        Only an explicit list of ids: for a point, a box, a name or a rank an empty station is the ordinary case and a
        ranked walk stops early. Only after a walk read to its end (`warn` is not reached otherwise), so a station
        never read is never named. Not when no station has rows, which `parameter-without-rows` tells where it can
        (a station that has rows of one parameter and none of another has rows, and is not named). Left out are the
        stations another warning already explains: the file of which was let go (`file-skipped`), and one `skip_empty`
        dropped (`station-skipped`); an id the network has no station for was never in the walk (`unknown-station`).
        """
        if self._asked is None or not self._returned:
            return
        left_go = set(self._collected) if self._skipped_all else set(self._skipped)
        stations = [
            station
            for station in self._asked
            if station not in self._returned and station not in self._explained and station not in left_go
        ]
        if not stations:
            return
        many = len(stations) > 1
        warn_response(
            log,
            STATION_WITHOUT_ROWS,
            f"No rows for {self._where(stations)}{_window(self._start, self._end)}, while the other stations named in "
            f"`stations` have rows: the source holds no readings of {'them' if many else 'it'} there, or "
            f"{'all of them were' if many else 'every reading was'} null and left out (`drop_nulls`).",
            stations=stations[:MAX_STATIONS_LISTED],
        )

    def _warn_without_rows(self) -> None:
        """Tell each parameter and dataset of the request that no station read had a row of, once."""
        request = self._request
        named = request._requested_named  # noqa: SLF001
        whole = request._requested_whole  # noqa: SLF001
        named_datasets = {key[:2] for key in named}
        # a parameter another warning already names (`parameter-ended`) is explained, and not told again
        # (named while this walk collected its stations: the warnings of the response besides are other walks',
        # `parameter-without-rows` among them, and would silence this one)
        explained = self._named
        told_whole: set[tuple[str, str]] = set()
        for parameter in request.parameters:
            if not isinstance(parameter, ParameterModel):
                continue
            key = (parameter.dataset.resolution.name, parameter.dataset.name)
            stations = self._stations_read(parameter.dataset)
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

    def _warn_skipped(self, *, rank_filled: bool) -> None:
        """Tell the stations whose file the provider let go, once: the answer may be missing their values (GH-3552).

        The other side of `parameter-without-rows`, which leaves those stations out because their values may be
        missing for that. A file that serves every station of the request (`whole_request`) is every collected
        station's. The datasets are the ones the walk read at those stations, since the provider says which station
        and not which of its datasets or files; it logs the file itself at level `WARNING`. Nothing is told when no
        file was let go, nor for the candidates a rank walk replaced when it `rank_filled`.
        """
        replaced = self._passed_over if rank_filled else set()
        stations = [
            station for station in (self._collected if self._skipped_all else self._skipped) if station not in replaced
        ]
        if not stations:
            return
        datasets = [
            f"{resolution}/{dataset}"
            for (resolution, dataset), read in self._examined.items()
            if set(stations).intersection(read)
        ]
        of = f" ({', '.join(datasets)})" if datasets else ""
        many = len(stations) > 1
        where = f"{self._where(stations)}{of}"
        if self._skipped_all:
            what = f"A file that every station of the request is read from ({where}) was not used"
        elif many:
            what = f"Files of {where} were not used"
        else:
            what = f"A file of {where} was not used"
        warn_response(
            log,
            FILE_SKIPPED,
            f"{what}: the download was refused or failed, the file was gone, a maintenance page came in its place, "
            f"or it would not parse. The values of {'these stations' if many else 'this station'} may be missing from "
            "the answer, which is partial. Try again later.",
            stations=stations[:MAX_STATIONS_LISTED],
        )

    @staticmethod
    def _where(stations: list[str]) -> str:
        """Name the stations as a warning lists them: all up to the limit, else how many and the first ones."""
        count = len(stations)
        listed = stations[:MAX_STATIONS_LISTED]
        if count == 1:
            return f"station {listed[0]}"
        if count <= MAX_STATIONS_LISTED:
            return f"stations {', '.join(listed)}"
        return f"{count} stations, the first {MAX_STATIONS_LISTED} of them {', '.join(listed)}"

    def _stations_read(self, dataset: DatasetModel) -> list[str]:
        """Give the stations the walk read for a dataset, those whose file was let go left out.

        A station whose file was let go says nothing of what the source holds. (A dataset that needs a window never
        gets here without one: the reader refuses the request, GH-3562.)
        """
        key = (dataset.resolution.name, dataset.name)
        return [station for station in self._examined.get(key, []) if station not in self._skipped]

    def _tell(self, parameter: str, subject: str, stations: list[str], dataset: DatasetModel) -> None:
        """Say that the source has no values for `subject` at `stations`, in the window and as the request narrows."""
        listed = stations[:MAX_STATIONS_LISTED]
        where = self._where(stations)
        narrowed = self._request._narrowed_by(dataset)  # noqa: SLF001
        narrow = f" in {' and in '.join(phrase for phrase, _ in narrowed)}" if narrowed else ""
        hints = [hint for _, hint in narrowed if hint]
        advice = f"{' or '.join(hints).capitalize()}." if hints else "Leave it out, or try another station or window."
        warn_response(
            log,
            PARAMETER_WITHOUT_ROWS,
            f"The source has no values for {subject} at {where}{_window(self._start, self._end)}{narrow}. {advice}",
            parameter=parameter,
            stations=listed,
        )
