# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""BUFR decoding availability for the wetterdienst package.

Decoding BUFR takes two halves that fail independently: `pdbufr`, which reads the messages, and
`eccodes`, the binding to the compiled library that does the decoding. `pdbufr` requires `eccodes`,
so a working install has both -- but the binding imports happily with no library behind it, and
only says so when asked for a version. Neither half alone answers "can this environment read
BUFR", which is the only question any caller has: use `bufr_is_available` for that, or
`require_bufr` where the answer has to be no further than the first line of a method.

pdbufr reads BUFR from a file it opens by name, so the bytes a reader downloads go through `bufr_file`.
"""

import importlib.util
import logging
import shutil
import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from tempfile import mkdtemp

from wetterdienst.exceptions import BufrReaderMissingError

log = logging.getLogger(__name__)

#: what the eccodes bindings warn on their first import wherever the library they load is older than
#: the one they recommend (`gribapi/__init__.py`, 2.42.0 in eccodes 2.48 and 2.49). Matched from
#: the start of the message, as `warnings` does, and on nothing else they might say
_ECCODES_VERSION_ADVICE = r"ecCodes [0-9.]+ or higher is recommended"


def quiet_eccodes_version_advice() -> None:
    """Ignore the eccodes bindings' advice to upgrade the library, and only that.

    Distribution libraries are older than the bindings recommend -- Debian trixie ships 2.41, Ubuntu
    24.04 2.34 -- and decode the BUFR this package reads all the same, so the advice reached every
    process that read BUFR as a warning nobody could act on (GH-2442). `ensure_eccodes` logs the
    library's version at debug in its place.

    One filter, installed once and left in place, scoped to the message and to the bindings'
    `gribapi` modules, which give it: any other warning, and this message from anywhere else, still
    reaches the caller. The bindings give the advice once, as `gribapi` is first imported, so a
    filter left after that hides nothing further, unless `gribapi` is imported afresh -- and a
    caller who imported eccodes before this ran has seen it already. The subsets warning `dwd/road`
    leaves alone is the other case: pdbufr gives it on every read it applies to, so a filter left
    for it would go on hiding it from anything else reading BUFR.

    Put first, ahead of the caller's filters. Appended, it lost to any broad one: `-X dev` and
    `-W default` showed the advice as before, and `-W error` -- or a test suite's `filterwarnings =
    error` -- raised it inside `import eccodes`, which `ensure_eccodes` reads as a reader that did
    not load, so the caller was told to install what they have. A caller who wants the advice gets
    it by importing eccodes before this runs.

    Called by both probes, and by `read_radar_bufr`, the one reader that can run without asking
    them first. Once `gribapi` is imported the advice has been given or not, and this does nothing:
    every change to the filters makes Python forget which warnings it has shown once, so it should
    not change them for nothing. Until then it is not cached, but asked each time -- a
    `catch_warnings` that was open when it ran, a test's or another thread's, puts back a list
    without it on the way out, and a cache would go on saying it is there. Where the bindings are not
    installed at all -- no `bufr` extra -- there is nothing to quiet, and the filters are left alone
    too.
    """
    if "gribapi" in sys.modules or importlib.util.find_spec("gribapi") is None:
        return
    warnings.filterwarnings(
        "ignore",
        message=_ECCODES_VERSION_ADVICE,
        category=UserWarning,
        # the package and its submodules, and not a module whose name merely starts the same
        module=r"gribapi(\.|$)",
    )


def import_pyproj_before_eccodes() -> None:
    """Import pyproj, where it is installed, before the eccodes bindings load their library.

    On Linux, the eccodes wheel pulls in the eckitlib wheel, which bundles its own PROJ, and
    findlibs loads it with `RTLD_GLOBAL`. pyproj bundles another. A process that loads eccodes and
    then imports pyproj aborts at exit (`double free or corruption`, exit 134 or 139), while one
    that imports pyproj first exits cleanly: ecmwf/eckit#354, GH-2441. pyproj comes with the
    `radarplus` extra and with libraries such as geopandas, so a caller reading DWD road or radar
    BUFR could not tell what they had done to get a failing exit status (GH-2468). Drop this once
    the floor requires an eckitlib with the upstream fix.

    Called by both probes, and by `read_radar_bufr`, the one reader that can run without asking
    them first; DWD road's reader asks `require_bufr` before it imports pdbufr. Where the bindings
    are loaded already the order is settled, and importing pyproj then would only make the abort
    reachable for a process that never imports it. Where the bindings are not installed there is
    nothing to put pyproj ahead of, and where pyproj is not -- a `bufr` install without
    `radarplus` -- nothing to import, which is the ordinary case and not logged. A pyproj that is
    installed and does not import is left to whoever imports it next: reading BUFR does not need it.

    pyproj is imported even where `sys.modules` has it already: another thread may be part way
    through that import, and the import statement waits for it to finish where a look at
    `sys.modules` would not.
    """
    if "gribapi" in sys.modules or importlib.util.find_spec("gribapi") is None:
        return
    try:
        # inside, as `find_spec` raises for a module in `sys.modules` whose `__spec__` is None
        if importlib.util.find_spec("pyproj") is None:
            return
        import pyproj  # noqa: F401, PLC0415
    except Exception:
        # installed and does not import -- a broken install, or, under `-W error`, the warning
        # pyproj gives on import where it finds no PROJ data directory. Not this function's to
        # report: the caller hears of it on their own import of pyproj, if they make one
        log.debug("pyproj did not import ahead of eccodes", exc_info=True)


@lru_cache
def ensure_eccodes() -> bool:
    """Ensure that eccodes is loaded."""
    try:
        # inside, as everything on the way to the import is: this question is answered, not raised
        import_pyproj_before_eccodes()
        quiet_eccodes_version_advice()
        import eccodes  # noqa: PLC0415

        # asking the library its version is the check that it loaded, not only what is logged
        version = eccodes.eccodes.codes_get_api_version()
        log.debug(f"ecCodes library {version}")
    except ModuleNotFoundError as e:
        if e.name in (None, "eccodes"):
            # not installed -- or nothing to go on, in which case the quiet path is the one
            # that was here before. `require_bufr` already knows how to explain absence
            return False
        # something *inside* it is missing -- a broken install raises `No module named
        # 'gribapi.bindings'` from within the package, which is the case the advice cannot help
        log.warning(f"eccodes is installed but {e.name} is missing", exc_info=True)
        return False
    except Exception:
        # installed, and it did not work. The plain ImportError of a binding with no compiled
        # library behind it ("libeccodes.so: cannot open shared object file"), a RuntimeError out
        # of gribapi, an AttributeError if `eccodes.eccodes` ever moves -- one answer for all of
        # them, and naming the ones seen so far is how this came to be widened twice already.
        # Whatever it was, it happened on the way to decoding, and a question that raises is no use
        # to `_attach_bufr`, which logs and carries on, nor to the constant the suite computes
        # while collecting, where a raise ends the collection
        log.warning("eccodes is installed but did not load", exc_info=True)
        return False
    return True


@lru_cache
def ensure_pdbufr() -> bool:
    """Ensure that pdbufr is loaded.

    Any `RuntimeError` out of the import is an answer and not an incident. It used to be read for
    the words "Cannot find the ecCodes library" and re-raised otherwise, which is gribapi's current
    phrasing and no promise -- and this question is asked from two places that cannot take a raise:
    `_attach_bufr`, documented to log and carry on rather than fail a query, and the `BUFR_AVAILABLE`
    the test suite computes while collecting, where raising aborts the collection instead of
    skipping the tests that need a reader. Whatever went wrong, it went wrong on the way to reading
    BUFR, which is the whole of what this answers.
    """
    try:
        # pdbufr imports eccodes, so where this is asked first the import of eccodes is this one.
        # The version is left to `ensure_eccodes`, which `bufr_is_available` asks first
        import_pyproj_before_eccodes()
        quiet_eccodes_version_advice()
        import pdbufr  # noqa: F401, PLC0415
    except ModuleNotFoundError as e:
        if e.name in (None, "pdbufr", "eccodes"):
            # pdbufr requires eccodes, so an absent eccodes surfaces from this import as well --
            # still absence, and `require_bufr` covers it. Matched on the whole name and not a
            # prefix of it, as in the sibling probe above: `eccodes.eccodes` missing means eccodes
            # is *there* and broken, which is what the warning below is for
            return False
        log.warning(f"pdbufr is installed but {e.name} is missing", exc_info=True)
        return False
    except Exception:
        # as above: anything out of this import is an answer, not an incident
        log.warning("pdbufr is installed but did not import", exc_info=True)
        return False
    return True


@lru_cache
def bufr_is_available() -> bool:
    """Whether this environment can decode BUFR at all.

    Both halves, because neither is sufficient: `eccodes` imports without the compiled library
    behind it and only fails when asked its version, and `pdbufr` without `eccodes` reads nothing.
    Asking for one and getting the other's absence is how a missing dependency turns into a
    traceback out of the middle of a parse.
    """
    return ensure_eccodes() and ensure_pdbufr()


def require_bufr(what: str) -> None:
    """Refuse a request this environment cannot decode, saying what to install.

    Args:
        what: the data being asked for, named in the message

    Raises:
        ImportError: where either half of the BUFR reader is missing or not working

    """
    if not bufr_is_available():
        msg = (
            f"{what} is published as BUFR, which needs eccodes and pdbufr to read: "
            f"`pip install wetterdienst[bufr]` installs both. They decode through a compiled "
            f"eccodes library, which most platforms get as a wheel; where yours does not, it "
            f"comes from `apt install libeccodes-dev` or `brew install eccodes`."
        )
        raise BufrReaderMissingError(msg)


@contextmanager
def bufr_file(content: bytes) -> Iterator[Path]:
    """Write BUFR bytes to a file of their own, for a reader that opens it by name.

    pdbufr reads BUFR from a file it opens itself, not from bytes in memory. The file is written and
    closed before the path is handed over, in a directory that goes again on the way out: Windows
    refuses to open a file a second time while a `NamedTemporaryFile` holds it open, so on Windows
    every read through one failed with `PermissionError` (GH-2446).

    A directory that cannot be removed -- on Windows, a file something else still holds open, such
    as a virus scanner reading what was just written -- is logged and left behind, rather than
    raised after a read that worked or in place of the read's own error.

    Args:
        content: the BUFR message(s), as published

    Yields:
        the path of the file holding them

    """
    directory = Path(mkdtemp(prefix="wetterdienst-bufr-"))
    try:
        path = directory / "message.bufr"
        path.write_bytes(content)
        yield path
    finally:
        try:
            shutil.rmtree(directory)
        except OSError as error:
            log.warning(f"Unable to remove the temporary BUFR file {directory}: {error}")
