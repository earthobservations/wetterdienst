# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Custom exceptions for the wetterdienst library."""


class InvalidEnumerationError(ValueError):
    """Raised when an invalid enumeration is provided."""


class NoParametersFoundError(ValueError):
    """Raised when no parameters are found."""


class NoPeriodsFoundError(ValueError):
    """Raised when none of the requested periods is published for the requested datasets."""


class MetaFileNotFoundError(FileNotFoundError):
    """Raised when a meta file is not found."""


class MetaFileFormatError(ValueError):
    """Raised when a meta file does not match the expected format."""


class ProductFileNotFoundError(FileNotFoundError):
    """Raised when a product file is not found."""


class StartDateEndDateError(Exception):
    """Raised when the start date is after the end date."""


class InvalidTimeIntervalError(ValueError):
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
    """Raised when a dataset that is published per date is requested without a window of time.

    Told apart from its parents for the same reason as `ReversedTimeIntervalError`. It is also a
    `StartDateEndDateError`, which is what this refusal was before, so that a caller catching that
    still catches it.
    """


class InvalidBoundingBoxError(ValueError):
    """Raised when a bounding box's borders are given the wrong way round."""


class LocationOutOfRangeError(ValueError):
    """Raised when a location lies outside the range a computation covers."""


class IssueNotFoundError(IndexError):
    """Raised when a forecast run is asked for by an issue time the source does not list."""


class NotEnoughDataError(ValueError):
    """Raised when what a request selects holds too little data to answer it."""


class ProviderNotFoundError(Exception):
    """Raised when a provider is not found in the provider list."""


class StationNotFoundError(Exception):
    """Raised when a station is not found in the station list."""


class ApiNotFoundError(Exception):
    """Raised when an API is not found in the API list."""


class NoInternetError(OSError):
    """Raised when no internet connection is available."""


class DownloadError(Exception):
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


class BufrReaderMissingError(ImportError):
    """Raised when data published as BUFR is asked for and the reader to decode it is unavailable.

    An `ImportError`, because that is what it is, and its own type because a caller reporting it
    as an instruction to the user must not report every other import failure that way -- a typo or
    a cycle inside a provider module is a defect and wants its traceback.
    """


class NoStationsWithElevationError(ValueError):
    """Raised when an elevation is asked about and no station in reach reports one of its own."""


class ParameterNotCarriedError(ValueError):
    """Raised when a parameter is asked for by name of a forecast run that never carries it."""


class ExportRefusedError(Exception):
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
