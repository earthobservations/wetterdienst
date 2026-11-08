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
- a parameter another warning already names (`parameter-ended`);
- a parameter whose values the provider left out because they are of another window (`note_left_out`): the source has
  them, and `other-window-left-out` says so, once, with the stations and the dates, for the dataset asked for whole
  as for the parameter asked for by its name;
- a parameter whose values the provider left out because their window had not closed when the request was served
  (`note_open_window`, `returned` false): the source has them, and `window-not-closed` says so, once, with the
  stations and the number of values.

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
Its message names the window and what narrowed the request, as `parameter-without-rows` does, and does not say what
the other stations have: at least one returned rows, but `sql_values` may cut them all away afterwards.

- It is told for that selection alone (a point, a box, a name or a rank has empty stations as the ordinary case, and a
  ranked walk stops early), after a walk read to its end, so that a station never read is never named.
- The stations are in the order of the walk, capped as the other warnings cap theirs.
- A station is named when the answer holds none of its rows: the source holds no readings of it in the window (one that
  begins after the window too), or all of them were null and `drop_nulls` left them out (with `drop_nulls=False` the
  station has rows).
- It leaves out the stations another warning explains, those of `file-skipped`, `station-skipped`,
  `other-window-left-out` (the source holds values of them, of another series) and `window-not-closed` (of a window
  that had not closed, left out), and the ones with
  a row of any requested parameter (a parameter with no row at a station that has others is `parameter-without-rows`'s,
  if no station has it).
- Nothing is told where every station is empty, which `parameter-without-rows` tells where it can, nor for an id the
  network has no station for (`unknown-station`).

An estimate (`interpolate`, `summarize`) reads the stations around a point as candidates and none of the above applies
to it: a station without a parameter is the ordinary case, and a walk that stops once it has enough stations never
reaches `warn`. What its walk left out at the stations it read is told by `EstimateLeftOut`, as one
`source-data-left-out` warning for the answer, with the cause and how many stations (GH-3848).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import TYPE_CHECKING

from wetterdienst.metadata.period import Period
from wetterdienst.model.metadata import ParameterModel
from wetterdienst.util.response_warnings import (
    FILE_SKIPPED,
    OTHER_WINDOW_LEFT_OUT,
    PARAMETER_WITHOUT_ROWS,
    SOURCE_DATA_LEFT_OUT,
    STATION_WITHOUT_ROWS,
    WINDOW_NOT_CLOSED,
    advise_on_skip_causes,
    collecting,
    tell_details,
    tell_skip_causes,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from contextlib import AbstractContextManager

    import polars as pl

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.util.response_warnings import SkipCause

log = logging.getLogger(__name__)

#: how many stations the warning lists; a request for a whole network that holds none of a parameter has hundreds
MAX_STATIONS_LISTED = 10

#: the phrase of `_narrowed_by` that names the periods asked for, of which each dataset of a request may give a set
_PERIODS_PHRASE = re.compile(r"the periods asked for \((.+)\)")


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
        nulls_dropped: bool = True,
        left_out: EstimateLeftOut | None = None,
    ) -> None:
        """Hold the request's parameters and the window of the walk; `enabled` False reads nothing and says nothing.

        `asked` is the stations of a request that named them by id, in the order of the walk, and None for any other
        selection (`station-without-rows`); `nulls_dropped` is whether the answer leaves rows without a value out
        (`drop_nulls` in the long shape), which a station named in it may have been emptied by. `left_out` is the
        tally of an estimate, told what each station collected lets go, whether `enabled` or not.
        """
        self._request = request
        self._enabled = enabled
        self._start = start
        self._end = end
        #: the stations the request named by id, and those the walk handed to the answer (`returned`) or told another
        #: warning of (`explained`: `station-skipped`, `other-window-left-out`)
        self._asked = None if asked is None else list(asked)
        self._nulls_dropped = nulls_dropped
        self._estimate = left_out
        self._returned: set[str] = set()
        self._explained: set[str] = set()
        #: the stations whose file the provider let go, in the order they came (a dict for the order): no evidence that
        #: the source holds nothing, and the stations `file-skipped` names
        self._skipped: dict[str, None] = {}
        #: why the provider let go the files of each station, and the file every station is read from, in the order the
        #: causes came (dicts for the order): what the advice of `file-skipped` is worded by
        self._skip_causes: dict[str, dict[SkipCause, None]] = {}
        self._skip_causes_of_all: dict[SkipCause, None] = {}
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
        #: the dates a provider left out for the rows of another window (`note_left_out`), by parameter
        #: (`resolution/dataset/parameter`) and then by station, and the clause that says which series it was
        self._left_out: dict[str, dict[str, int]] = {}
        self._left_out_because: dict[str, str] = {}
        #: the values a provider found of a window that had not closed (`note_open_window`), by parameter and then by
        #: station, the earliest time a window of them closes, and whether the provider returned them (marked) or left
        #: them out
        self._open: dict[str, dict[str, int]] = {}
        self._open_closes: dict[str, dt.datetime] = {}
        self._open_returned: dict[str, bool] = {}

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

        def skipped(whole_request: bool, cause: SkipCause) -> None:  # noqa: FBT001
            if whole_request:
                self._skipped_all = True
                self._skip_causes_of_all[cause] = None
            else:
                self._skipped[station_id] = None
                self._skip_causes.setdefault(station_id, {})[cause] = None
            if self._estimate is not None:
                self._estimate.skipped(station_id, whole_request=whole_request)

        def left_out(parameter: str, count: int, because: str) -> None:
            stations = self._left_out.setdefault(parameter, {})
            stations[station_id] = stations.get(station_id, 0) + count
            self._left_out_because[parameter] = because
            if self._estimate is not None:
                self._estimate.left_out(station_id, parameter, count)
            # the source has values there: `parameter-without-rows` must not say it has none, nor
            # `station-without-rows` that the station has no values of it: `other-window-left-out` says why
            self._named.add(parameter)
            self._explained.add(station_id)

        def open_window(parameter: str, count: int, closes: dt.datetime, returned: bool) -> None:  # noqa: FBT001
            stations = self._open.setdefault(parameter, {})
            stations[station_id] = stations.get(station_id, 0) + count
            self._open_closes[parameter] = min(closes, self._open_closes.get(parameter, closes))
            self._open_returned[parameter] = returned
            if not returned and self._estimate is not None:
                self._estimate.open_window(station_id, parameter, count)
            if not returned:
                # the source has values there, left out: no `parameter-without-rows`, no `station-without-rows`
                self._named.add(parameter)
                self._explained.add(station_id)

        self._collected[station_id] = None
        if self._estimate is not None:
            self._estimate.collected(station_id)
        return collecting(skipped, self._named, left_out, open_window)

    def rejected(self, station_id: str, count: int, by_check: dict[str, int]) -> None:
        """Tell an estimate how many values of the station a hard plausibility check made null, by check."""
        if self._estimate is not None:
            self._estimate.rejected(station_id, count, by_check)

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
        """Note that another warning tells why the station is not in the answer (`station-skipped` and the like)."""
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
        self._warn_left_out()
        self._warn_open_window()
        if not self._skipped_all:
            self._warn_without_rows()
        self._warn_stations_without_rows()

    def _warn_stations_without_rows(self) -> None:
        """Tell the stations named by id that have no rows in the answer, once others have (GH-3828).

        Only an explicit list of ids: for a point, a box, a name or a rank an empty station is the ordinary case and a
        ranked walk stops early. Only after a walk read to its end (`warn` is not reached otherwise), so a station
        never read is never named. Not when no station has rows, which `parameter-without-rows` tells where it can
        (a station that has rows of one parameter and none of another has rows, and is not named). Left out are the
        stations another warning already explains: the file of which was let go (`file-skipped`), and one `skip_empty`
        dropped (`station-skipped`), or whose values were left out for another window (`other-window-left-out`); an id
        the network has no station for was never in the walk (`unknown-station`).

        The message says nothing of the other stations (`sql_values`, which cuts rows afterwards, may leave none of them
        with rows in the answer), but what narrowed the request (`periods`, a run, a lead time) as
        `parameter-without-rows` does, since the values may be in what it left out. `there` refers to the window or to
        what narrowed the request, so a request with neither says none.
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
        window = _window(self._start, self._end)
        phrases, hints = self._narrowing()
        narrow = f" in {' and in '.join(phrases)}" if phrases else ""
        why = f"The source holds no values of {'them' if many else 'it'}{' there' if window or phrases else ''}"
        if self._nulls_dropped:
            why += f", or {'all of them were' if many else 'every value was'} null and left out (`drop_nulls`)"
        advice = f" {' or '.join(hints).capitalize()}." if hints else ""
        warn_response(
            log,
            STATION_WITHOUT_ROWS,
            f"No rows for {self._where(stations)}{window}{narrow}. {why}.{advice}",
            stations=stations[:MAX_STATIONS_LISTED],
        )

    def _narrowing(self) -> tuple[list[str], list[str]]:
        """Give what narrowed the request for any of its datasets, as phrases and hints, each once (`_narrowed_by`).

        The periods that datasets were each narrowed to are one phrase, naming all of them.
        """
        phrases: dict[str, None] = {}
        periods: set[Period] = set()
        hints: dict[str, None] = {}
        seen: set[tuple[str, str]] = set()
        for parameter in self._request.parameters:
            if not isinstance(parameter, ParameterModel):
                continue
            key = (parameter.dataset.resolution.name, parameter.dataset.name)
            if key in seen:
                continue
            seen.add(key)
            for phrase, hint in self._request._narrowed_by(parameter.dataset):  # noqa: SLF001
                if match := _PERIODS_PHRASE.fullmatch(phrase):
                    periods.update(Period(name) for name in match.group(1).split(", "))
                    phrase = "the periods asked for"
                phrases[phrase] = None
                if hint:
                    hints[hint] = None
        if "the periods asked for" in phrases:
            named = ", ".join(period.value for period in sorted(periods))
            phrases = {
                (f"the periods asked for ({named})" if phrase == "the periods asked for" else phrase): None
                for phrase in phrases
            }
        return list(phrases), list(hints)

    def _warn_left_out(self) -> None:
        """Tell, for each parameter a provider left the rows of another window out of, the stations and the dates.

        The source holds values for those dates, which the answer does not have, and it is no gap in the source: the
        values are another window's and would be wrong under the parameter's name. One warning for each parameter,
        with the stations (the first ten) and the dates counted at each. A station whose rows were the candidate of a
        rank walk that passed it over for the next is still named: the dates were left out of its frame.
        """
        for parameter, stations in self._left_out.items():
            listed = list(stations)[:MAX_STATIONS_LISTED]
            dates = ", ".join(f"{station} {stations[station]}" for station in listed)
            more = f", and {len(stations) - len(listed)} more" if len(stations) > len(listed) else ""
            total = sum(stations.values())
            these = "dates that are" if total != 1 else "date that is"
            warn_response(
                log,
                OTHER_WINDOW_LEFT_OUT,
                f"The source has values of {parameter} on {total} {these} not in the answer ({dates}{more}): "
                f"{self._left_out_because[parameter]}. They are not missing at the source, and the answer has no row "
                "for them rather than a value of another window under this name.",
                parameter=parameter,
                stations=listed,
            )

    def _warn_open_window(self) -> None:
        """Tell, for each parameter whose values are of a window that had not closed, the stations and the values.

        The source serves the value of a period that is still going on and marks nothing (`note_open_window`): it may
        still change. A value left out is not missing at the source, and a value returned is marked in its
        `quality_flags`. One warning for each parameter, with the stations (the first ten) and the values counted at
        each, and the time the earliest of the windows closes (UTC).
        """
        for parameter, stations in self._open.items():
            listed = list(stations)[:MAX_STATIONS_LISTED]
            counts = ", ".join(f"{station} {stations[station]}" for station in listed)
            more = f", and {len(stations) - len(listed)} more" if len(stations) > len(listed) else ""
            total = sum(stations.values())
            closes = self._open_closes[parameter].astimezone(dt.UTC)
            when = f"{closes:%Y-%m-%d %H:%M} UTC"
            if self._open_returned[parameter]:
                message = (
                    f"{total} {'value' if total == 1 else 'values'} of {parameter} ({counts}{more}) "
                    f"{'is' if total == 1 else 'are'} of a window that had not closed when the request was served "
                    f"(the earliest closes at {when}): {'it is' if total == 1 else 'they are'} in the answer, marked "
                    "`completeness:Incomplete` in `quality_flags`, and may still change. The source does not mark "
                    "them. Ask again once the window has closed for the final value."
                )
            else:
                message = (
                    f"{total} {'value' if total == 1 else 'values'} of {parameter} ({counts}{more}) "
                    f"{'is' if total == 1 else 'are'} left out of the answer: the window had not closed when the "
                    f"request was served (the earliest closes at {when}), so {'it is' if total == 1 else 'they are'} "
                    "partial and may still change, and the source does not mark them. They are not missing at the "
                    "source: ask again once the window has closed."
                )
            warn_response(log, WINDOW_NOT_CLOSED, message, parameter=parameter, stations=listed)

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
                # a parameter of it that has values the answer left out (`other-window-left-out`) is a dataset the
                # source holds values of
                held_back = any(
                    name.startswith(f"{key[0]}/{key[1]}/")
                    for name in (*self._left_out, *(name for name, back in self._open_returned.items() if not back))
                )
                if not held_back and not any(row[:2] == key for row in self._with_rows):
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
        causes = [
            *self._skip_causes_of_all,
            *(cause for station in stations for cause in self._skip_causes.get(station, ())),
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
            f"{what}: {tell_skip_causes(causes)}. The values of "
            f"{'these stations' if many else 'this station'} may be missing from the answer, which is partial. "
            f"{advise_on_skip_causes(causes)}",
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


#: what a window of a resolution is called in the warning of an estimate, by the resolution of the parameter
_OPEN_WINDOWS = {"daily": "today", "monthly": "this month", "annual": "this year"}


class EstimateLeftOut:
    """What the walk of an estimate left out at the stations it read, told as one warning for the answer (GH-3848).

    `interpolate` and `summarize` read the stations around a point as candidates, nearest first, until they have enough,
    and neither `file-skipped` nor `other-window-left-out` is told of a station there (`ParameterRows.warn` is reached
    by a walk read to its end, which an estimate stops). The walk hands each station it reads to this (the
    `ParameterRows` of `TimeseriesValues.query`, as `ParameterRows.collecting` is told by the provider) and the
    estimate calls `warn` once the walk is over, so that the answer says that source data was left out, by which cause
    and at how many stations, and never once for each station:

    - `file-skipped`'s cause: the provider let a file go (a refused or failed download, a file withdrawn since the
      listing, a maintenance page, a file that would not parse, a directory found empty), so the station's values may be
      missing; a file that every station is read from (`whole_request`) is every station's.
    - `other-window-left-out`'s: dates of a parameter that only another series of the source has, which are no missing
      data and are left out so that a value of another window is not given under this parameter's name; counted in dates
      for each parameter.
    - `window-not-closed`'s, for the values the provider left out of the answer (`note_open_window`, `returned`
      false): values of a window that had not closed yet (today, this month, this year), counted in values for each
      resolution. An estimate cannot carry the incomplete mark of a value the source serves before its window closes,
      so the provider leaves those out of an estimate (`metno/frost`: the month and the year too, which `values`
      returns marked) and they are told here (GH-3883).
    - `rejected-by-plausibility`'s: values a hard plausibility check made null (`REJECTED_TOKEN`), counted in values and
      by check. What a soft check flags (`suspect:`) is left out by the estimate itself, whatever the mode, and is not
      counted here.

    One warning holds the causes: a caller of an estimate asks one question of it (is the answer made from all that
    the source holds?), and the warning is for that question; a values request keeps its codes. It carries the stations
    that were affected, the first ten.

    The estimate stops at the first station it reads that it does not need (`collection_is_done`), and that station was
    read all the same: `forget` leaves it out, as the answer is not made of it. So is a station read after the answer
    was complete that the walk passed over for want of rows (the usual shape of a lost file), which never reaches the
    estimate: `mark` and `forget_since` leave out those of the stations read since the last one the estimate used.
    """

    def __init__(self) -> None:
        """Start with nothing read."""
        self._collected: dict[str, None] = {}
        self._files: dict[str, None] = {}
        #: the stations that let go a file every station is read from: it is every station's while one of them stays
        self._files_of_all: set[str] = set()
        #: the dates left out, by parameter (`resolution/dataset/parameter`) and then by station
        self._dates: dict[str, dict[str, int]] = {}
        #: the values a hard check made null, by station: the count, and the count by check
        self._rejected: dict[str, tuple[int, dict[str, int]]] = {}
        #: the values of a window that had not closed that the provider left out, by what the window is (`today`, ...)
        #: and then by station
        self._open: dict[str, dict[str, int]] = {}

    def collected(self, station_id: str) -> None:
        """Note that the walk reads the station, which a file that serves every station was let go for."""
        self._collected[station_id] = None

    def skipped(self, station_id: str, *, whole_request: bool) -> None:
        """Note that the provider let a file go while the station was read."""
        if whole_request:
            self._files_of_all.add(station_id)
        else:
            self._files[station_id] = None

    def left_out(self, station_id: str, parameter: str, count: int) -> None:
        """Note that the provider left `count` dates of `parameter` out of the station: they are of another series."""
        stations = self._dates.setdefault(parameter, {})
        stations[station_id] = stations.get(station_id, 0) + count

    def open_window(self, station_id: str, parameter: str, count: int) -> None:
        """Note that the provider left `count` values of `parameter` out of the station: their window had not closed.

        ``parameter`` is `resolution/dataset/parameter`, and its resolution says which window it was.
        """
        window = _OPEN_WINDOWS.get(parameter.split("/", maxsplit=1)[0], "the current period")
        stations = self._open.setdefault(window, {})
        stations[station_id] = stations.get(station_id, 0) + count

    def rejected(self, station_id: str, count: int, by_check: dict[str, int]) -> None:
        """Note that a hard plausibility check made `count` values of the station null, `by_check` for each check."""
        if count > 0:
            self._rejected[station_id] = (count, dict(by_check))

    def mark(self) -> int:
        """Give the number of stations read so far, for `forget_since`."""
        return len(self._collected)

    def forget_since(self, mark: int, is_done: Callable[[str], bool]) -> None:
        """Leave out each station read since `mark` for which the estimate was done, as it was at that station.

        The walk hands the estimate the stations that have rows. One that has none is read and passed over, and stands
        between the last station the estimate used (`mark` was taken after it) and the one it stopped at, or the end of
        the walk. Where `is_done` holds for such a station, as it does for the one the walk stopped at, the walk would
        have stopped there had it had rows, and its loss is none to the answer. A station passed over before that
        stays counted: the answer was not complete, and it may have been the one to complete it.
        """
        for station in list(self._collected)[mark:]:
            if is_done(station):
                self.forget(station)

    def forget(self, station_id: str) -> None:
        """Leave out a station the walk read and the estimate did not use, as it lost the answer nothing.

        That is the station the estimate stopped at, and, through `forget_since`, a station passed over for want of rows
        once the answer was complete.
        """
        self._collected.pop(station_id, None)
        self._files.pop(station_id, None)
        self._files_of_all.discard(station_id)
        self._rejected.pop(station_id, None)
        for stations in self._dates.values():
            stations.pop(station_id, None)
        self._dates = {parameter: stations for parameter, stations in self._dates.items() if stations}
        for stations in self._open.values():
            stations.pop(station_id, None)
        self._open = {window: stations for window, stations in self._open.items() if stations}

    def warn(self) -> None:
        """Tell, in one warning, what was left out and at how many of the stations read; nothing if nothing was."""
        files = list(self._collected if self._files_of_all else self._files)
        other = [station for station in self._collected if any(station in dates for dates in self._dates.values())]
        rejected = [station for station in self._collected if station in self._rejected]
        open_ = [station for station in self._collected if any(station in windows for windows in self._open.values())]
        affected = [
            station
            for station in self._collected
            if station in files or station in other or station in rejected or station in open_
        ]
        if not affected:
            return
        read = len(self._collected)
        sentences = [f"Source data was left out of this estimate at {len(affected)} of the {read} stations it read."]
        if other:
            dates = ", ".join(f"{sum(stations.values())} of {parameter}" for parameter, stations in self._dates.items())
            sentences.append(
                f"Dates of another series of the source were left out at {self._count(other)}: {dates}. "
                "The source holds values for them, so nothing is missing there, but they are not read: a value of "
                "another window would be wrong under the parameter's name."
            )
        if open_:
            total = sum(sum(stations.values()) for stations in self._open.values())
            windows = ", ".join(f"{sum(stations.values())} for {window}" for window, stations in self._open.items())
            one = total == 1
            sentences.append(
                f"{total} {'value' if one else 'values'} at {self._count(open_)} "
                f"{'was' if one else 'were'} of a window that had not closed yet ({windows}) and "
                f"{'is' if one else 'are'} left out: {'it is' if one else 'they are'} partial and may "
                f"still change, and the source does not mark {'it' if one else 'them'}. "
                f"{'It is' if one else 'They are'} not missing at the source and {'comes' if one else 'come'} back "
                "once the window has closed."
            )
        if rejected:
            total = sum(self._rejected[station][0] for station in rejected)
            checks: dict[str, int] = {}
            for station in rejected:
                for check, number in self._rejected[station][1].items():
                    checks[check] = checks.get(check, 0) + number
            sentences.append(
                f"{total} values at {self._count(rejected)} were numbers a plausibility check rejected "
                f"({tell_details(checks)}; a value several checks rejected is counted under each) and are not used."
            )
        if files:
            sentences.append(
                "A file the provider could not use (a refused or failed download, a file withdrawn since the listing, "
                "a maintenance page, a file that would not parse, or a directory found empty) was left out at "
                f"{self._count(files)}: the values of {'these stations' if len(files) > 1 else 'this station'} may be "
                "missing from the estimate. A failed download, a withdrawn file, a maintenance page and an empty "
                "directory may be back later, so try again; a refused download or a file that would not parse mostly "
                "stays as it is, and is worth reporting to the provider."
            )
        warn_response(log, SOURCE_DATA_LEFT_OUT, " ".join(sentences), stations=affected[:MAX_STATIONS_LISTED])

    @staticmethod
    def _count(stations: list[str]) -> str:
        """Give the number of stations and name them: all up to the limit, else the first ones."""
        count = len(stations)
        listed = ", ".join(stations[:MAX_STATIONS_LISTED])
        if count == 1:
            return f"1 station ({listed})"
        if count <= MAX_STATIONS_LISTED:
            return f"{count} stations ({listed})"
        return f"{count} stations (the first {MAX_STATIONS_LISTED} of them {listed})"
