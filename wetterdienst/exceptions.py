# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
class InvalidEnumerationError(ValueError):
    pass


class NoParametersFoundError(ValueError):
    pass


class MetaFileNotFoundError(FileNotFoundError):
    pass


class ProductFileNotFoundError(FileNotFoundError):
    pass


class StartDateEndDateError(Exception):
    pass


class InvalidTimeIntervalError(ValueError):
    pass


class ProviderNotFoundError(Exception):
    pass


class StationNotFoundError(Exception):
    pass
