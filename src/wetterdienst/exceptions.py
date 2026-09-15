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


class ProviderNotFoundError(Exception):
    """Raised when a provider is not found in the provider list."""


class StationNotFoundError(Exception):
    """Raised when a station is not found in the station list."""


class ApiNotFoundError(Exception):
    """Raised when an API is not found in the API list."""


class NoInternetError(OSError):
    """Raised when no internet connection is available."""


class BufrReaderMissingError(ImportError):
    """Raised when data published as BUFR is asked for and the reader to decode it is unavailable.

    An `ImportError`, because that is what it is, and its own type because a caller reporting it
    as an instruction to the user must not report every other import failure that way -- a typo or
    a cycle inside a provider module is a defect and wants its traceback.
    """


class NoStationsWithHeightError(ValueError):
    """Raised when a height is asked about and no station in reach reports one of its own."""
