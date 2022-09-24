# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=======================
List of DWD radar sites
=======================

Sources
=======
- April, 2018: https://www.dwd.de/DE/derdwd/messnetz/atmosphaerenbeobachtung/_functions/HaeufigGesucht/koordinaten-radarverbund.pdf?__blob=publicationFile
- October, 2020: https://www.dwd.de/DE/leistungen/radolan/radolan_info/radolan_radvor_op_komposit_format_pdf.pdf?__blob=publicationFile

References
==========
- https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_network.html
- https://github.com/wradlib/wradlib-notebooks/blob/v1.8.0/notebooks/radolan/radolan_network.ipynb
"""  # noqa:B950,E501
from enum import Enum
from typing import Dict

import pandas as pd


class DwdRadarSite(Enum):
    """
    Enumerate short names of all radar sites.
    """

    ASB = "asb"
    BOO = "boo"
    DRS = "drs"
    EIS = "eis"
    ESS = "ess"
    FBG = "fbg"
    FLD = "fld"
    HNR = "hnr"
    ISN = "isn"
    MEM = "mem"
    NEU = "neu"
    NHB = "nhb"
    OFT = "oft"
    PRO = "pro"
    ROS = "ros"
    TUR = "tur"
    UMD = "umd"


class DwdRadarSitesGenerator:  # pragma: no cover
    """
    Parse list of sites from PDF documents [1,2] and output as Python dictionary.

    [1] https://www.dwd.de/DE/derdwd/messnetz/atmosphaerenbeobachtung/_functions/HaeufigGesucht/koordinaten-radarverbund.pdf?__blob=publicationFile
    [2] https://www.dwd.de/DE/leistungen/radolan/radolan_info/radolan_radvor_op_komposit_format_pdf.pdf?__blob=publicationFile
    """  # noqa:B950,E501

    url = (
        "https://www.dwd.de/DE/derdwd/messnetz/atmosphaerenbeobachtung/_functions"
        "/HaeufigGesucht/koordinaten-radarverbund.pdf?__blob=publicationFile"
    )

    def all(self) -> Dict:  # pragma: no cover
        """
        Build dictionary from DataFrame containing radar site information.
        """
        df = self.read_pdf()
        result = {}
        for item in df.to_dict(orient="records"):
            key = item["dwd_id"]
            value = item
            result[key] = value
        return result

    def read_pdf(self) -> pd.DataFrame:
        """
        Parse PDF file and build DataFrame containing radar site information.
        """

        # Read table from PDF.
        import tabula

        df = tabula.read_pdf(self.url, multiple_tables=False, pages=1)[0]

        # Set column names.
        df.columns = [
            "name",
            "dwd_id",
            "wmo_id",
            "coordinates_wgs84_text",
            "coordinates_wgs84",
            "coordinates_gauss",
            "altitude",
        ]

        # Adjust offsets.
        for column in ["name", "dwd_id", "wmo_id", "altitude"]:
            df[column] = df[column].shift(-1)

        # Remove header rows.
        df = df.shift(-8)

        # Drop empty rows.
        df = df.dropna(axis="index", how="all")

        # Select each second row, starting from first one.
        firsts = df.iloc[::2]

        # Select each second row, starting from second one.
        seconds = df.iloc[1::2]

        # Mungle into one coherent data frame.
        data = firsts
        data = data.drop(labels=["coordinates_wgs84_text", "coordinates_gauss"], axis="columns")
        data = data.rename(columns={"coordinates_wgs84": "latitude"})
        data.insert(4, "longitude", seconds["coordinates_wgs84"].values)
        data = data.reset_index(drop=True)

        for column in ["latitude", "longitude"]:
            data[column] = data[column].apply(lambda x: x.strip("NE").replace(",", ".")).apply(float)

        for column in ["wmo_id", "altitude"]:
            data[column] = data[column].apply(int)

        return data


if __name__ == "__main__":  # pragma: no cover
    """
    Setup
    =====
    ::

        pip install tabula-py pout black


    Synopsis
    ========
    ::

        python wetterdienst/provider/dwd/radar/sites.py
    """

    import pprint

    import black

    sites = DwdRadarSitesGenerator().all()
    print(black.format_str(pprint.pformat(sites), mode=black.Mode()))  # noqa: T201
