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
