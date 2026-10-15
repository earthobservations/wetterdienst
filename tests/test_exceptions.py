# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The exceptions of wetterdienst: one root, and the built-in classes each of them was before it (GH-2634)."""

from __future__ import annotations

import inspect
import pickle

import pytest

import wetterdienst
from wetterdienst import exceptions
from wetterdienst.exceptions import (
    ApiNotFoundError,
    BufrReaderMissingError,
    ConfigurationError,
    CredentialMissingError,
    DateRequiredError,
    DownloadError,
    ExportRefusedError,
    ImageTooLargeError,
    InvalidBoundingBoxError,
    InvalidEnumerationError,
    InvalidParameterError,
    InvalidTimeIntervalError,
    IssueNotFoundError,
    LocationOutOfRangeError,
    MetadataNotFoundError,
    MetaFileFormatError,
    MetaFileNotFoundError,
    MissingDependencyError,
    MissingTimeIntervalError,
    NoInternetError,
    NoParametersFoundError,
    NoPeriodsFoundError,
    NoStationsWithElevationError,
    NotEnoughDataError,
    NotFoundError,
    ParameterNotCarriedError,
    ProductFileNotFoundError,
    ProviderNotFoundError,
    RequestError,
    ReversedTimeIntervalError,
    StartDateEndDateError,
    StationNotFoundError,
    UpstreamError,
    WetterdienstError,
)

#: each class of `exceptions.py` with the class of the hierarchy that is its kind, and the built-in
#: classes it derived from before the hierarchy, which it must still be caught as. A class added to
#: the module has to be given a row here, which is how it gets its place.
_BASES: dict[type[BaseException], tuple[type[WetterdienstError], tuple[type[BaseException], ...]]] = {
    InvalidEnumerationError: (RequestError, (ValueError,)),
    InvalidParameterError: (RequestError, (ValueError,)),
    NoParametersFoundError: (RequestError, (ValueError,)),
    NoPeriodsFoundError: (RequestError, (ValueError,)),
    MetaFileNotFoundError: (UpstreamError, (FileNotFoundError, OSError)),
    MetaFileFormatError: (UpstreamError, (ValueError,)),
    ProductFileNotFoundError: (UpstreamError, (FileNotFoundError, OSError)),
    StartDateEndDateError: (RequestError, (Exception,)),
    InvalidTimeIntervalError: (RequestError, (ValueError,)),
    ReversedTimeIntervalError: (RequestError, (StartDateEndDateError,)),
    MissingTimeIntervalError: (RequestError, (InvalidTimeIntervalError, ValueError)),
    DateRequiredError: (RequestError, (MissingTimeIntervalError, StartDateEndDateError, ValueError)),
    InvalidBoundingBoxError: (RequestError, (ValueError,)),
    LocationOutOfRangeError: (RequestError, (ValueError,)),
    IssueNotFoundError: (NotFoundError, (IndexError, LookupError)),
    NotEnoughDataError: (RequestError, (ValueError,)),
    ProviderNotFoundError: (NotFoundError, (Exception,)),
    StationNotFoundError: (NotFoundError, (Exception,)),
    ApiNotFoundError: (NotFoundError, (Exception,)),
    MetadataNotFoundError: (NotFoundError, (LookupError,)),
    NoInternetError: (UpstreamError, (OSError,)),
    DownloadError: (UpstreamError, (Exception,)),
    MissingDependencyError: (ConfigurationError, (ImportError,)),
    BufrReaderMissingError: (ConfigurationError, (MissingDependencyError, ImportError)),
    CredentialMissingError: (ConfigurationError, (ValueError,)),
    NoStationsWithElevationError: (RequestError, (ValueError,)),
    ParameterNotCarriedError: (RequestError, (ValueError,)),
    ImageTooLargeError: (RequestError, (Exception,)),
    ExportRefusedError: (WetterdienstError, (Exception,)),
}

#: the kinds, with the built-in class each is
_KINDS = {
    RequestError: ValueError,
    NotFoundError: LookupError,
    ConfigurationError: Exception,
    UpstreamError: Exception,
    ExportRefusedError: Exception,
}


def _classes_of_the_module() -> list[type[BaseException]]:
    return [
        cls
        for _, cls in inspect.getmembers(exceptions, inspect.isclass)
        if cls.__module__ == exceptions.__name__ and issubclass(cls, BaseException)
    ]


def _instance(cls: type[BaseException]) -> BaseException:
    """Build an instance without calling the class' own `__init__`, which two of them give arguments."""
    return cls.__new__(cls)


def test_every_class_of_the_module_is_a_row_of_the_table_or_the_root_or_a_kind() -> None:
    """A class added to `exceptions.py` is given its kind here, so none is left without a root."""
    unplaced = [
        cls.__name__
        for cls in _classes_of_the_module()
        if cls not in _BASES and cls is not WetterdienstError and cls not in _KINDS
    ]
    assert unplaced == []


@pytest.mark.parametrize("cls", _classes_of_the_module(), ids=lambda cls: cls.__name__)
def test_every_class_has_the_root(cls: type[BaseException]) -> None:
    """A caller can write `except WetterdienstError` for any of them."""
    assert issubclass(cls, WetterdienstError)
    assert isinstance(_instance(cls), WetterdienstError)


@pytest.mark.parametrize(("cls", "expected"), list(_BASES.items()), ids=[cls.__name__ for cls in _BASES])
def test_every_class_is_of_its_kind_and_keeps_the_classes_it_was(
    cls: type[BaseException], expected: tuple[type[WetterdienstError], tuple[type[BaseException], ...]]
) -> None:
    """Each class gains its kind and keeps its built-in bases, so an `except ValueError` still catches it."""
    kind, builtins = expected
    assert issubclass(cls, kind)
    for builtin in builtins:
        assert issubclass(cls, builtin), f"{cls.__name__} is no longer a {builtin.__name__}"
        # and is caught as it, not only in name
        with pytest.raises(builtin):
            raise _instance(cls)


@pytest.mark.parametrize(("kind", "builtin"), list(_KINDS.items()), ids=lambda value: value.__name__)
def test_the_kinds_are_the_root_and_the_built_in_class_they_stand_for(
    kind: type[WetterdienstError], builtin: type[BaseException]
) -> None:
    """The kinds hang from the root, a request error being a `ValueError` and a not-found a `LookupError`."""
    assert issubclass(kind, WetterdienstError)
    assert issubclass(kind, builtin)


def test_the_kinds_are_told_apart() -> None:
    """A class is of one kind: a handler asking for one does not catch another."""
    for kind in (RequestError, NotFoundError, ConfigurationError, UpstreamError):
        for other in (RequestError, NotFoundError, ConfigurationError, UpstreamError, ExportRefusedError):
            assert issubclass(kind, other) is (kind is other)


def test_the_os_errors_keep_the_layout_of_their_built_in_class() -> None:
    """The `OSError`s are `OSError`s still: their `errno`, `filename` and `strerror` come through."""
    error = MetaFileNotFoundError(2, "No such file", "meta.txt")
    assert (error.errno, error.strerror, error.filename) == (2, "No such file", "meta.txt")
    assert isinstance(error, FileNotFoundError)
    assert isinstance(NoInternetError("offline"), OSError)


@pytest.mark.parametrize(
    "error",
    [
        NoInternetError("offline"),
        MetaFileNotFoundError("no meta file"),
        StationNotFoundError("no station"),
        IssueNotFoundError("no issue"),
        MissingDependencyError("pip install wetterdienst[export]"),
        DownloadError("https://example.com/a", "timed out"),
    ],
    ids=lambda error: type(error).__name__,
)
def test_an_error_pickles_with_its_class_and_message(error: Exception) -> None:
    """The new base does not change how the errors cross a process boundary."""
    copy = pickle.loads(pickle.dumps(error))  # noqa: S301
    assert type(copy) is type(error)
    assert str(copy) == str(error)


def test_the_hierarchy_is_public() -> None:
    """The root and the kinds are importable from the package, where its other public classes are."""
    for name in (
        "WetterdienstError",
        "RequestError",
        "NotFoundError",
        "ConfigurationError",
        "UpstreamError",
        "ExportRefusedError",
    ):
        assert getattr(wetterdienst, name) is getattr(exceptions, name)
        assert name in wetterdienst.__all__
