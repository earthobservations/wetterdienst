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

from __future__ import annotations

from enum import Enum

import polars as pl


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

    def all(self) -> dict:  # pragma: no cover  # noqa: A003
        """
        Build dictionary from DataFrame containing radar site information.
        """
        df = self.read_pdf()
        result = {}
        for item in df.to_dicts():
            key = item["dwd_id"]
            value = item
            result[key] = value
        return result

    def read_pdf(self) -> pl.DataFrame:
        """
        Parse PDF file and build DataFrame containing radar site information.
        """

        # Read table from PDF.
        import tabula

        df = tabula.read_pdf(self.url, multiple_tables=False, pages=1)[0]

        df = pl.from_pandas(df)

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
        df = df.filter(~pl.fold(True, lambda acc, s: acc & s.is_null(), pl.all()))

        # Select each second row, starting from first one.
        firsts = df[::2, :]

        # Select each second row, starting from second one.
        seconds = df[1::2, :]

        # Mungle into one coherent data frame.
        data = firsts
        data = data.drop("coordinates_wgs84_text", "coordinates_gauss")
        data = data.rename(mapping={"coordinates_wgs84": "latitude"})
        data = data.with_columns(seconds.get_column("coordinates_wgs84").alias("longitude"))
        return data.with_columns(
            pl.col("latitude").str.strip_chars("NE").str.replace(",", ".").cast(float),
            pl.col("longitude").str.strip_chars("NE").str.replace(",", ".").cast(float),
            pl.col("wmo_id").cast(int),
            pl.col("altitude").cast(int),
        )


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
