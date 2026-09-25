"""
About
=====

Demo for querying Australian Bureau of Meteorology's Water Data Online (WDO) service.

It uses `kiwis-pie`, a Python library for querying a WISKI system using the KiWIS
(KISTERS Web Interoperability Solution) interface.


Setup
=====
::

    pip install kiwis-pie


Synopsis
========
::

    python -m wetterdienst.provider.bom.wdo


References
==========

- http://www.bom.gov.au/waterdata/
- http://www.bom.gov.au/waterdata/services
- https://github.com/amacd31/kiwis_pie
- https://www.kisters.com.au/wiski-modules.html
- https://kiwis.kisters.de/KiWIS/

"""
from datetime import date
from pprint import pprint

from kiwis_pie import KIWIS


class BomWdoAccess:
    def __init__(self):
        # Introduction.
        print_header("About")
        print(__doc__)
        self.kiwis = KIWIS("http://www.bom.gov.au/waterdata/services")

    def display_index(self):

        # Retrieve list of sites.
        print_header("List of all sites")
        sites = self.kiwis.get_site_list()
        print(sites)
        print()

        # Retrieve list of stations.
        print_header("List of all stations")
        stations = self.kiwis.get_station_list()
        print(stations)
        print()

        # Retrieve list of parameters.
        print_header("List of all parameters")
        parameters = self.kiwis.get_parameter_list()
        print(parameters)
        print()

        # Retrieve list of parameter types.
        print_header("List of all parameter types")
        parameter_types = self.kiwis.get_parameter_type_list()
        print(parameter_types)
        print()

    def display_details(
        self, station_name, timeseries_name, parameter_type, date_from, date_to
    ):

        # Get station information by station name.
        station = self.kiwis.get_station_list(station_name=station_name)

        # Display station information.
        print_header(f'Station information for "{station_name}"')
        pprint(station.to_dict(orient="list"))
        print()

        # Resolve station name to station identifier.
        station_id = station.station_id.values[0]

        # Retrieve list of timeseries.
        print_header(f'List of all timeseries for station "{station_name}"')
        timeseries = self.kiwis.get_timeseries_list(station_id=station_id)
        print(timeseries)
        print()

        # Get ready.
        print_header(
            f'One month worth of "{parameter_type}" data from "{station_name}"'
        )
        print()

        # Resolve timeseries name to timeseries identifier for specific station.
        timeseries_id = self.kiwis.get_timeseries_list(
            station_id=station_id,
            ts_name=timeseries_name,
            parametertype_name=parameter_type,
        ).ts_id.values[0]

        # Acquire values.
        data = self.kiwis.get_timeseries_values(
            ts_id=timeseries_id, to=date_to, **{"from": date_from}
        )

        # Display dataset information.
        print_header("Dataset information")
        print(f"Station name:    {station_name}")
        print(f"Station ID:      {station_id}")
        print(f"Timeseries name: {timeseries_name}")
        print(f"Timeseries ID:   {timeseries_id}")
        print(f"Parameter Type:  {parameter_type}")
        print()

        # Display data.
        print_header("Data")
        print(data)
        print()

        # Optionally use the `keep_tz` option to return in local timezone instead of UTC.
        # k.get_timeseries_values(ts_id=ts_id, to=date(2016, 1, 31), **{"from": date(2016, 1, 1)}, keep_tz=True)  # noqa: E501


def print_header(label):
    length = max(len(label), 42)
    print("-" * length)
    print(label.center(length))
    print("-" * length)


def main():
    bom = BomWdoAccess()

    # Acquire and display list of available sites, stations, parameters
    # and parameter types.
    bom.display_index()

    # Acquire and display 31 days worth of "daily water course discharge"
    # data for "Cotter River at Gingera" from the "daily mean streamflow (Q)"
    # timeseries.
    bom.display_details(
        station_name="Cotter R. at Gingera",
        timeseries_name="DMQaQc.Merged.DailyMean.24HR",
        parameter_type="Water Course Discharge",
        date_from=date(2016, 1, 1),
        date_to=date(2016, 1, 31),
    )


if __name__ == "__main__":
    """
    Synopsis::

        python -m wetterdienst.provider.bom.wdo
    """
    main()
