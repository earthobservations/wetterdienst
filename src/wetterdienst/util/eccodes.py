# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""BUFR decoding availability for the wetterdienst package.

Decoding BUFR takes two halves that fail independently: `pdbufr`, which reads the messages, and
`eccodes`, the binding to the compiled library that does the decoding. `pdbufr` requires `eccodes`,
so a working install has both -- but the binding imports happily with no library behind it, and
only says so when asked for a version. Neither half alone answers "can this environment read
BUFR", which is the only question any caller has: use `bufr_is_available` for that, or
`require_bufr` where the answer has to be no further than the first line of a method.
"""

from functools import lru_cache


@lru_cache
def ensure_eccodes() -> bool:
    """Ensure that eccodes is loaded."""
    try:
        import eccodes  # noqa: PLC0415

        eccodes.eccodes.codes_get_api_version()
    except (ModuleNotFoundError, RuntimeError):
        return False
    return True


@lru_cache
def ensure_pdbufr() -> bool:
    """Ensure that pdbufr is loaded."""
    try:
        import pdbufr  # noqa: F401, PLC0415
    except ImportError:
        return False
    except RuntimeError as e:
        # pdbufr may raise a RuntimeError if the underlying ecCodes library is not found, which is a common issue
        # and should be treated as a missing dependency rather than a critical error
        if "Cannot find the ecCodes library" in str(e):
            return False
        raise
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
            f"{what} is published as BUFR, which needs eccodes and pdbufr to read. "
            f"Install them with `pip install wetterdienst[bufr]`, which carries both, and a "
            f"compiled eccodes library -- `apt install libeccodes-dev` or `brew install eccodes` "
            f"-- where your platform has no wheel for one."
        )
        raise ImportError(msg)
