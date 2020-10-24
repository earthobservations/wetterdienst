"""
List of DWD radar sites.

- https://www.dwd.de/DE/derdwd/messnetz/atmosphaerenbeobachtung/_functions/HaeufigGesucht/koordinaten-radarverbund.pdf?__blob=publicationFile  # noqa:E501,B950
- https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_network.html
- https://github.com/wradlib/wradlib-notebooks/blob/v1.8.0/notebooks/radolan/radolan_network.ipynb
"""
from enum import Enum

import pandas as pd
import warnings


""" Information about all radar sites """
RADAR_LOCATIONS = {
    "ASB": {
        "name": "ASR Borkum",
        "dwd_id": "ASB",
        "wmo_id": 10103,
        "latitude": 53.564011,
        "longitude": 6.748292,
        "altitude": 36,
    },
    "BOO": {
        "name": "Boostedt",
        "dwd_id": "BOO",
        "wmo_id": 10132,
        "latitude": 54.004381,
        "longitude": 10.046899,
        "altitude": 125,
    },
    "DRS": {
        "name": "Dresden",
        "dwd_id": "DRS",
        "wmo_id": 10488,
        "latitude": 51.124639,
        "longitude": 13.768639,
        "altitude": 263,
    },
    "EIS": {
        "name": "Eisberg",
        "dwd_id": "EIS",
        "wmo_id": 10780,
        "latitude": 49.540667,
        "longitude": 12.402788,
        "altitude": 799,
    },
    "ESS": {
        "name": "Essen",
        "dwd_id": "ESS",
        "wmo_id": 10410,
        "latitude": 51.405649,
        "longitude": 6.967111,
        "altitude": 185,
    },
    "FBG": {
        "name": "Feldberg",
        "dwd_id": "FBG",
        "wmo_id": 10908,
        "latitude": 47.873611,
        "longitude": 8.003611,
        "altitude": 1516,
    },
    "FLD": {
        "name": "Flechtdorf",
        "dwd_id": "FLD",
        "wmo_id": 10440,
        "latitude": 51.311197,
        "longitude": 8.801998,
        "altitude": 628,
    },
    "HNR": {
        "name": "Hannover",
        "dwd_id": "HNR",
        "wmo_id": 10339,
        "latitude": 52.460083,
        "longitude": 9.694533,
        "altitude": 98,
    },
    "ISN": {
        "name": "Isen",
        "dwd_id": "ISN",
        "wmo_id": 10873,
        "latitude": 48.174705,
        "longitude": 12.101779,
        "altitude": 678,
    },
    "MEM": {
        "name": "Memmingen",
        "dwd_id": "MEM",
        "wmo_id": 10950,
        "latitude": 48.042145,
        "longitude": 10.219222,
        "altitude": 724,
    },
    "NEU": {
        "name": "Neuhaus",
        "dwd_id": "NEU",
        "wmo_id": 10557,
        "latitude": 50.500114,
        "longitude": 11.135034,
        "altitude": 880,
    },
    "NHB": {
        "name": "Neuheilenbach",
        "dwd_id": "NHB",
        "wmo_id": 10605,
        "latitude": 50.109656,
        "longitude": 6.548328,
        "altitude": 586,
    },
    "OFT": {
        "name": "Offenthal",
        "dwd_id": "OFT",
        "wmo_id": 10629,
        "latitude": 49.984745,
        "longitude": 8.712933,
        "altitude": 246,
    },
    "PRO": {
        "name": "Prötzel",
        "dwd_id": "PRO",
        "wmo_id": 10392,
        "latitude": 52.648667,
        "longitude": 13.858212,
        "altitude": 194,
    },
    "ROS": {
        "name": "Rostock",
        "dwd_id": "ROS",
        "wmo_id": 10169,
        "latitude": 54.17566,
        "longitude": 12.058076,
        "altitude": 37,
    },
    "TUR": {
        "name": "Türkheim",
        "dwd_id": "TUR",
        "wmo_id": 10832,
        "latitude": 48.585379,
        "longitude": 9.782675,
        "altitude": 768,
    },
    "UMD": {
        "name": "Ummendorf",
        "dwd_id": "UMD",
        "wmo_id": 10356,
        "latitude": 52.160096,
        "longitude": 11.176091,
        "altitude": 185,
    },
}


class DWDRadarSite(Enum):
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
    ISN = "isn"
    HNR = "hnr"
    MEM = "mem"
    NEU = "neu"
    NHB = "nhb"
    OFT = "oft"
    PRO = "pro"
    ROS = "ros"
    TUR = "tur"
    UMD = "umd"


"""
About
=====
Parse list of sites from PDF document [1] and output as Python dictionary.

[1] https://www.dwd.de/DE/derdwd/messnetz/atmosphaerenbeobachtung/_functions/HaeufigGesucht/koordinaten-radarverbund.pdf?__blob=publicationFile  # noqa:E501,B950


Setup
=====
::

    pip install tabula-py pout black


Synopsis
========
::

    python -m wetterdienst.dwd.radar.sites

"""


def read_dwd_messnetz_pdf(url) -> dict:
    """
    Parse PDF file and build DataFrame containing radar site information.
    """

    # Read table from PDF.
    import tabula

    df = tabula.read_pdf(url, multiple_tables=False, pages=1)[0]

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
    data = data.drop(
        labels=["coordinates_wgs84_text", "coordinates_gauss"], axis="columns"
    )
    data = data.rename(columns={"coordinates_wgs84": "latitude"})
    data.insert(4, "longitude", seconds["coordinates_wgs84"].values)
    data = data.reset_index(drop=True)

    for column in ["latitude", "longitude"]:
        data[column] = (
            data[column].apply(lambda x: x.strip("NE").replace(",", ".")).apply(float)
        )

    for column in ["wmo_id", "altitude"]:
        data[column] = data[column].apply(int)

    return data


def get_dwd_radar_network() -> pd.DataFrame:
    """
    Get DataFrame containing radar site information.
    """
    url = "https://www.dwd.de/DE/derdwd/messnetz/atmosphaerenbeobachtung/_functions/HaeufigGesucht/koordinaten-radarverbund.pdf?__blob=publicationFile"  # noqa:E501,B950
    return read_dwd_messnetz_pdf(url)


def get_dwd_radar_sites() -> dict:
    """
    Build dictionary from DataFrame containing radar site information.
    """
    df = get_dwd_radar_network()
    result = {}
    for item in df.to_dict(orient="records"):
        key = item["dwd_id"]
        value = item
        result[key] = value
    return result


warnings.filterwarnings("ignore", category=RuntimeWarning)

if __name__ == "__main__":
    import pout
    import black

    locations = get_dwd_radar_sites()
    print(black.format_str(pout.ss(locations), mode=black.Mode()))
