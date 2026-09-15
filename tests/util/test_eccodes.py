# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the BUFR reader availability helpers."""

import builtins
import logging

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


def test_a_reader_that_is_there_and_does_not_work_says_so(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Installed and broken is a different answer from not installed, and wants different words.

    `require_bufr` tells the caller to install the extra, which is the whole story where nothing is
    installed and no help at all where the package is there and its compiled library is not. The
    advice cannot tell those apart, so the reason is logged at warning rather than left at debug
    for someone who already knows to look.
    """
    real_import = builtins.__import__

    def import_of_something_broken(name: str, *args: object, **kwargs: object) -> object:
        if name in {"eccodes", "pdbufr"}:
            msg = "libeccodes.so: cannot open shared object file: No such file or directory"
            raise ImportError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_of_something_broken)
    with caplog.at_level(logging.WARNING):
        assert eccodes.bufr_is_available() is False
    assert "did not load" in caplog.text
    assert "libeccodes.so" in caplog.text


def test_not_installed_at_all_stays_quiet(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Nothing installed is what the message already explains, so it is not also a warning."""
    real_import = builtins.__import__

    def import_of_something_absent(name: str, *args: object, **kwargs: object) -> object:
        if name in {"eccodes", "pdbufr"}:
            # as the import machinery raises it: `name` set, which is what tells "this package is
            # absent" from "something inside it is"
            msg = f"No module named {name!r}"
            raise ModuleNotFoundError(msg, name=name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_of_something_absent)
    with caplog.at_level(logging.WARNING):
        assert eccodes.bufr_is_available() is False
    assert not caplog.text


def test_require_bufr_raises_its_own_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal has a type of its own, so reporting it does not mean reporting every ImportError.

    The CLI turns this one into a line of advice with no traceback. A cycle or a typo inside a
    provider module is also an ImportError and is a defect, which wants its traceback.
    """
    from wetterdienst.exceptions import BufrReaderMissingError  # noqa: PLC0415

    monkeypatch.setattr(eccodes, "bufr_is_available", lambda: False)
    with pytest.raises(BufrReaderMissingError):
        eccodes.require_bufr("DWD road weather data")
    assert issubclass(BufrReaderMissingError, ImportError)


def test_a_broken_install_is_not_read_as_an_absent_one(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A package that is present and internally broken raises absence's exception, not absence.

    `import eccodes` on a broken install commonly fails as `No module named 'gribapi.bindings'` --
    a `ModuleNotFoundError` raised from *inside* the package. Read as "not installed", the caller
    is told to install what they have, which is the advice this warning exists to avoid.
    """
    real_import = builtins.__import__

    def import_missing_something_inside(name: str, *args: object, **kwargs: object) -> object:
        if name in {"eccodes", "pdbufr"}:
            msg = "No module named 'gribapi.bindings'"
            raise ModuleNotFoundError(msg, name="gribapi.bindings")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_missing_something_inside)
    with caplog.at_level(logging.WARNING):
        assert eccodes.bufr_is_available() is False
    assert "gribapi.bindings" in caplog.text
