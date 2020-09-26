from enum import Enum

""" metadata about radar sites """
RADAR_LOCATIONS = {
    "asb": {
        "site_name": "ASR Borkum",
        "location_id": 10103,
        "latitude": 53.564011,
        "longitude": 6.748292,
    },
    "boo": {
        "site_name": "Boostedt",
        "location_id": 10132,
        "latitude": 54.004381,
        "longitude": 10.046899,
    },
    "drs": {
        "site_name": "Dresden",
        "location_id": 10488,
        "latitude": 51.124639,
        "longitude": 13.768639,
    },
    "eis": {
        "site_name": "Eisberg",
        "location_id": 10780,
        "latitude": 49.540667,
        "longitude": 12.402788,
    },
    "ess": {
        "site_name": "Essen",
        "location_id": 10410,
        "latitude": 51.405649,
        "longitude": 6.967111,
    },
    "fbg": {
        "site_name": "Feldberg",
        "location_id": 10908,
        "latitude": 47.873611,
        "longitude": 8.003611,
    },
    "fld": {
        "site_name": "Flechtdorf",
        "location_id": 10440,
        "latitude": 51.311197,
        "longitude": 8.801998,
    },
    "isn": {
        "site_name": "Isen",
        "location_id": 10873,
        "latitude": 48.174705,
        "longitude": 12.101779,
    },
    "hnr": {
        "site_name": "Hannover",
        "location_id": 10339,
        "latitude": 52.460083,
        "longitude": 9.694533,
    },
    "mem": {
        "site_name": "Memmingen",
        "location_id": 10950,
        "latitude": 48.042145,
        "longitude": 10.219222,
    },
    "neu": {
        "site_name": "Neuhausen",
        "location_id": 10557,
        "latitude": 50.500114,
        "longitude": 11.135034,
    },
    "nhb": {
        "site_name": "Neuheilenbach",
        "location_id": 10605,
        "latitude": 50.109656,
        "longitude": 6.548328,
    },
    "oft": {
        "site_name": "Offenthal",
        "location_id": 10629,
        "latitude": 49.984745,
        "longitude": 8.712933,
    },
    "pro": {
        "site_name": "Prötzel",
        "location_id": 10392,
        "latitude": 52.648667,
        "longitude": 13.858212,
    },
    "ros": {
        "site_name": "Rostock",
        "location_id": 10169,
        "latitude": 54.175660,
        "longitude": 12.058076,
    },
    "tur": {
        "site_name": "Türkheim",
        "location_id": 10832,
        "latitude": 48.585379,
        "longitude": 9.782675,
    },
    "umd": {
        "site_name": "Ummendorf",
        "location_id": 10356,
        "latitude": 52.160096,
        "longitude": 11.176091,
    },
}

""" enumeration for Radar Sites """


class RadarSites(Enum):
    """
    enumeration for the different radar locations/sites
    """

    ASB = "asb"
    BOO = "boo"
    DRS = "drs"
    EIS = "eis"
    ESS = "ess"
    FGB = "fbg"
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
