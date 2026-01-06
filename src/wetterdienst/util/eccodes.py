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
    return True


@lru_cache
def check_pdbufr() -> None:
    """Ensure pdbufr is installed before doing anything else."""
    try:
        import pdbufr  # noqa: F401, PLC0415
    except ImportError as e:
        msg = "pdbufr is required for reading DWD Road Observations."
        raise ImportError(msg) from e
