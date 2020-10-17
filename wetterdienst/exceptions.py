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
