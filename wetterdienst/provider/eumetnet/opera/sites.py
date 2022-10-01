# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import gzip
import json
from typing import Dict, List

import pkg_resources
import requests


class OperaRadarSites:
    """
    Provide information about all European OPERA radar sites.
    """

    data_file = pkg_resources.resource_filename(__name__, "sites.json.gz")

    def __init__(self):
        self.sites = self.load()

    def load(self) -> List[Dict]:
        """
        Load and decode JSON file from filesystem.
        """
        with gzip.open(self.data_file, mode="rt") as fp:
            return json.load(fp)

    def all(self) -> List[Dict]:
        """
        The whole list of OPERA radar sites.
        """
        return self.sites

    def asdict(self) -> Dict:
        """
        Dictionary of sites, keyed by ODIM code.
        """
        result = {}
        for site in self.sites:
            if site["odimcode"] is None:
                continue
            result[site["odimcode"]] = site
        return result

    def by_odimcode(self, odimcode: str) -> Dict:
        """
        Return radar site by ODIM code.

        :param odimcode:
        :return:
        """
        if not (len(odimcode) == 3 or len(odimcode) == 5):
            raise ValueError("ODIM code must be three or five letters")
        for site in self.sites:
            if site["odimcode"] and odimcode.lower() in site["odimcode"]:
                return site
        else:
            raise KeyError("Radar site not found")

    def by_wmocode(self, wmocode: int) -> Dict:
        """
        Return radar site by WMO code.

        :param wmocode:
        :return:
        """
        for site in self.sites:
            if site["wmocode"] == wmocode:
                return site
        else:
            raise KeyError("Radar site not found")

    def by_countryname(self, name: str) -> List[Dict]:
        """
        Filter list of radar sites by country name.

        :param name: The country name, e.g. "Germany", "United Kingdom".
        :return:     List of site information.
        """
        sites = list(
            filter(
                lambda site: site["country"] and site["country"].lower() == name.lower(),
                self.sites,
            )
        )
        if not sites:
            raise KeyError("No radar sites for this country")
        return sites


class OperaRadarSitesGenerator:
    """
    Parse list of OPERA sites published by EUMETNET.

    https://www.eumetnet.eu/wp-content/themes/aeron-child/observations-programme/current-activities/opera/database/OPERA_Database/OPERA_RADARS_DB.json
    """

    url = (
        "https://www.eumetnet.eu/wp-content/themes/aeron-child/observations-programme/"
        "current-activities/opera/database/OPERA_Database/OPERA_RADARS_DB.json"
    )

    def get_opera_radar_sites(self) -> List[Dict]:  # pragma: no cover

        data = requests.get(self.url).json()

        # Filter empty elements and convert data types.
        integer_values = ["maxrange", "number", "startyear", "status", "wmocode"]
        float_values = [
            "beam",
            "diametrantenna",
            "frequency",
            "gain",
            "heightantenna",
            "heightofstation",
            "latitude",
            "longitude",
        ]
        boolean_values = ["doppler", "status"]

        def asbool(obj):
            # from sqlalchemy.util.asbool
            if isinstance(obj, str):
                obj = obj.strip().lower()
                if obj in ["true", "yes", "on", "y", "t", "1"]:
                    return True
                elif obj in ["false", "no", "off", "n", "f", "0"]:
                    return False
                else:
                    raise ValueError("String is not true/false: %r" % obj)
            return bool(obj)

        def convert_types(element):
            converted = {}
            for key, value in element.items():
                try:
                    if key in integer_values:
                        value = int(value)
                    if key in float_values:
                        value = float(value)
                    if key in boolean_values:
                        value = asbool(value)
                    if value == "":
                        value = None
                except Exception:  # noqa: S110
                    value = None
                converted[key] = value
            return converted

        def filter_and_convert(elements):
            for element in elements:
                if element["location"] and element["latitude"] and element["longitude"]:
                    yield convert_types(element)

        return list(filter_and_convert(data))

    def to_json(self) -> str:
        """
        Return JSON representation of all sites.
        """
        sites = self.get_opera_radar_sites()
        return json.dumps(sites, indent=4)

    def export(self):
        """
        Generate "sites.json.gz".
        """
        sites = self.get_opera_radar_sites()
        with gzip.open(OperaRadarSites.data_file, mode="wt", compresslevel=9, encoding="utf-8") as fp:
            json.dump(sites, fp, indent=4)


if __name__ == "__main__":  # pragma: no cover
    """
    Generate "sites.json.gz".

    Synopsis::

        python wetterdienst/provider/eumetnet/opera/sites.py
    """
    orsg = OperaRadarSitesGenerator()
    orsg.export()
