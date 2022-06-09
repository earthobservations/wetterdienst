# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
class FailedDownload(Exception):
    pass


class InvalidEnumeration(ValueError):
    pass


class InvalidParameter(ValueError):
    pass


class InvalidParameterSet(ValueError):
    pass


class InvalidParameterCombination(ValueError):
    pass


class NoParametersFound(ValueError):
    pass


class MetaFileNotFound(FileNotFoundError):
    pass


class ProductFileNotFound(FileNotFoundError):
    pass


class StartDateEndDateError(Exception):
    pass


class DatetimeOutOfRangeError(Exception):
    pass


class InvalidTimeInterval(ValueError):
    pass


class ProviderError(Exception):
    pass
