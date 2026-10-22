# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The ids of the data files of a network, to hold its station catalogue to the coverage rules (GH-3248).

A catalogue that breaks none of the rules of `station_catalogue.py` can still list a station that answers nothing, or
leave out a station whose data is there: a caller never finds the second, and the first is every request that names
it. Both show only against the data, so `DataIndex.ids` reads, for one resolution and dataset, the ids of the data
files of a network from the listing or feed its provider reads (the directories of `dwd/observation` and
`dwd/derived`, the feed of `ipma/observation`), or from the listing it would have to read (the directories of
`chmi/observation`, the STAC collection of `meteoswiss/observation`). `check_coverage` then holds the catalogue to
`COVERAGE_RULES`.

Two tests apply them: `test_station_coverage.py` to the stub of each network, which serves the listing or feed beside
the catalogue, so that what a reader drops silently (a data file whose station the list does not carry) or lists in
vain shows without the network, and `test_station_catalogues_live.py` to the live lists, for the networks whose index
is cheap to read: a directory listing, or one file the catalogue pass reads anyway.

Every network that has a catalogue is either in `INDEXES` or named in `NOT_HELD` with the reason, and a dataset of a
network in `INDEXES` that has no listing is named in `NOT_HELD_DATASETS`: `test_station_coverage.py` fails for a network
that is neither, so a new provider is held to the rules or says why it cannot be. A network that is held in its stub
and not live says why in `NOT_LIVE`.

The ids go through the downloader or the listing of the provider's own module (`download_file` of
`meteoswiss/observation`, the listing of `dwd/poi`), which is what a stub replaces, so a listing is served where the
catalogue is; `chmi/observation` has no listing of its own, and goes through `list_files` of this module.

The ids of `dwd/observation` and `dwd/derived` are read from the raw listing with a pattern of this module, not through
the file index of the provider: the catalogue is joined to that index, so a name its pattern misses would drop out of
both sides and no rule could fire (GH-3257).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, NamedTuple

from tests.provider.station_catalogue import COVERAGE_RULES, Accepted
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.dwd.derived.fileindex import _build_url_from_dataset_and_period as _derived_url
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.observation.fileindex import _build_url_from_dataset_and_period as _observation_url
from wetterdienst.provider.dwd.observation.fileindex import _create_file_index_for_dwd_server
from wetterdienst.provider.dwd.poi import api as poi_api
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.ipma.observation.parser import parse_ipma_observations_feed
from wetterdienst.provider.meteoswiss.observation import api as meteoswiss_api
from wetterdienst.provider.noaa.ghcn import api as ghcn_api
from wetterdienst.ui.core import resolve_network
from wetterdienst.util.network import list_remote_files_fsspec

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings


class DataIndex(NamedTuple):
    """How to read the ids of the data files of a network, and which coverage rules its source can be held to."""

    # the ids the data files of one dataset are named for, as the catalogue would write them
    ids: Callable[[Settings, DatasetModel], set[str]]
    rules: tuple[str, ...] = COVERAGE_RULES


def dataset_of(network: str, resolution: str, dataset: str) -> DatasetModel:
    """Give the metadata of a dataset of a network, such as `dwd/poi`, `hourly` and `data`."""
    provider, name = network.split("/")
    return resolve_network(provider, name).metadata[resolution][dataset]


def _listed_ids(url: str, settings: Settings, name: re.Pattern[str]) -> set[str]:
    """Read the ids of the files of a directory that the pattern takes, padded to the five digits the lists write."""
    files = _create_file_index_for_dwd_server(url, settings, CacheExpiry.TWELVE_HOURS).collect().get_column("filename")
    ids = {match.group(1).zfill(5) for file in files if not file.startswith("_") and (match := name.search(file))}
    return ids - {"00000"}


_ZIP_ID = re.compile(r"_(\d{1,5})_.*\.zip$")
_SOIL_ID = re.compile(r"_(\d{1,5})\.txt\.gz$")


def _dwd_observation(settings: Settings, dataset: DatasetModel) -> set[str]:
    """Read the stations the files of the dataset name for any of its periods, which the catalogue joins to."""
    urls = [_observation_url(dataset, period) for period in dataset.periods]
    return {station_id for url in urls for station_id in _listed_ids(url, settings, _ZIP_ID)}


def _dwd_derived(settings: Settings, dataset: DatasetModel) -> set[str]:
    name = _SOIL_ID if dataset.name == "soil" else _ZIP_ID
    urls = [_derived_url(dataset, period) for period in dataset.periods]
    return {station_id for url in urls for station_id in _listed_ids(url, settings, name)}


def _dwd_dmo(settings: Settings, dataset: DatasetModel) -> set[str]:
    """Read the directories of the stations a product forecasts for, which narrow the shared list."""
    request = DwdDmoRequest(parameters=[(dataset.resolution.name, dataset.name)], settings=settings)
    ids = request._read_covered_station_ids(dataset.name_original)  # noqa: SLF001
    assert ids is not None, "the directory of the DMO stations could not be read"
    return ids


def _dwd_poi(settings: Settings, _dataset: DatasetModel) -> set[str]:
    """Read the stations that have a report file, whose names pad an id with underscores."""
    files = poi_api.list_remote_files_fsspec(poi_api._BASE_URL, settings, CacheExpiry.TWELVE_HOURS)  # noqa: SLF001
    names = (file.rsplit("/", 1)[-1] for file in files)
    return {poi_api._station_id_from_file_name(name) for name in names if name.endswith(poi_api._FILE_SUFFIX)}  # noqa: SLF001


# the one place the listing of a directory is read from, which a stub of `chmi/observation` replaces
list_files = list_remote_files_fsspec


def _chmi(settings: Settings, dataset: DatasetModel) -> set[str]:
    """Read the ids of the files `<prefix>-<station>-<element>.csv` of every element of a resolution.

    A station is named by its WSI, as in the catalogue. The directory of an element lists the files of all stations.
    """
    config = chmi_api._RESOLUTION_CONFIG[dataset.resolution.value]  # noqa: SLF001
    ids = set()
    # a directory holds the files of several elements, so it is listed once
    for category in dict.fromkeys(element_config[0] for element_config in config["elements"].values()):
        url = f"{chmi_api._BASE_URL}/data/{config['path']}/{category}/"  # noqa: SLF001
        names = [file.rsplit("/", 1)[-1] for file in list_files(url, settings, CacheExpiry.NO_CACHE)]
        for element, element_config in config["elements"].items():
            if element_config[0] != category:
                continue
            name = re.compile(rf"^{re.escape(config['prefix'])}-(?P<station>.+)-{re.escape(element)}\.csv$")
            ids |= {match.group("station") for file in names if (match := name.match(file))}
    return ids


STAC_ITEMS = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn/items?limit=100"


def _meteoswiss(settings: Settings, dataset: DatasetModel) -> set[str]:
    """Read the stations whose STAC item lists a file of the resolution, as the reader looks for one.

    The reader asks for the item of a station by its lower-case id and takes the assets `ogd-smn_<id>_<granularity>`,
    so the id is the catalogue's, which is upper case.
    """
    granularity = dataset.resolution.name_original
    ids: set[str] = set()
    url: str | None = STAC_ITEMS
    while url:
        file = meteoswiss_api.download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        page = json.loads(file.content.read())
        for item in page["features"]:
            asset = re.compile(rf"^ogd-smn_{re.escape(item['id'])}_{re.escape(granularity)}(_.*)?\.csv$")
            if any(asset.match(name) for name in item["assets"]):
                ids.add(item["id"].upper())
        url = next((link["href"] for link in page.get("links", []) if link["rel"] == "next"), None)
    return ids


def _ipma(settings: Settings, _dataset: DatasetModel) -> set[str]:
    """Read the stations the feed of the last day has a reading of."""
    file = ipma_api.download_file(
        url=ipma_api._OBSERVATIONS_URL,  # noqa: SLF001
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.FIVE_MINUTES,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    file.raise_if_exception()
    feed = parse_ipma_observations_feed(file.content.read())
    readings = (stations for stations in feed.values() if isinstance(stations, dict))
    return {station_id for stations in readings for station_id, reading in stations.items() if reading}


def _ghcn_daily(settings: Settings, _dataset: DatasetModel) -> set[str]:
    """Read the stations of the inventory, which lists an element and the years of each, as the catalogue joins it."""
    file = ghcn_api.download_file(
        url="https://noaa-ghcn-pds.s3.amazonaws.com/ghcnd-inventory.txt",
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.TWELVE_HOURS,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    file.raise_if_exception()
    return {line[:11] for line in file.content.read().decode("utf8").splitlines() if line.strip()}


INDEXES: dict[str, DataIndex] = {
    "chmi/observation": DataIndex(_chmi),
    "dwd/derived": DataIndex(_dwd_derived),
    "dwd/dmo": DataIndex(_dwd_dmo),
    "dwd/observation": DataIndex(_dwd_observation),
    "dwd/poi": DataIndex(_dwd_poi),
    # the feed holds the last day: a station without a reading in it is down for the day as often as it is listed in
    # vain, so only a reading of a station the list does not carry is held
    "ipma/observation": DataIndex(_ipma, rules=("data_orphan",)),
    "meteoswiss/observation": DataIndex(_meteoswiss),
    "noaa/ghcn": DataIndex(_ghcn_daily),
}

# the networks that are held in their stub and not against the live list, with the reason
NOT_LIVE: dict[str, str] = {
    "dwd/observation": (
        "one listing for each of the 62 datasets and each of their periods, of which the historical "
        "`daily/precipitation_more` alone lists 6,156 files; the one-time run of GH-3248 held them all (GH-3258)"
    ),
}

_ONE_AT_A_TIME = "the data is read for one station at a time from an API with no listing of data files"

# the networks that are not held, with the reason: a network is here when its source lists no data file by station,
# or the list is the only listing there is, or it is held for a credential this does not use
NOT_HELD: dict[str, str] = {
    "aemet/observation": f"needs a credential, and {_ONE_AT_A_TIME}",
    "dmi/observation": _ONE_AT_A_TIME,
    "dwd/mosmix": (
        "the directory of a station exists beyond its forecasts: 396 of the 6,045 of `MOSMIX_L/single_stations` are "
        "not in the catalogue and the two read (EW002, 03041) are empty, so whether one holds a run takes a listing "
        "of each, 5,600 requests; the one listing would hold `data_missing` alone, and an empty directory would count "
        "as data (read 2026-10-21)"
    ),
    "dwd/phenology": "one file for each phase holds every station, and the historical ones run to 160 MB",
    "dwd/road": "one BUFR file for each station group and minute holds the stations of the group, named inside it",
    "dwd/swsmos": (
        "the stations are those of one run file (2 MB compressed, 300,000 rows) and differ from run to run: the run "
        "of 2026-10-21 20:00 UTC has no row for 28 of the 1,874 listed and one for O210, which is not listed"
    ),
    "ea/hydrology": _ONE_AT_A_TIME,
    "eaufrance/hubeau": f"building its catalogue takes minutes, and {_ONE_AT_A_TIME}",
    "eccc/observation": _ONE_AT_A_TIME,
    "fmi/observation": _ONE_AT_A_TIME,
    "geosphere/observation": _ONE_AT_A_TIME,
    "imgw/hydrology": "the archives are one for each month or year and hold every station, named inside the zip",
    "imgw/meteorology": "the archives are one for each month or year and hold every station, named inside the zip",
    "knmi/observation": "needs a credential, and one NetCDF file for each timestamp holds every station",
    "lhmt/observation": "the data is read for one station and day at a time from an API with no listing of data files",
    "meteofrance/observation": "one file for each department and period holds its stations, named inside it",
    "meteofrance/synop": "one file for each year holds every station, named inside it",
    "metno/frost": f"needs a credential, and {_ONE_AT_A_TIME}",
    "metoffice/observation": f"needs a credential, and {_ONE_AT_A_TIME}",
    "nws/observation": _ONE_AT_A_TIME,
    "rmi/observation": "one WFS feature for each timestamp holds every station, named inside it",
    "smhi/observation": "its catalogue is made from the list of stations of each parameter, which is that listing",
    "wsv/pegel": "the data is read for one station and parameter at a time from an API with no listing of data files",
}

# the datasets of a network that is held that are not: `<network> <resolution>/<dataset>` and the reason
NOT_HELD_DATASETS: dict[str, str] = {
    "chmi/observation 10_minutes/data": "one file for each element, station and month under a directory for each year",
    "chmi/observation hourly/data": "one file for each element, station and month under a directory for each year",
    "dwd/derived monthly/heating_degreedays": "one file for each month holds every station",
    "dwd/derived monthly/cooling_degreehours_13": "one file for each month holds every station",
    "dwd/derived monthly/cooling_degreehours_16": "one file for each month holds every station",
    "dwd/derived monthly/cooling_degreehours_18": "one file for each month holds every station",
    "dwd/derived monthly/climate_correction_factor": (
        "one file for each twelve months holds every postal code, and the catalogue lists all 100,000 numbers of five "
        "digits"
    ),
    "noaa/ghcn hourly/data": "the server lists no directory of the files of the stations, which are 404 for it",
}

_CHMI_PREFIX = "0-203-0-"


def _chmi_ids(*suffixes: str) -> frozenset[str]:
    """Name stations of `chmi/observation` by what follows the `0-203-0-` they all begin with."""
    return frozenset(f"{_CHMI_PREFIX}{suffix}" for suffix in suffixes)


# the stations of `meta1.csv` that have no file in a resolution, and the files of stations it does not list (GH-3259),
# read from the directories of the elements on 2026-10-21
_CHMI_NO_FILE = {
    "daily": _chmi_ids(
        *("11566", "11579", "11629", "20101066001", "20301043001", "20301050203", "20301056001", "41202002002"),
        *("41202085001", "41301003002", "41301012003", "41403038001", "41501040101", "41502008001", "41502014001"),
        *("41502109501", "41601096001", "41603044001", "41604006101", "41604023002", "41701001001", "41701043001"),
        *("41701095001", "42108058001", "42108076001"),
    ),
    "monthly": _chmi_ids(
        *("10407043001", "11004001001", "11480", "11566", "11579", "11629", "41202002002", "41202085001"),
        *("41301003002", "41301012003", "41403038001", "41501040101", "41502008001", "41502014001", "41502109501"),
        *("41601096001", "41603044001", "41604006101", "41604023002", "41701001001", "41701043001", "41701095001"),
        *("42108058001", "42108076001"),
    ),
    "annual": _chmi_ids(
        *("10407043001", "11004001001", "11301156001", "11480", "11566", "11579", "11629", "11799", "20303074001"),
        *("41202002002", "41202085001", "41301003002", "41301012003", "41403038001", "41501027001", "41501040101"),
        *("41502008001", "41502014001", "41502109501", "41601096001", "41602025001", "41603044001", "41604006101"),
        *("41604023002", "41701001001", "41701043001", "41701095001", "42108058001", "42108076001"),
    ),
}
_CHMI_NO_STATION = {
    "monthly": _chmi_ids(
        *("10101019002", "10201037002", "10501061001", "10501066001", "10502008001", "10602027002", "10801007001"),
        *("10803007001", "10902036001", "11001055001", "11002001002", "11101006001", "11302058001", "11401001001"),
        *("11403042001", "11405002001", "20201004002", "20202006001", "20202012001", "20301004002", "20301006001"),
        *("20301006002", "20303019001", "20410008001", "40102028001", "41001017002", "41101024001", "41101078002"),
        "41101095001",
    ),
    "annual": _chmi_ids(
        *("10101019002", "10201037002", "10501061001", "10502008001", "10602027002", "10801007001", "10803007001"),
        *("10902036001", "11001055001", "11002001002", "11101006001", "11302058001", "11401001001", "11405002001"),
        *("20201004002", "20202012001", "20303019001", "20410008001", "41001017002", "41101024001", "41101078002"),
        "41101095001",
    ),
}

CHMI_NO_FILE = Accepted(
    "data_missing",
    "the catalogue is one list for every resolution and lists closed stations of a short record that have no file in "
    "this one (GH-3259)",
    where=lambda row: row["station_id"] in _CHMI_NO_FILE.get(row["resolution"], ()),
)
CHMI_NO_STATION = Accepted(
    "data_orphan",
    "the monthly and annual files of stations that `meta1.csv` does not carry, 8 of them beside another suffix of the "
    "same station (GH-3259)",
    where=lambda row: row["station_id"] in _CHMI_NO_STATION.get(row["resolution"], ()),
)
DWD_NO_DESCRIPTION = Accepted(
    "data_orphan",
    "the historical file of station 01018 has no line in the description of its period, as those of 02996 and 05047 "
    "(GH-3258)",
    where=lambda row: row["station_id"] == "01018",
)
# the stations of `ghcnd-stations.txt` that the inventory has no line for, read on 2026-10-21 (GH-3260)
_GHCN_NO_INVENTORY = frozenset(
    (
        "CAN03010010",
        "CAN03010162",
        "CAN03010237",
        "CAN03010730",
        "CAN03010816",
        "CAN03010979",
        "CAN03010992",
        "CAN03011815",
        "CAN03011892",
        "CAN03012050",
        "CAN03012073",
        "CAN03012818",
        "CAN03013140",
        "CAN03013640",
        "CAN03013644",
        "CAN03013660",
        "CAN03013790",
        "CAN03014690",
        "CAN03014795",
        "CAN03014921",
        "CAN03015480",
        "CAN03015600",
        "CAN03015673",
        "CAN03015676",
        "CAN03015900",
        "CAN03016022",
        "CAN03016070",
        "CAN03016505",
        "CAN03016802",
        "CAN03016852",
        "CAN03017282",
        "CAN03020405",
        "CAN03020610",
        "CAN03020679",
        "CAN03021912",
        "CAN03023402",
        "CAN03023740",
        "CAN03024668",
        "CAN03024925",
        "CAN03024965",
        "CAN03025243",
        "CAN03025297",
        "CAN03026479",
        "CAN03027582",
        "CAN03030450",
        "CAN03030525",
        "CAN03030680",
        "CAN03030720",
        "CAN03030772",
        "CAN03030830",
        "CAN03032550",
        "CAN03032801",
        "CAN03032818",
        "CAN03032927",
        "CAN03033498",
        "CAN03033550",
        "CAN03033897",
        "CAN03034795",
        "CAN03035342",
        "CAN03035422",
        "CAN03035530",
        "CAN03035845",
        "CAN03036086",
        "CAN03036205",
        "CAN03044232",
        "CAN03044545",
        "CAN03045000",
        "CAN03050960",
        "CAN03050965",
        "CAN03056100",
        "CAN03056489",
        "CAN03060330",
        "CAN03060406",
        "CAN03061975",
        "CAN03063165",
        "CAN03072525",
        "CAN03073071",
        "CAN03073535",
        "CAN03074190",
        "CAN03074935",
        "CAN03075160",
        "CAN03075601",
        "CAN03076680",
        "GMM00010628",
        "SWE00138044",
        "SWE00139526",
        "SWE00140360",
        "SWE00140450",
        "SWE00140588",
        "USC00015131",
        "USC00043194",
        "USC00044883",
        "USC00045711",
        "USC00092994",
        "USC00095440",
        "USC00095974",
        "USC00120825",
        "USC00126615",
        "USC00130046",
        "USC00130199",
        "USC00130220",
        "USC00130580",
        "USC00131662",
        "USC00131724",
        "USC00132080",
        "USC00132197",
        "USC00132200",
        "USC00132202",
        "USC00133000",
        "USC00134229",
        "USC00135295",
        "USC00135558",
        "USC00135957",
        "USC00136115",
        "USC00136209",
        "USC00136570",
        "USC00137167",
        "USC00137249",
        "USC00137315",
        "USC00137717",
        "USC00138004",
        "USC00138341",
        "USC00138701",
        "USC00138749",
        "USC00144585",
        "USC00144840",
        "USC00204081",
        "USC00220198",
        "USC00221657",
        "USC00230031",
        "USC00230716",
        "USC00230823",
        "USC00231343",
        "USC00232731",
        "USC00232832",
        "USC00234375",
        "USC00234652",
        "USC00236421",
        "USC00238558",
        "USC00332725",
        "USC00348989",
        "USC00474105",
        "USC00474590",
        "USC00510177",
        "USC00514717",
        "USC00516938",
        "USC00517460",
    )
)

GHCN_NO_INVENTORY = Accepted(
    "data_missing",
    "147 stations of `ghcnd-stations.txt` have no line in the inventory and no data file (GH-3260)",
    where=lambda row: row["station_id"] in _GHCN_NO_INVENTORY,
)

# the exceptions of a stub, by its catalogue (`<network> <resolution>/<dataset>`): the mismatches of the source
ACCEPTED_STUB: dict[str, tuple[Accepted, ...]] = {
    "chmi/observation daily/data": (CHMI_NO_FILE,),
    "dwd/observation daily/climate_summary": (DWD_NO_DESCRIPTION,),
    "noaa/ghcn daily/data": (GHCN_NO_INVENTORY,),
}

# the exceptions of the live lists, by network
ACCEPTED_LIVE: dict[str, tuple[Accepted, ...]] = {
    "chmi/observation": (CHMI_NO_FILE, CHMI_NO_STATION),
    "dwd/derived": (
        Accepted(
            "data_orphan",
            "the directory of the soil files has nine files of stations that the list does not carry (GH-3258)",
            where=lambda row: (
                row["dataset"] == "soil"
                and row["station_id"]
                in {"01584", "02110", "02814", "02968", "03612", "04261", "05941", "07350", "13710"}
            ),
        ),
    ),
    "noaa/ghcn": (GHCN_NO_INVENTORY,),
    "meteoswiss/observation": (
        Accepted(
            "data_missing",
            "the STAC item of MLJ lists a daily, an hourly and a 10 minute file and no monthly or annual one "
            "(read 2026-10-21)",
            where=lambda row: row["station_id"] == "MLJ" and row["resolution"] in {"monthly", "annual"},
        ),
    ),
}
