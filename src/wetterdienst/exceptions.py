# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Custom exceptions for the wetterdienst library.

Every class here derives from `WetterdienstError`, so a caller can catch the library's own
exceptions with one `except` (a plain `ValueError` or `KeyError` raised for a bad argument is not
one of them yet), and the REST API, the MCP tools and the
command line can tell what to answer from the class instead of keeping a list of them::

    WetterdienstError
    ├── RequestError      the request cannot be served as phrased (a `ValueError`)
    ├── NotFoundError     what the request names does not exist (a `LookupError`)
    ├── ConfigurationError  this installation is not set up to serve it
    ├── UpstreamError     the provider's side failed or sent what the parser does not expect
    ├── ExportRefusedError  a sink will not perform the export it was asked for
    └── ImageTimeoutError   the browser that draws an image did not finish in time (also a `TimeoutError`)

Each class that was an exception of its own before keeps the built-in classes it derived from, so an
`except ValueError`, `except OSError`, `except FileNotFoundError` or `except IndexError` that caught
it still does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self


class WetterdienstError(Exception):
    """Root of the exception classes of wetterdienst.

    Not raised itself. An error the library did not name -- a defect, a failure of a library
    underneath that is not mapped to one of these -- is not a `WetterdienstError`, and the REST API
    answers one that is a subclass of this and of none of the below with a 500, the server's error.
    """


class RequestError(WetterdienstError, ValueError):
    """Raised when the request cannot be served as phrased, and the caller can rephrase it.

    A `ValueError`, which is what these refusals have been. The REST API answers it with a 400 and
    the command line with a usage error, exit 2.
    """


class NotFoundError(WetterdienstError, LookupError):
    """Raised when something the request names does not exist: a provider, a network, a station, an issue.

    A `LookupError`. The REST API answers it with a 404 and the command line with a usage error.
    """


class ConfigurationError(WetterdienstError):
    """Raised when this installation is not set up to serve what was asked, and the caller cannot change that.

    A missing or rejected credential, or a missing optional dependency: the request was well formed, whoever runs the
    process has to act. The REST API answers it with a 501 and does not repeat the message, which
    names a setting or a package of the server.
    """


class UpstreamError(WetterdienstError):
    """Raised when the provider's side failed: it did not answer, or sent what the parser does not expect.

    Not the caller's mistake, and not ours either: the REST API answers it with a 502, a 503 for a
    provider it could not connect to (`NoInternetError`) and a 504 for one that did not answer in
    time (a timeout on the `__cause__` of a `DownloadError`), and the command line keeps its
    traceback.
    """


class InvalidEnumerationError(RequestError):
    """Raised when an invalid enumeration is provided."""


class InvalidParameterError(RequestError):
    """Raised when a requested parameter is unknown to the provider or not shaped like a parameter.

    The message names each one with the close match, where there is one, and the names that would
    have matched. Raised by default; a request built with `on_unknown="warn"` logs it and goes on
    with the parameters that did resolve.

    `resolved` says whether any other parameter of the request did resolve, that is whether
    `on_unknown="warn"` would have gone on with something.
    """

    resolved: bool = False


class NoParametersFoundError(RequestError):
    """Raised when no parameters are found."""


class NoPeriodsFoundError(RequestError):
    """Raised when none of the requested periods is published for the requested datasets."""


class MetaFileNotFoundError(UpstreamError, FileNotFoundError):
    """Raised when a meta file is not found."""


class MetaFileFormatError(UpstreamError, ValueError):
    """Raised when a meta file does not match the expected format."""


class ProductFileNotFoundError(UpstreamError, FileNotFoundError):
    """Raised when a product file is not found."""


class StartDateEndDateError(RequestError):
    """Raised when the start date is after the end date."""


class InvalidTimeIntervalError(RequestError):
    """Raised when an invalid time interval is provided."""


class ReversedTimeIntervalError(StartDateEndDateError):
    """Raised when a request's window ends before it starts.

    Told apart from its parent so that the REST API, the MCP tools and the command line, whose callers
    pass the window as ``timestamp`` or ``--timestamp`` / ``--start`` / ``--end`` and know nothing of a
    request's ``start`` and ``end``, can word the refusal their own way. Python callers get the
    request's message.
    """


class MissingTimeIntervalError(InvalidTimeIntervalError):
    """Raised when a computation that needs a window of time is given none.

    Told apart from its parent for the same reason as `ReversedTimeIntervalError`.
    """


class DateRequiredError(MissingTimeIntervalError, StartDateEndDateError):
    """Raised when a dataset that is queried by a window is requested without one.

    Told apart from its parents for the same reason as `ReversedTimeIntervalError`. It is also a
    `StartDateEndDateError`, which is what this refusal was before, so that a caller catching that
    still catches it.
    """


class InvalidBoundingBoxError(RequestError):
    """Raised when a bounding box's borders are given the wrong way round."""


class LocationOutOfRangeError(RequestError):
    """Raised when a location lies outside the range a computation covers."""


class IssueNotFoundError(NotFoundError, IndexError):
    """Raised when a forecast run is asked for by an issue time the source does not list."""


class NotEnoughDataError(RequestError):
    """Raised when what a request selects holds too little data to answer it."""


class ProviderNotFoundError(NotFoundError):
    """Raised when a provider is not found in the provider list."""


class StationNotFoundError(NotFoundError):
    """Raised when a station is not found in the station list."""


class ApiNotFoundError(NotFoundError):
    """Raised when an API is not found in the API list."""


class MetadataNotFoundError(NotFoundError):
    """Raised when a resolution or dataset is asked about that the provider does not have."""


class NoInternetError(UpstreamError, OSError):
    """Raised when no connection to the provider could be made: no network, a failed name lookup, a refusing host.

    Raised by every download and every listing, for every provider, station catalogues included: an
    offline library does not answer with an empty frame, which a scheduled job cannot tell from a
    source that has no data (GH-2640). The message names the URL, without its query or user
    information, and the connection error underneath is its `__cause__`.

    Told apart from `DownloadError`, which is a source that answered badly -- a 4xx or 5xx, a
    timeout, a body cut short -- and from an empty listing, which is an answer. A caller that
    prefers an empty result when offline catches it::

        try:
            df = request.all().df
        except NoInternetError:
            df = pl.DataFrame()

    The REST API answers it with a 503, and the command line prints it as one line, exit 1.
    """


class DownloadError(UpstreamError):
    """Raised when a download failed, saying which file it was and why.

    The failure a download met is on `__cause__`, as the exception it was: a timeout, a response
    error, a dropped connection. Catch this to handle any of them, or read `__cause__` to tell them
    apart.

    `url` is the address without its query, fragment or user information, which can carry a key or
    a password; it is what the message shows. Held in `args`, so the error pickles.
    """

    def __init__(self, url: str, reason: str) -> None:
        """Initialize the error with the address that failed and why."""
        super().__init__(url, reason)
        self.url = url
        self.reason = reason

    def __str__(self) -> str:
        """Say which file failed to download, and how."""
        return f"Failed to download {self.url}: {self.reason}"


class StationListingIncompleteError(UpstreamError):
    """Raised when a station is not found while the lookup of the stations went without a listing of the provider.

    `dwd/observation` and `dwd/derived` look the stations up in directories of DWD's server, and go on without one
    that came back empty or missing, or that lists no description of its stations: the answer is partial, and says so
    with a `file-skipped` warning. An estimate (`interpolate`, `summarize`) or the stripes ask for one station by its
    id, and have no answer to put the warning in. A station that is not found then may be unknown, or one that only
    the skipped directory lists: the request is valid, the cause is upstream, and a 404 would say that the station
    does not exist. So it is this, a 502 over REST, which names the directories.

    `station_id` is the id asked for, `gaps` the directories the lookup went without, each with the reason. Not a
    `StationNotFoundError`: it is the provider's side that failed, and the same request can succeed once DWD has
    filled the directory again. Raised only where a station is not found and a directory was skipped.
    """

    def __init__(self, station_id: str, gaps: dict[str, str]) -> None:
        """Keep the id and the directories, and name them in the message."""
        self.station_id = station_id
        self.gaps = dict(gaps)
        went_without = " and ".join(f"the directory {directory} ({reason})" for directory, reason in self.gaps.items())
        super().__init__(
            f"No station found for {station_id}. The lookup of the stations went without {went_without}, so a station "
            "that only it lists is not found, and this may be one. Try again later."
        )

    def __reduce__(self) -> tuple:
        """Rebuild from the id and the directories, not from the message in `args`, so the error pickles."""
        return type(self), (self.station_id, self.gaps), self.__dict__


class MissingDependencyError(ConfigurationError, ImportError):
    """Raised when something needs an optional dependency that is not installed.

    An `ImportError`, because that is what it is, and its own type because a caller reporting it
    as an instruction to the user must not report every other import failure that way -- a typo or
    a cycle inside a provider module is a defect and wants its traceback. The message names the
    package and, where the installed metadata knows one, the extra that installs it; it is the
    whole of what there is to say, so the command line prints it as one line and the REST API
    answers 501, as the deployment's lack and not the request's fault. Raised through
    `wetterdienst.util.extras.import_optional`.
    """


class BufrReaderMissingError(MissingDependencyError):
    """Raised when data published as BUFR is asked for and the reader to decode it is unavailable.

    The eccodes and pdbufr pair is one reader, so it is one dependency to the caller. Its own
    type, as its message names a compiled library as well as the extra.
    """


class CredentialMissingError(ConfigurationError, ValueError):
    """Raised when a provider needs a credential to be asked anything and none is configured.

    A `ValueError`, which is what the providers raised before this had a type of its own, so that a
    caller catching that still catches it. Its own type because the message names the setting to
    change, which is an instruction for whoever runs the process: the Python caller and the command
    line user are that person and get it as it is, while the REST API and the MCP tools, whose
    callers administer nothing of the server, answer with a fixed sentence and log the message.
    """


class CredentialRejectedError(ConfigurationError, PermissionError):
    """Raised when a provider refuses the credential this installation holds for it (HTTP 401 or 403).

    The sibling of `CredentialMissingError`: there the key is not set, here it is set and the
    provider does not accept it, so whoever runs the process has to replace it. A `PermissionError`,
    which is what the provider raised before this had a type of its own, so that a caller catching
    that still catches it. Its message names the setting to change and never the credential itself;
    the Python caller and the command line user, who run the process, get it as it is, while the REST
    API and the MCP tools answer with a fixed sentence (a 501, as for a missing credential) and log it.
    """


class NoStationsWithElevationError(RequestError):
    """Raised when an elevation is asked about and no station in reach reports one of its own."""


class ParameterNotCarriedError(RequestError):
    """Raised when a parameter is asked for by name of a forecast run that never carries it."""


class ImageTooLargeError(RequestError):
    """Raised when a chart would be rendered larger than the caller allows (`max_side`), in pixels on a side.

    The REST API sets the limit and answers it with a 400. The size is only known once the figure is
    built, as a chart of several parameters is 300 px taller for each, so this is raised after the
    values were collected and before the browser is started.
    """

    def __init__(self, width: float, height: float, max_side: int) -> None:
        """Keep the size the image would have and the limit it exceeds, in pixels."""
        self.width = width
        self.height = height
        self.max_side = max_side
        super().__init__(
            f"The image would be {width:.0f} x {height:.0f} px, and this server renders no side longer than "
            f"{max_side} px."
        )

    def __reduce__(self) -> tuple:
        """Rebuild from the size and the limit, not from the message in `args`, so the error pickles."""
        return type(self), (self.width, self.height, self.max_side), self.__dict__


class ImageTimeoutError(WetterdienstError, TimeoutError):
    """Raised when a chart was not rendered to an image in time, and the browser that draws it was closed (GH-3723).

    Kaleido draws an image in a Chrome of its own. One that is stuck (a start that does not end, a page that is
    never ready) used to hold the caller for ever. The render has `IMAGE_TIMEOUT` seconds, the start of the browser
    included, and then the browser is shut down, its processes with it, so that nothing is left behind.

    Neither the caller's mistake nor the provider's: the request was valid, the renderer of this machine did not
    answer, and the same one can succeed on a retry. The REST API answers it with a 504 of the kind `image-timeout`
    and the command line with one line, exit 1. A `TimeoutError` too.
    """

    def __init__(self, timeout: float | None) -> None:
        """Keep the limit of the render, in seconds; None where a shorter wait of the browser's own ran out first."""
        self.timeout = timeout
        limit = "" if timeout is None else f" (the limit is {timeout:g} seconds)"
        super().__init__(
            f"The image was not rendered in time{limit}: the browser that draws it did not finish and was closed. "
            "Try again; if it keeps happening, check that Chrome starts on this machine."
        )

    def __reduce__(self) -> tuple:
        """Rebuild from the seconds, not from the message in `args`, so the error pickles."""
        return type(self), (self.timeout,), self.__dict__


class UnknownFormatError(RequestError, KeyError):
    """Raised when an output format is asked for that nothing here renders, naming it and the ones that are.

    A `RequestError`, so a `ValueError` and what the REST API answers with a 400, and also the `KeyError`
    that `to_format` and the charts raised before this class, so both `except KeyError` and `except ValueError`
    still catch it. The alerts result raised a `ValueError`.
    """

    def __init__(self, fmt: str, supported: Sequence[str]) -> None:
        """Keep the format that was asked for and the ones that are supported."""
        self.fmt = fmt
        self.supported = tuple(supported)
        super().__init__(f"Unknown output format {fmt!r}: use one of {', '.join(self.supported)}")

    def __str__(self) -> str:
        """Give the message as it is, where a `KeyError` would give it in quotes."""
        return Exception.__str__(self)

    def __reduce__(self) -> tuple[type[Self], tuple[str, tuple[str, ...]], dict[str, object]]:
        """Rebuild from the format and the list, as the message is no argument of the constructor.

        The `__dict__` goes along, which is where a note added to the error (`__notes__`) is kept.
        """
        return type(self), (self.fmt, self.supported), self.__dict__


class ExportRefusedError(WetterdienstError):
    """Raised when a sink will not perform an export, for a reason the caller can act on.

    Four shapes of the same thing: `if_exists` asked for something this sink does not do, the
    target already holds data and `if_exists` said to stop, the target names a format or protocol
    nothing here writes, or the target cannot be read, such as one whose password holds an
    unencoded `@`. What they share is that the message is the whole of what is
    useful -- there is nothing in the traceback a caller would read.

    Its own type, because every caller that reports one as an instruction rather than as a crash
    would otherwise have to guess from the class. Guessing is what this replaces: `fail` used to
    arrive as a `KeyError` from DuckDB and as pandas' `ValueError` from the SQLAlchemy sinks, and
    both classes are also how a sink breaks, so a defect inside one was reported as advice -- a
    `KeyError` printed its own argument and nothing else.
    """


class ProviderContractError(WetterdienstError):
    """Raised when the frame a provider hands the core cannot be made to fit the long form (GH-2627).

    A defect of the provider's code, not of the request and not of the source's data: the frame lacks a column
    the core cannot make up (`parameter`, `timestamp` or `value`), or holds one of a type nothing can turn into
    the declared one (a timestamp that is a string, a value that is a list). The message names the provider, the
    column and what it was handed. A value that is merely not a number is no such defect: it becomes null.

    Not part of the documented public surface: it is for the people who write a provider, and a caller meets it
    as the REST API's 500, the server's error.
    """
