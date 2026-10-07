# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the BUFR reader availability helpers."""

import builtins
import contextlib
import importlib
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import textwrap
import warnings
from collections.abc import Iterator
from io import BytesIO

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
    """The loaded library, reporting itself as an older one.

    A stand-in for gribapi's `lib` rather than a patch of it: the compiled library takes no
    attributes. Its first answer comes with another warning of the same category, to show the
    filter lets through what it does not name -- and the first answer is the one the import asks for.
    """

    def __init__(self, lib: object, version: int) -> None:
        self._lib = lib
        self._version = version
        self._asked = False

    def grib_get_api_version(self) -> int:
        if not self._asked:
            self._asked = True
            # attributed to the frame asking, gribapi/__init__.py, as the advice is: the filter's
            # module matches it, so only the filter's message can let it through
            warnings.warn("something else the bindings say on import", UserWarning, stacklevel=2)
        return self._version

    def __getattr__(self, name: str) -> object:
        return getattr(self._lib, name)


@pytest.fixture
def stale_library(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Import eccodes and pdbufr afresh, over a library older than the bindings recommend.

    The suite has imported both already -- `BUFR_AVAILABLE` asks while collecting -- and the advice
    is given once, by `gribapi/__init__.py` as it is first imported. So that module and the chain
    importing it is forgotten for the test, and put back after it. `gribapi.gribapi`, the bindings
    and `eccodes.highlevel` stay, so the library is not loaded a second time nor declared to cffi
    again, which it refuses; the advice reads the version from `gribapi.gribapi.lib`, which is
    where the stale one is put.

    The stale one is a minor release below what the installed bindings recommend, which moves
    with them -- 2.42.0 in eccodes 2.48, 2.31.0 in 1.7.1, the floor the minimum-versions job
    installs. Its version is what the fixture gives the test.
    """
    import gribapi  # noqa: PLC0415
    import gribapi.gribapi  # noqa: PLC0415

    stale = gribapi.min_recommended_version_int - 100
    version = f"{stale // 10000}.{stale // 100 % 100}.{stale % 100}"
    monkeypatch.setattr(gribapi.gribapi, "lib", _StaleLibrary(gribapi.gribapi.lib, stale))
    # read once from the library as gribapi.gribapi was first imported, and named in the advice
    monkeypatch.setattr(gribapi.gribapi, "__version__", version)

    def forgotten(name: str) -> bool:
        return name in {"gribapi", "eccodes", "eccodes.eccodes"} or name.split(".", maxsplit=1)[0] == "pdbufr"

    before = {name: module for name, module in sys.modules.items() if forgotten(name)}
    for name in before:
        del sys.modules[name]
    try:
        yield version
    finally:
        for name in [name for name in sys.modules if forgotten(name)]:
            del sys.modules[name]
        sys.modules.update(before)


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_the_stale_library_does_provoke_the_advice(stale_library: str) -> None:
    """The control for the test below: imported plainly, the stand-in gets the bindings' advice.

    Without it, the test below would pass just as well if the advice were reworded, raised from a
    module the fixture keeps, or never raised at all.
    """
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        importlib.import_module("eccodes")
    said = [str(warning.message) for warning in seen]
    # whichever version the installed bindings recommend, matched by the pattern the filter uses,
    # so this also says the filter's pattern fits the advice as given
    advice = eccodes._ECCODES_VERSION_ADVICE  # noqa: SLF001
    running = re.escape(stale_library)
    assert [message for message in said if re.fullmatch(rf"{advice}\. You are running version {running}", message)]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.usefixtures("stale_library")
@pytest.mark.parametrize("probe", ["ensure_eccodes", "ensure_pdbufr"])
def test_the_advice_to_upgrade_the_library_is_not_warned(probe: str) -> None:
    """A distribution's ecCodes is older than the bindings recommend, and reads BUFR all the same.

    The bindings warned so on every first import -- Debian trixie ships 2.41 and Ubuntu 24.04 2.34,
    against a recommended 2.42 -- and a caller could neither act on it nor tell it was harmless
    (GH-2442). Either probe may be the first import in a process, pdbufr importing eccodes itself.
    Nothing else the import says is held back.

    "always" here and below, so the run's own filters (`-W error`, `-W ignore`) do not decide what
    is seen; the filter under test goes ahead of it.
    """
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        assert getattr(eccodes, probe)() is True
    said = [str(warning.message) for warning in seen]
    assert not [message for message in said if "or higher is recommended" in message]
    assert "something else the bindings say on import" in said


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_the_library_version_is_logged_in_its_place(stale_library: str, caplog: pytest.LogCaptureFixture) -> None:
    """Which library loaded is still there to be read, at debug."""
    with caplog.at_level(logging.DEBUG, logger=eccodes.__name__), warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert eccodes.ensure_eccodes() is True
    assert f"ecCodes library {stale_library}" in caplog.text


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.usefixtures("stale_library")
def test_a_radar_bufr_read_asked_directly_is_quiet_too() -> None:
    """`read_radar_bufr` imports pdbufr itself and can be called without asking either probe first.

    What it is handed here is not BUFR, so the read fails -- after the import, which is the part
    this is about. How it fails is not: gribapi's error for bytes that are not BUFR.
    """
    from wetterdienst.provider.dwd.radar.api import _BUFR_VALUE_FIELD, read_radar_bufr  # noqa: PLC0415

    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        with contextlib.suppress(Exception):
            read_radar_bufr(BytesIO(b"not BUFR"), next(iter(_BUFR_VALUE_FIELD)))
    # the read got as far as importing the reader, so the advice had its chance
    assert "pdbufr" in sys.modules
    said = [str(warning.message) for warning in seen]
    assert not [message for message in said if "or higher is recommended" in message]
    assert "something else the bindings say on import" in said


#: the filter is installed only where the bindings are, and these tests watch it being installed
needs_the_bindings = pytest.mark.skipif(importlib.util.find_spec("gribapi") is None, reason="eccodes required")
#: Python 3.14's context-aware warnings keep `catch_warnings`' list apart from `warnings.filters`,
#: which these tests read
reads_the_filter_list = pytest.mark.skipif(
    bool(getattr(sys.flags, "context_aware_warnings", False)), reason="filters are context-local"
)


@needs_the_bindings
def test_the_advice_is_ignored_only_from_the_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The filter is left in place, so it is scoped to the module that gives the advice.

    The same words from anywhere else -- here, this test module -- are not the bindings' import-time
    advice, and are still shown.
    """
    advice = "ecCodes 2.42.0 or higher is recommended. You are running version 2.34.1"
    # as before the bindings' first import, the only time the filter is installed
    monkeypatch.delitem(sys.modules, "gribapi", raising=False)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        eccodes.quiet_eccodes_version_advice()
        warnings.warn(advice, stacklevel=1)
        # a module whose name only starts like the bindings' is somewhere else too
        warnings.warn_explicit(advice, UserWarning, "gribapi_tools.py", 1, module="gribapi_tools")
        # and the bindings' own submodules are not
        warnings.warn_explicit(advice, UserWarning, "gribapi/gribapi.py", 1, module="gribapi.gribapi")
    assert [(str(warning.message), warning.filename) for warning in seen] == [
        (advice, __file__),
        (advice, "gribapi_tools.py"),
    ]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
@pytest.mark.usefixtures("stale_library")
def test_warnings_as_errors_do_not_make_the_reader_look_missing() -> None:
    """Under `-W error` the advice was raised inside `import eccodes`, and read as no reader at all.

    `ensure_eccodes` answers any failure of the import as absence, so a caller running with warnings
    as errors -- a test suite's `filterwarnings = error` -- was told to install what they have. The
    filter goes ahead of theirs. Here it is an error filter for the advice alone, so that the
    stand-in's other warning is not one too.
    """
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        warnings.filterwarnings("error", message=eccodes._ECCODES_VERSION_ADVICE)  # noqa: SLF001
        assert eccodes.ensure_eccodes() is True


@reads_the_filter_list
def test_the_filters_are_left_alone_once_the_bindings_are_imported(monkeypatch: pytest.MonkeyPatch) -> None:
    """After the bindings' first import the advice has been given or not, and a filter does nothing.

    Changing the filters anyway would make Python forget which warnings it has shown once, and show
    them again.
    """
    monkeypatch.setitem(sys.modules, "gribapi", sys.modules.get("gribapi", object()))
    with warnings.catch_warnings():
        before = list(warnings.filters)
        eccodes.quiet_eccodes_version_advice()
        assert warnings.filters == before


@needs_the_bindings
@reads_the_filter_list
def test_a_filter_dropped_before_the_import_is_put_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asked again before the bindings' first import, the filter is there again if it was lost.

    A `catch_warnings` open when it was first installed -- a test's, another thread's -- puts back a
    list without it on the way out.
    """
    monkeypatch.delitem(sys.modules, "gribapi", raising=False)

    def installed() -> bool:
        return any(f[0] == "ignore" and f[1] is not None and "recommended" in f[1].pattern for f in warnings.filters)

    # from no filters at all, whatever the run had installed before
    with warnings.catch_warnings():
        warnings.resetwarnings()
        with warnings.catch_warnings():
            eccodes.quiet_eccodes_version_advice()
            assert installed()
        # dropped as the block put back the list it found
        assert not installed()
        eccodes.quiet_eccodes_version_advice()
        assert installed()


@reads_the_filter_list
def test_the_filters_are_left_alone_where_the_bindings_are_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the `bufr` extra there is no advice to quiet, and no reason to touch the filters."""
    monkeypatch.delitem(sys.modules, "gribapi", raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda *_: None)
    with warnings.catch_warnings():
        before = list(warnings.filters)
        eccodes.quiet_eccodes_version_advice()
        assert warnings.filters == before


@pytest.mark.parametrize("probe", ["ensure_eccodes", "ensure_pdbufr"])
def test_quieting_the_advice_cannot_make_a_probe_raise(probe: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Asking whether BUFR can be read is answered, not raised, whatever fails on the way.

    `find_spec` runs import hooks of its own -- a broken one raises -- and two callers cannot take a
    raise: `_attach_bufr`, which logs and carries on, and `BUFR_AVAILABLE`, computed while the suite
    collects.
    """

    def broken(*_: object) -> None:
        msg = "an import hook that does not work"
        raise RuntimeError(msg)

    monkeypatch.delitem(sys.modules, "gribapi", raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", broken)
    assert getattr(eccodes, probe)() is False


def _bufr_message(descriptors: list[int], values: dict[str, object]) -> bytes:
    """Encode one uncompressed single-subset BUFR message, as ecCodes writes it.

    Built here rather than downloaded, so a read of real BUFR runs in the offline selection.
    """
    import eccodes as bindings  # noqa: PLC0415

    handle = bindings.codes_bufr_new_from_samples("BUFR4")
    try:
        bindings.codes_set(handle, "numberOfSubsets", 1)
        bindings.codes_set(handle, "compressedData", 0)
        bindings.codes_set_array(handle, "unexpandedDescriptors", descriptors)
        for key, value in values.items():
            if isinstance(value, list):
                bindings.codes_set_array(handle, key, value)
            else:
                bindings.codes_set(handle, key, value)
        bindings.codes_set(handle, "pack", 1)
        return bindings.codes_get_message(handle)
    finally:
        bindings.codes_release(handle)


#: year, month, day, hour, minute
_TIME_DESCRIPTORS = [4001, 4002, 4003, 4004, 4005]
_TIME = {"year": 2026, "month": 9, "day": 13, "hour": 12, "minute": 0}


def test_bufr_file_holds_the_bytes_and_goes_again_after_a_failed_read() -> None:
    """The file is there to be opened by name while the read runs, and gone however the read ends."""
    with pytest.raises(RuntimeError, match="the read failed"), eccodes.bufr_file(b"some bytes") as path:  # noqa: PT012
        assert path.read_bytes() == b"some bytes"
        msg = "the read failed"
        raise RuntimeError(msg)
    assert not path.exists()
    assert not path.parent.exists()


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_a_road_file_decodes_through_the_reader() -> None:
    """A road message is read by pdbufr from the file it is written to, on every platform.

    The road tests around the parse stub pdbufr, and the ones reading published files are remote, so
    nothing in the offline selection had pdbufr open a road file. On Windows it could not: the file
    was a `NamedTemporaryFile` still held open, which Windows will not open a second time
    (GH-2446).
    """
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    message = _bufr_message(
        # shortStationName, the time, airTemperature
        [1018, *_TIME_DESCRIPTORS, 12101],
        {"shortStationName": "A006", **_TIME, "airTemperature": 285.5},
    )
    parameters = list(api.DwdRoadRequest.metadata["15_minutes"]["data"])
    file = File(url="a-road-file", content=BytesIO(message), status=200)
    df = api.DwdRoadValues._DwdRoadValues__parse_dwd_road_weather_data(file, parameters)  # noqa: SLF001
    assert df.drop_nulls("value").select("station_id", "parameter", "value").rows() == [
        ("A006", "airTemperature", 285.5),
    ]


@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_a_radar_file_decodes_through_the_reader() -> None:
    """A radar BUFR product is read by pdbufr from the file it is written to, on every platform.

    On Windows that read failed for the reason the road read did, and `_attach_bufr` logged "Unable
    to read BUFR file." and left the result's frame empty (GH-2446).
    """
    from wetterdienst.provider.dwd.radar.api import read_radar_bufr  # noqa: PLC0415
    from wetterdienst.provider.dwd.radar.metadata import DwdRadarParameter  # noqa: PLC0415

    message = _bufr_message(
        # shortStationName, the time, latitude, longitude, heightOfStation, projectionType,
        # pictureType, and three echoTops
        [1018, *_TIME_DESCRIPTORS, 5001, 6001, 7001, 29001, 30031, 101003, 21021],
        {
            "shortStationName": "BOO",
            **_TIME,
            "latitude": 54.0,
            "longitude": 10.0,
            "heightOfStation": 125.0,
            "projectionType": 0,
            "pictureType": 2,
            "echoTops": [1000.0, 2000.0, 3000.0],
        },
    )
    data = BytesIO(message)
    df = read_radar_bufr(data, DwdRadarParameter.PE_ECHO_TOP)
    assert df.get_column("station_id").unique().to_list() == ["BOO"]
    assert df.get_column("value").to_list() == [1000.0, 2000.0, 3000.0]
    # and the caller's bytes are still there to be read
    assert data.read() == message


def test_bufr_file_a_file_that_will_not_go_does_not_fail_the_read(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A file the OS will not let go of yet is left behind and logged, not raised after a read that worked.

    On Windows a file still open elsewhere -- a virus scanner reading what was just written -- cannot
    be removed, and the removal runs the moment the read returns.
    """
    unlink = os.unlink

    def refusing(path: str | os.PathLike, *args: object, **kwargs: object) -> None:
        if os.fspath(path).endswith("message.bufr"):
            msg = "[WinError 32] The process cannot access the file because it is being used"
            raise PermissionError(msg)
        unlink(path, *args, **kwargs)

    with caplog.at_level(logging.WARNING, logger=eccodes.__name__), eccodes.bufr_file(b"some bytes") as path:
        monkeypatch.setattr(os, "unlink", refusing)
    monkeypatch.undo()
    try:
        assert path.read_bytes() == b"some bytes"
        assert f"Unable to remove the temporary BUFR file {path.parent}" in caplog.text
    finally:
        shutil.rmtree(path.parent)


#: run in a fresh interpreter, since this one loaded eccodes while collecting: notes, each time the
#: bindings' module that loads the compiled library is looked for, whether pyproj was there already
_WATCH_THE_ORDER = """
import importlib.abc
import json
import sys

seen = []


class Watch(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "gribapi.bindings":
            seen.append("pyproj" in sys.modules)


sys.meta_path.insert(0, Watch())
"""

#: each way a read can be the first to load eccodes: DWD road asks `require_bufr` and radar's
#: `_attach_bufr` asks `bufr_is_available`, both through `ensure_eccodes`; `ensure_pdbufr` and
#: `read_radar_bufr` can each be asked first
_LOADS_ECCODES = {
    "ensure_eccodes": "from wetterdienst.util.eccodes import ensure_eccodes; ensure_eccodes()",
    "ensure_pdbufr": "from wetterdienst.util.eccodes import ensure_pdbufr; ensure_pdbufr()",
    "read_radar_bufr": textwrap.dedent(
        """
        import contextlib
        from io import BytesIO
        from wetterdienst.provider.dwd.radar.api import _BUFR_VALUE_FIELD, read_radar_bufr
        with contextlib.suppress(Exception):
            read_radar_bufr(BytesIO(b"not BUFR"), next(iter(_BUFR_VALUE_FIELD)))
        """
    ),
}

needs_eccodes_and_pyproj = pytest.mark.skipif(
    importlib.util.find_spec("gribapi") is None or importlib.util.find_spec("pyproj") is None,
    reason="eccodes and pyproj required",
)


def _watch(code: str) -> list[bool]:
    """Run `code` in a fresh interpreter, and say whether pyproj came before each look for the bindings."""
    script = f"{_WATCH_THE_ORDER}\n{code}\nprint(json.dumps(seen))"
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True, timeout=120)  # noqa: S603
    return json.loads(done.stdout.splitlines()[-1])


@needs_eccodes_and_pyproj
@pytest.mark.parametrize("entry", _LOADS_ECCODES)
def test_pyproj_is_imported_before_wetterdienst_loads_eccodes(entry: str) -> None:
    """Pyproj is there before the bindings load their library, whichever way a read gets to them.

    On Linux the eckitlib wheel the bindings pull in bundles its own PROJ, and a process that loads
    it before pyproj aborts at exit (ecmwf/eckit#354, GH-2441). A read of DWD road or radar BUFR
    loaded it first, so a caller that went on to use pyproj or wradlib failed with exit status 134
    or 139 after its work was done (GH-2468). The order is what is checked, being what avoids the
    abort, and can be checked where the abort does not happen.
    """
    assert _watch(_LOADS_ECCODES[entry]) == [True]


@needs_eccodes_and_pyproj
def test_a_caller_that_loads_eccodes_first_keeps_its_order() -> None:
    """Where eccodes is loaded already, pyproj is not imported after it.

    The order is settled by then, and importing pyproj would only make the abort at exit reachable
    for a process that never imports it. Also the control for the test above: an import of eccodes
    that does not go through this package is seen without pyproj.
    """
    code = textwrap.dedent(
        """
        import eccodes
        from wetterdienst.util.eccodes import ensure_eccodes
        assert ensure_eccodes()
        seen.append("pyproj" in sys.modules)
        """
    )
    assert _watch(code) == [False, False]
