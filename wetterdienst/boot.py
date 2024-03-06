# """Wetterdienst - Open weather data for humans"""
# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.


def get_version(appname):
    from importlib.metadata import PackageNotFoundError, version  # noqa

    try:
        return version(appname)
    except PackageNotFoundError:  # pragma: no cover
        return "unknown"
