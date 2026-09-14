# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the BUFR reader availability helpers."""

import builtins

import pytest

from wetterdienst.util import eccodes


@pytest.fixture(autouse=True)
def _forget_the_answers() -> None:
    """Ask again each time.

    The three helpers are cached, being a question about the environment rather than about a
    request, so a test that changes the environment has to clear what an earlier one settled --
    and clear it again afterwards, or the absence it staged outlives it.
    """
    for fn in (eccodes.ensure_eccodes, eccodes.ensure_pdbufr, eccodes.bufr_is_available):
        fn.cache_clear()
    yield
    for fn in (eccodes.ensure_eccodes, eccodes.ensure_pdbufr, eccodes.bufr_is_available):
        fn.cache_clear()


def test_ensure_eccodes_reads_a_library_it_cannot_load_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """An eccodes with no compiled library behind it is as good as no eccodes.

    It raises the plain `ImportError` out of the import -- "libeccodes.so: cannot open shared
    object file" -- where a missing package raises `ModuleNotFoundError`. Only the second was
    caught, so the first came back out of a question that exists to be answered rather than
    raised: `_attach_bufr` logs and carries on where the reader is unavailable, and cannot do
    that if asking whether it is available is itself what fails.
    """
    real_import = builtins.__import__

    def import_without_the_library(name: str, *args: object, **kwargs: object) -> object:
        if name == "eccodes":
            # what the loader says, and a plain ImportError rather than the ModuleNotFoundError a
            # missing package raises -- the package is there, what it binds to is not
            msg = "libeccodes.so: cannot open shared object file: No such file or directory"
            raise ImportError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_the_library)
    assert eccodes.ensure_eccodes() is False
    assert eccodes.bufr_is_available() is False


def test_require_bufr_is_quiet_where_the_reader_is_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is raised where both halves answer."""
    monkeypatch.setattr(eccodes, "bufr_is_available", lambda: True)
    assert eccodes.require_bufr("DWD road weather data") is None


def test_require_bufr_names_the_extra_and_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal carries the remedy, both halves of it.

    A wheel covers the compiled library on most platforms and not on all, so the message names the
    extra that carries the readers and the system package that carries what they read with.
    """
    monkeypatch.setattr(eccodes, "bufr_is_available", lambda: False)
    with pytest.raises(ImportError, match=r"pip install wetterdienst\[bufr\]") as excinfo:
        eccodes.require_bufr("DWD road weather data")
    assert "DWD road weather data" in str(excinfo.value)
    assert "libeccodes-dev" in str(excinfo.value)


def test_ensure_pdbufr_reads_any_import_failure_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A RuntimeError out of the import is an answer, whatever it says.

    It used to be read for the words "Cannot find the ecCodes library" and re-raised otherwise --
    gribapi's present phrasing, and no promise. Two callers cannot take a raise: `_attach_bufr`,
    which logs and carries on rather than fail a query, and the `BUFR_AVAILABLE` the suite computes
    while collecting, where raising aborts collection instead of skipping the tests that want a
    reader.
    """
    real_import = builtins.__import__

    def import_with_some_other_complaint(name: str, *args: object, **kwargs: object) -> object:
        if name == "pdbufr":
            msg = "ecCodes bindings unavailable: some future wording nobody matched on"
            raise RuntimeError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_with_some_other_complaint)
    assert eccodes.ensure_pdbufr() is False
    assert eccodes.bufr_is_available() is False
