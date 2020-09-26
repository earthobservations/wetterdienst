class FailedDownload(Exception):
    pass


class InvalidParameter(ValueError):
    pass


class InvalidParameterCombination(ValueError):
    pass


class MetaFileNotFound(FileNotFoundError):
    pass


class ProductFileNotFound(FileNotFoundError):
    pass


class StartDateEndDateError(Exception):
    pass


class DatetimeOutOfRangeError(Exception):
    pass
