# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import gzip
import importlib.resources
import json
from typing import Any

import requests


class OperaRadarSites:
    """
    Provide information about all European OPERA radar sites.
    """

    data_file = importlib.resources.files(__package__) / "sites.json.gz"

    def __init__(self):
        self.sites = self.load()

    def load(self) -> list[dict]:
        """
        Load and decode JSON file from filesystem.
        """
        with importlib.resources.as_file(self.data_file) as rf:
            with gzip.open(rf, mode="rb") as f:
                return json.load(f)

    def all(self) -> list[dict]:  # noqa: A003
        """
        The whole list of OPERA radar sites.
        """
        return self.sites

    def to_dict(self) -> dict:
        """
        Dictionary of sites, keyed by ODIM code.
        """
        result = {}
        for site in self.sites:
            if site["odimcode"] is None:
                continue
            result[site["odimcode"]] = site
        return result

    def by_odim_code(self, odim_code: str) -> dict:
        """
        Return radar site by ODIM code.

        :param odim_code: The ODIM code, e.g. "atrau".
        :return:          Single site information.
        """
        if len(odim_code) not in (3, 5):
            raise ValueError("ODIM code must be three or five letters")
        for site in self.sites:
            if site["odimcode"] and odim_code.lower() in site["odimcode"]:
                return site
        else:
            raise KeyError("Radar site not found")

    def by_wmo_code(self, wmo_code: int) -> dict:
        """
        Return radar site by WMO code.

        :param wmo_code: The WMO code, e.g. 11038.
        :return:        Single site information.
        """
        for site in self.sites:
            if site["wmocode"] == wmo_code:
                return site
        else:
            raise KeyError("Radar site not found")

    def by_country_name(self, country_name: str) -> list[dict]:
        """
        Filter list of radar sites by country name.

        :param country_name: The country name, e.g. "Germany", "United Kingdom".
        :return:             List of site information.
        """
        sites = [site for site in self.sites if site["country"] and site["country"].lower() == country_name.lower()]
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

    def get_opera_radar_sites(self) -> list[dict]:  # pragma: no cover
        data = requests.get(self.url, timeout=10).json()

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

        def asbool(obj: Any) -> bool:
            # from sqlalchemy.util.asbool
            if isinstance(obj, str):
                obj = obj.strip().lower()
                if obj in ["true", "yes", "on", "y", "t", "1"]:
                    return True
                elif obj in ["false", "no", "off", "n", "f", "0"]:
                    return False
                else:
                    raise ValueError(f"String is not true/false: {obj}")
            return bool(obj)

        def convert_types(element: dict) -> dict[str, int | float | bool | None]:
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
                except ValueError:
                    value = None
                converted[key] = value
            return converted

        def filter_and_convert(elements):
            for element in elements:
                if element["location"] and element["latitude"] and element["longitude"]:
                    yield convert_types(element)

        return list(filter_and_convert(data))

    def to_json(self, indent: int = 4) -> str:
        """
        Return JSON representation of all sites.
        """
        sites = self.get_opera_radar_sites()
        return json.dumps(sites, indent=indent)

    def export(self, indent: int = 4):
        """
        Generate "sites.json.gz".
        """
        sites = self.get_opera_radar_sites()
        with importlib.resources.as_file(OperaRadarSites.data_file) as rf:
            with gzip.open(rf, mode="wt", compresslevel=9, encoding="utf-8") as f:
                json.dump(sites, f, indent=indent)


if __name__ == "__main__":  # pragma: no cover
    """
    Generate "sites.json.gz".

    Synopsis::

        python wetterdienst/provider/eumetnet/opera/sites.py
    """
    orsg = OperaRadarSitesGenerator()
    orsg.export()
