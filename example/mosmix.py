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
from wetterdienst.util.cli import setup_logging
from wetterdienst.dwd.mosmix import MOSMIXReader


def mosmix_example():

    # A. MOSMIX-L -- Specific stations
    # mosmix = MOSMIXReader(station_ids=['01001', '01008'], parameters=['DD', 'ww'])
    mosmix = MOSMIXReader(station_ids=["01001", "01008"])
    response = mosmix.read_mosmix_l_latest()

    # B. MOSMIX-S -- All stations.
    # Remark: This will take **some** time for downloading and parsing ~40MB worth of XML.
    # mosmix = MOSMIXReader(station_ids=['01028', '01092'])
    # mosmix = MOSMIXReader(station_ids=['01028', '01092'], parameters=['DD', 'ww'])
    # response = mosmix.read_mosmix_s_latest()

    # C. MOSMIX-L -- All stations.
    # Remark: This will take **ages** for downloading and parsing ~80MB worth of XML.
    # mosmix = MOSMIXReader()
    # response = mosmix.read_mosmix_l_latest()

    response.forecasts = response.forecasts.dropna(axis='columns', how='all')

    output_section("Metadata", response.metadata)
    output_section("Stations", response.stations)
    output_section("Forecasts", response.forecasts)


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
