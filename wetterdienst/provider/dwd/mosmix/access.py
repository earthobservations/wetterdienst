# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
# Source:
# https://github.com/jlewis91/dwdbulk/blob/master/dwdbulk/api/forecasts.py
from __future__ import annotations

import datetime as dt
import logging
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from fsspec.implementations.zip import ZipFileSystem
from lxml.etree import iterparse  # noqa: S410
from tqdm import tqdm

from wetterdienst.metadata.columns import Columns
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.io import read_in_chunks
from wetterdienst.util.logging import TqdmToLogger
from wetterdienst.util.network import NetworkFilesystemManager

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)


class KMLReader:
    """Read DWD XML Weather Forecast File of Type KML."""

    def __init__(self, station_ids: list[str], settings: Settings) -> None:
        self.station_ids = station_ids
        self.metadata = {}
        self.timesteps = []
        self.nsmap = None
        self.iter_elems = None

        self.dwdfs = NetworkFilesystemManager.get(settings=settings, ttl=CacheExpiry.FIVE_MINUTES)

    def download(self, url: str) -> BytesIO:
        """Download kml file as bytes.
        https://stackoverflow.com/questions/37573483/progress-bar-while-download-file-over-http-with-requests

        block_size: int or None
                    Bytes to download in one request; use instance value if None. If
                    zero, will return a streaming Requests file-like instance.

        :param url: url string to kml file
        :return: content as bytes
        """

        response = self.dwdfs.open(url, block_size=0)
        total = self.dwdfs.size(url)

        buffer = BytesIO()

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        with tqdm(
            desc=url,
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
            file=tqdm_out,
        ) as bar:
            for data in read_in_chunks(response, chunk_size=1024):
                size = buffer.write(data)
                bar.update(size)

        return buffer

    def fetch(self, url) -> bytes:
        """
        Fetch weather mosmix file (zipped xml).
        """
        buffer = self.download(url)
        zfs = ZipFileSystem(buffer, "r")
        return zfs.open(zfs.glob("*")[0]).read()

    def read(self, url: str):
        """
        Download and read DWD XML Weather Forecast File of Type KML.
        """

        log.info(f"Downloading KMZ file {Path(url).name}")
        kml = self.fetch(url)

        log.info("Parsing KML data")
        self.iter_elems = iterparse(BytesIO(kml), events=("start", "end"), resolve_entities=False)

        prod_items = {
            "issuer": "Issuer",
            "product_id": "ProductID",
            "generating_process": "GeneratingProcess",
            "issue_time": "IssueTime",
        }

        nsmap = None

        # Get Basic Metadata
        prod_definition = None
        prod_definition_tag = None
        for event, element in self.iter_elems:
            if event == "start":
                # get namespaces from root element
                if nsmap is None:
                    nsmap = element.nsmap
                    prod_definition_tag = f"{{{nsmap['dwd']}}}ProductDefinition"
            elif event == "end":
                if element.tag == prod_definition_tag:
                    prod_definition = element
                    # stop processing after head
                    # leave forecast data for iteration
                    break

        self.metadata = {k: prod_definition.find(f"{{{nsmap['dwd']}}}{v}").text for k, v in prod_items.items()}
        self.metadata["issue_time"] = dt.datetime.fromisoformat(self.metadata["issue_time"])

        # Get time steps.
        timesteps = prod_definition.findall(
            "dwd:ForecastTimeSteps",
            nsmap,
        )[0]
        self.timesteps = [dt.datetime.fromisoformat(i.text) for i in timesteps.getchildren()]

        # save namespace map for later iteration
        self.nsmap = nsmap

    def iter_items(self):
        clear = True
        placemark_tag = f"{{{self.nsmap['kml']}}}Placemark"
        for event, element in self.iter_elems:
            if event == "start":
                if element.tag == placemark_tag:
                    clear = False
            elif event == "end":
                if element.tag == placemark_tag:
                    yield element
                    clear = True
                if clear:
                    element.clear()

    def get_metadata(self):
        """Get metadata as DataFrame."""
        return pl.DataFrame([self.metadata])

    def get_station_forecast(self, station_id: str) -> pl.DataFrame:
        """Get forecasts as DataFrame."""
        for station_forecast in self.iter_items():
            if station_forecast.find("kml:name", self.nsmap).text != station_id:
                continue
            measurement_list = station_forecast.findall("kml:ExtendedData/dwd:Forecast", self.nsmap)
            data_dict = {Columns.DATE.value: self.timesteps}
            for measurement_item in measurement_list:
                measurement_parameter = measurement_item.get(f"{{{self.nsmap['dwd']}}}elementName")
                measurement_string = measurement_item.getchildren()[0].text
                measurement_values = " ".join(measurement_string.split()).split(" ")
                measurement_values = [None if i == "-" else float(i) for i in measurement_values]
                data_dict[measurement_parameter.lower()] = measurement_values
            station_forecast.clear()
            return pl.DataFrame(data_dict)
        else:
            raise IndexError(f"Station {station_id} not found in KML file")
