# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the BUFR reader availability helpers."""

import builtins
import importlib
import logging
import sys
import threading
import warnings
from collections.abc import Iterator

import pytest

from tests.conftest import BUFR_AVAILABLE
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


def test_the_probe_answers_whatever_the_import_does(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nothing escapes the question, not only the failures seen so far.

    It was widened twice by naming what had been seen -- `ModuleNotFoundError`, then `ImportError`,
    then `RuntimeError` -- and an `AttributeError` from `eccodes.eccodes` moving, or a gribapi
    error class, would have escaped all three. Two callers cannot take a raise: the radar path that
    logs and carries on, and `BUFR_AVAILABLE`, computed while the suite is collecting.
    """
    real_import = builtins.__import__

    def import_that_fails_unusually(name: str, *args: object, **kwargs: object) -> object:
        if name in {"eccodes", "pdbufr"}:
            msg = "something nobody wrote a handler for"
            raise AttributeError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_that_fails_unusually)
    with caplog.at_level(logging.WARNING):
        assert eccodes.bufr_is_available() is False
    assert "did not load" in caplog.text


def test_a_broken_eccodes_seen_through_pdbufr_is_not_read_as_absence(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`eccodes.eccodes` missing means eccodes is there and broken, whichever import surfaces it.

    The two probes read the name differently: one exactly, one by prefix, so the same failure was
    a warning through `ensure_eccodes` and silent absence through `ensure_pdbufr` -- and silent
    absence is what hands the caller advice to install what they have.
    """
    real_import = builtins.__import__

    def import_with_a_broken_eccodes(name: str, *args: object, **kwargs: object) -> object:
        if name == "pdbufr":
            msg = "No module named 'eccodes.eccodes'"
            raise ModuleNotFoundError(msg, name="eccodes.eccodes")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_with_a_broken_eccodes)
    with caplog.at_level(logging.WARNING):
        assert eccodes.ensure_pdbufr() is False
    assert "eccodes.eccodes" in caplog.text


class _StaleLibrary:
    """The loaded library, reporting itself as 2.34.1 -- what Ubuntu 24.04 ships.

    A stand-in for gribapi's `lib` rather than a patch of it: the compiled library takes no
    attributes. Its first answer comes with another warning of the same category, to show the
    filter lets through what it does not name -- and the first answer is the one the import asks for.
    """

    def __init__(self, lib: object) -> None:
        self._lib = lib
        self._asked = False

    def grib_get_api_version(self) -> int:
        if not self._asked:
            self._asked = True
            warnings.warn("something else the bindings say on import", UserWarning, stacklevel=1)
        return 23401

    def __getattr__(self, name: str) -> object:
        return getattr(self._lib, name)


@pytest.fixture
def _a_first_import_of_a_stale_library(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Import eccodes and pdbufr afresh, over a library older than the bindings recommend.

    The suite has imported both already -- `BUFR_AVAILABLE` asks while collecting -- and the advice
    is given once, by `gribapi/__init__.py` as it is first imported. So that module and the chain
    importing it is forgotten for the test, and put back after it. `gribapi.gribapi`, the bindings
    and `eccodes.highlevel` stay, so the library is not loaded a second time nor declared to cffi
    again, which it refuses; the advice reads the version from `gribapi.gribapi.lib`, which is
    where the stale one is put.
    """
    import gribapi.gribapi  # noqa: PLC0415

    monkeypatch.setattr(gribapi.gribapi, "lib", _StaleLibrary(gribapi.gribapi.lib))
    # read once from the library as gribapi.gribapi was first imported, and named in the advice
    monkeypatch.setattr(gribapi.gribapi, "__version__", "2.34.1")

    def forgotten(name: str) -> bool:
        return name in {"gribapi", "eccodes", "eccodes.eccodes"} or name.split(".", maxsplit=1)[0] == "pdbufr"

    before = {name: module for name, module in sys.modules.items() if forgotten(name)}
    for name in before:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in [name for name in sys.modules if forgotten(name)]:
            del sys.modules[name]
        sys.modules.update(before)


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.usefixtures("_a_first_import_of_a_stale_library")
def test_the_stale_library_does_provoke_the_advice() -> None:
    """The control for the test below: imported plainly, the stand-in gets the bindings' advice.

    Without it, the test below would pass just as well if the advice were reworded, raised from a
    module the fixture keeps, or never raised at all.
    """
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        importlib.import_module("eccodes")
    said = [str(warning.message) for warning in seen]
    assert "ecCodes 2.42.0 or higher is recommended. You are running version 2.34.1" in said


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.usefixtures("_a_first_import_of_a_stale_library")
@pytest.mark.parametrize("probe", ["ensure_eccodes", "ensure_pdbufr"])
def test_the_advice_to_upgrade_the_library_is_not_warned(probe: str) -> None:
    """A distribution's ecCodes is older than the bindings recommend, and reads BUFR all the same.

    The bindings warned so on every first import -- Debian trixie ships 2.41 and Ubuntu 24.04 2.34,
    against a recommended 2.42 -- and a caller could neither act on it nor tell it was harmless
    (GH-2442). Either probe may be the first import in a process, pdbufr importing eccodes itself.
    Nothing else the import says is held back.
    """
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        assert getattr(eccodes, probe)() is True
    said = [str(warning.message) for warning in seen]
    assert not [message for message in said if "or higher is recommended" in message]
    assert "something else the bindings say on import" in said


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.usefixtures("_a_first_import_of_a_stale_library")
def test_the_library_version_is_logged_in_its_place(caplog: pytest.LogCaptureFixture) -> None:
    """Which library loaded is still there to be read, at debug."""
    with (
        caplog.at_level(logging.DEBUG, logger=eccodes.__name__),
        pytest.warns(UserWarning, match="something else the bindings say on import"),
    ):
        assert eccodes.ensure_eccodes() is True
    assert "ecCodes library 2.34.1" in caplog.text


def test_two_threads_do_not_put_back_each_others_filters() -> None:
    """`catch_warnings` puts back the filter list it found, which another thread may have changed.

    The REST API answers in a thread pool, and `lru_cache` runs a body again for a second caller
    that asks before the first has an answer. Interleaved, the second puts back the list holding
    the first one's filter after the first has put back the original, and the advice stays
    silenced for the rest of the process. Here the first waits inside while the second tries to
    come in.
    """
    original = list(warnings.filters)
    inside = threading.Event()
    leave = threading.Event()

    def first() -> None:
        with eccodes._without_eccodes_version_advice():  # noqa: SLF001
            inside.set()
            leave.wait(5)

    def second() -> None:
        inside.wait(5)
        with eccodes._without_eccodes_version_advice():  # noqa: SLF001
            leave.set()

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for thread in threads:
        thread.start()
    # without the lock, the second is in at once and lets the first go before this times out
    assert not leave.wait(0.5)
    leave.set()
    for thread in threads:
        thread.join(5)
    assert warnings.filters == original
