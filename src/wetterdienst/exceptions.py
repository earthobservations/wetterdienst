# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Custom exceptions for the wetterdienst library."""


class InvalidEnumerationError(ValueError):
    """Raised when an invalid enumeration is provided."""


class NoParametersFoundError(ValueError):
    """Raised when no parameters are found."""


class MetaFileNotFoundError(FileNotFoundError):
    """Raised when a meta file is not found."""


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
