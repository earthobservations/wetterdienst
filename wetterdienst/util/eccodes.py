# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
def ensure_eccodes() -> bool:
    """Function to ensure that eccodes is loaded"""
    try:
        import eccodes

        eccodes.eccodes.codes_get_api_version()
    except (ModuleNotFoundError, RuntimeError):
        return False
    return True


def ensure_pdbufr() -> bool:
    """Function to ensure that pdbufr is loaded"""
    try:
        import pdbufr  # noqa: F401
    except ImportError:
        return False
    return True


def check_pdbufr():
    """ensure pdbufr is installed before doing anything else"""
    try:
        import pdbufr  # noqa: F401
    except ImportError as e:
        raise ImportError("pdbufr is required for reading DWD Road Observations.") from e
