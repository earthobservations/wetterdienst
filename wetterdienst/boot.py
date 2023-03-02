# """Wetterdienst - Open weather data for humans"""
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.


def monkeypatch():
    from wetterdienst.monkeypatch import fsspec_monkeypatch

    fsspec_monkeypatch.activate()


def get_version(appname):
    from importlib.metadata import PackageNotFoundError, version  # noqa

    try:
        return version(appname)
    except PackageNotFoundError:  # pragma: no cover
        return "unknown"


def info() -> None:
    """Print basic information about the wetterdienst package"""
    from wetterdienst import Settings, __version__

    wd_info = {
        "version": __version__,
        "authors": "Benjamin Gutzmann <gutzemann@gmail.com>, Andreas Motl <andreas.motl@panodata.org>",
        "documentation": "https://wetterdienst.readthedocs.io/",
        "repository": "https://github.com/earthobservations/wetterdienst",
        "cache_dir (default)": Settings().cache_dir,
    }

    text = get_title("Wetterdienst - Open weather data for humans")

    for key, value in wd_info.items():
        text += f"\n{key}:\t {value}"

    print(text)  # noqa: T201

    return


def get_title(text: str) -> str:
    line = "=" * len(text)
    return f"{line}\n{text}\n{line}"
