# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Example for DWD MOSMIX acquisition.

This program will request latest MOSMIX-L data for
stations 01001 and 01008 and parameters DD and ww.

Other MOSMIX variants are also listed and can be
enabled on demand.
"""
from wetterdienst.provider.dwd.forecast import (
    DwdForecastDate,
    DwdMosmixRequest,
    DwdMosmixType,
)
from wetterdienst.util.cli import setup_logging


def mosmix_example():

    # A. MOSMIX-L -- Specific stations - each station with own file
    request = DwdMosmixRequest(
        parameter=["DD", "ww"],
        start_issue=DwdForecastDate.LATEST,  # automatically set if left empty
        mosmix_type=DwdMosmixType.LARGE,
        tidy=True,
        humanize=True,
    )

    stations = request.filter_by_station_id(
        station_id=["01001", "01008"],
    )

    response = next(stations.values.query())

    # meta data enriched with information from metadata_for_forecasts()
    output_section("Metadata", response.stations.df)
    output_section("Forecasts", response.df)

    # B. MOSMIX-S -- All stations - specified stations are extracted.

    request = DwdMosmixRequest(
        parameter=["DD", "ww"],
        start_issue=DwdForecastDate.LATEST,  # automatically set if left empty
        mosmix_type=DwdMosmixType.SMALL,
        tidy=True,
        humanize=True,
    )

    stations = request.filter_by_station_id(
        station_id=["01001", "01008"],
    )

    response = next(stations.values.query())

    output_section("Metadata", response.stations.df)
    output_section("Forecasts", response.df)


def output_section(title, data):  # pragma: no cover
    print("-" * len(title))
    print(title)
    print("-" * len(title))
    print(data)
    print()


def main():
    setup_logging()
    mosmix_example()


if __name__ == "__main__":
    main()
