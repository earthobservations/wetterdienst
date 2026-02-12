# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""eccodes utilities for the wetterdienst package."""

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
